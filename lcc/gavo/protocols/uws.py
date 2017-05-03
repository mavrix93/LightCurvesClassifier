"""
Support classes for the universal worker service.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from __future__ import with_statement

import cPickle as pickle
import contextlib
import datetime
import os
import shutil
import signal
import tempfile
import weakref

from twisted.internet import protocol
from twisted.internet import reactor

from gavo import base
from gavo import rsc
from gavo import rscdef
from gavo import svcs
from gavo import utils
from gavo.base import cron

# Ward against typos
from gavo.votable.tapquery import ( #noflake: exported names
	PENDING, QUEUED, EXECUTING, COMPLETED, ERROR, ABORTED, UNKNOWN)

END_STATES = set([COMPLETED, ERROR, ABORTED])

# used in the computation of quote
EST_TIME_PER_JOB = datetime.timedelta(minutes=10)

_DEFAULT_LOCK_TIMEOUT = 20


__docformat__ = "restructuredtext en"


class UWSError(base.Error):
	"""UWS-related errors, mainly to communicate with web renderers.

	UWSErrors are constructed with a displayable message (may be None to
	autogenerate one), a jobId (give one; the default None is only there
	to avoid breaking legacy code) and optionally a source exception and a hint.
	"""
	def __init__(self, msg, jobId=None, sourceEx=None, hint=None):
		base.Error.__init__(self, msg, hint=hint)
		self.msg = msg
		self.jobId = jobId
		self.sourceEx = sourceEx
		self.args = [self.msg, self.jobId, self.sourceEx, self.hint]
	
	def __str__(self):
		if self.msg:
			return self.msg
		elif self.sourceEx:
			return "UWS on job %s operation failed (%s, %s)"%(
				self.jobId,
				self.sourceEx.__class__.__name__,
				str(self.sourceEx))
		else:
			return "Unspecified UWS related error (id: %s)"%self.jobId


class JobNotFound(base.NotFoundError, UWSError):
	def __init__(self, jobId):
		base.NotFoundError.__init__(self, str(jobId), "UWS job", "jobs table")
	
	def __str__(self):
		return base.NotFoundError.__str__(self)


class UWS(object):
	"""a UWS facade.

	You must construct it with the job class (see UWSJob) and a 
	uwsactions.JobActions instance

	The UWS then provides methods to access the jobs table,
	create jobs and and deserialize jobs from the jobs table.

	If you want more canned queries, use the 
	_makeMoreStatements(statements, jobsTable) hook.

	You must override the getURLForId(jobId) method in your concrete
	implementation.

	Also, you probably must override the 
	getParamsFromRequest(wjob, request, service)
	method that takes a writable job and a nevow-type request object and
	fills the job parameters from the request.  The default implementation
	does nothing, and you do not need to upcall.

	You should also override jobdocPreamble and joblistPreamble.  This
	is raw XML that is prepended to job and list documents.  This is primarily
	for PIs giving stylesheets, but given we don't use doctypes you could
	provide internal subsets there, too.  Anyway, see the TAP UWS runner 
	for examples.
	"""
	# how often should we check for jobs that wait for destruction?
	cleanupInterval = 3600*12

	# raw XML to prepend to joblist documents
	joblistPreamble = ""
	# raw XML to prepend to job documents
	jobdocPreamble = ""

	def __init__(self, jobClass, jobActions):
		self.jobClass = jobClass
		self.jobActions = jobActions
		self._statementsCache = None
		cron.runEvery(self.cleanupInterval, 
			"UWS %s jobs table reaper"%str(self),
			self.cleanupJobsTable)
	
	def _makeMoreStatements(self, statements, jobsTable):
		"""adds custom statements to the canned query dict in derived
		classes.
		"""
		pass

	def _makeStatementsCache(self):
		"""returns a dictionary containing canned queries to manipulate
		the jobs table for this UWS.
		"""
		res = {}
		td = self.jobClass.jobsTD
		with base.getTableConn() as conn:
			jobsTable = rsc.TableForDef(td, connection=conn, exclusive=True)
			res["getByIdEx"] = jobsTable.getQuery(td, "jobId=%(jobId)s", {"jobId": 0})
			res["feedToIdEx"] = None, jobsTable.addCommand, None
			res["deleteByIdEx"] = None, jobsTable.getDeleteQuery(
				"jobId=%(jobId)s")[0], None

			jobsTable = rsc.TableForDef(td, connection=conn)
			res["getById"] = jobsTable.getQuery(td, "jobId=%(jobId)s", {"jobId": 0})
			res["getAllIds"] = jobsTable.getQuery(
				[td.getColumnByName("jobId")], "")
			res["getIdsAndPhases"] = jobsTable.getQuery(
				[td.getColumnByName("jobId"), td.getColumnByName("phase")], "")

			countField = base.makeStruct(
				svcs.OutputField, name="count", type="integer", select="count(*)")
			res["countRunning"] = jobsTable.getQuery([countField],
				"phase='EXECUTING'")
			res["countQueued"] = jobsTable.getQuery([countField],
				"phase='QUEUED'")

			self._makeMoreStatements(res, jobsTable)
		return res

	@property
	def _statements(self):
		"""returns a dictionary of canned statements manipulating the jobs
		table.
		"""
		if self._statementsCache is None:
				self._statementsCache = self._makeStatementsCache()
		return self._statementsCache

	def runCanned(self, statementId, args, conn):
		"""runs the canned statement statementId with args through the
		DB connection conn.

		This will return row dictionaries of the result if there is a result.
		"""
		resultTableDef, statement, _ = self._statements[statementId]
		cursor = conn.cursor()

		try:
			cursor.execute(statement, args)
		except base.QueryCanceledError:
			conn.rollback()
			raise base.ReportableError("Could not access the jobs table."
				" This probably means there is a stale lock on it.  Please"
				" notify the service operators.")

		res = None
		if resultTableDef:
			res = [resultTableDef.makeRowFromTuple(row)
				for row in cursor]
		cursor.close()
		return res

	def _serializeProps(self, props, writableConn):
		"""inserts (or overwrites) the job properties props through
		wriableConn.
		"""
		self.runCanned("feedToIdEx", props, writableConn)

	def getNewJobId(self, **kws):
		"""creates a new job and returns its id.

		kws can be properties of the new job or the special key timeout
		giving after how many seconds we should give up trying to lock
		the db.
		"""
		timeout = kws.pop("timeout", _DEFAULT_LOCK_TIMEOUT)
		with base.getWritableTableConn() as conn:
			with base.connectionConfiguration(conn, timeout=timeout):
				props = self.jobClass.getDefaults(conn)
				props["jobId"] = self.jobClass.getNewId(self, conn)
				job = self.jobClass(props, self, writable=True)
				job.change(**kws)
				self._serializeProps(job.getProperties(), conn)
		return job.jobId

	def getNewIdFromRequest(self, request, service):
		"""returns the id of a new TAP job created from request.

		Request has to be a newow request or similar, with request arguments in
		request.args.

		This calls getParamsFromRequest(wjob, request, service) to do the actual
		work; this latter method is what individual UWSes should override.
		"""
		jobId = self.getNewJobId()
		with self.changeableJob(jobId) as wjob:
			self.getParamsFromRequest(wjob, request, service)
		return jobId

	def getParamsFromRequest(self, wjob, request, service):
		"""should transfer "interesting" arguments from request to wjob.

		The default implementation does nothing; override this in actual UWSes.
		"""
		return

	def _getJob(self, jobId, conn, writable=False):
		"""helps getJob and getNewJob.
		"""
		statementId = 'getById'
		if writable:
			statementId = 'getByIdEx'
		res = self.runCanned(statementId, {"jobId": jobId}, conn)
		if len(res)!=1:
			raise JobNotFound(jobId)
		return self.jobClass(res[0], self, writable)

	def getJob(self, jobId):
		"""returns a read-only UWSJob for jobId.

		Note that by the time you do something with the information here,
		the "true" state in the database may already be different.  There
		should be no way to write whatever information you have in here,
		so any "racing" here shouldn't hurt.
		"""
		with base.getTableConn() as conn:
			return self._getJob(jobId, conn)

	def getNewJob(self, **kws):
		"""creates a new job and returns a read-only instance for it.
		"""
		newId = self.getNewJobId(**kws)
		return self.getJob(newId)

	@contextlib.contextmanager
	def changeableJob(self, jobId, timeout=_DEFAULT_LOCK_TIMEOUT):
		"""a context manager for job manipulation.

		This is done such that any changes to the job's properties
		within the controlled section get propagated to the database.
		As long as you are in the controlled section, nobody else
		can change the job.
		"""
		with base.getWritableTableConn() as conn:
			with base.connectionConfiguration(conn, timeout=timeout):
				job = self._getJob(jobId, conn, writable=True)
				try:
					yield job
				except:
					conn.rollback()
					raise
				else:
					self._serializeProps(job.getProperties(), conn)
					conn.commit()

	def changeToPhase(self, jobId, newPhase, input=None, 
			timeout=_DEFAULT_LOCK_TIMEOUT):
		with self.changeableJob(jobId, timeout=timeout) as wjob:
			try:
				transition = wjob.getTransitionTo(newPhase)
				return transition(newPhase, wjob, input)
			except Exception, exception:
				# transition to error if possible.  If that fails at well,
				# blindly set error and give up.
				try:
					if newPhase!=ERROR:
						return wjob.getTransitionTo(ERROR)(ERROR, wjob, exception)
				except:
					wjob.change(phase=ERROR, error=exception)
				raise

	def destroy(self, jobId):
		"""removes the job with jobId from the UWS.

		This calls the job's prepareForDestruction method while the job is writable.
		"""
		try:
			try:
				with self.changeableJob(jobId) as job:
					job.prepareForDestruction()
			except Exception, exc:
				base.ui.notifyWarning(
					"Ignored error while destroying UWS job %s: %s"%(jobId, exc))
		finally:
			with base.getWritableTableConn() as conn:
				self.runCanned("deleteByIdEx", locals(), conn)

	def _countUsingCanned(self, statementId):
		"""helps the count* methods.
		"""
		with base.getTableConn() as conn:
			return self.runCanned(statementId, {}, conn)[0]["count"]

	def countRunningJobs(self):
		"""returns the number of EXECUTING jobs in the jobsTable.
		"""
		return self._countUsingCanned('countRunning')

	def countQueuedJobs(self):
		"""returns the number of QUEUED jobs in jobsTable.
		"""
		return self._countUsingCanned('countQueued')

	def getJobIds(self):
		"""returns a list of all currently existing job ids.
		"""
		with base.getTableConn() as conn:
			return [r["jobId"] for r in self.runCanned('getAllIds', {}, conn)]

	def getIdsAndPhases(self):
		"""returns pairs for id and phase for all jobs in the UWS.
		"""
		with base.getTableConn() as conn:
			return [(r["jobId"], r["phase"])
				for r in self.runCanned('getIdsAndPhases', {}, conn)]

	def cleanupJobsTable(self, includeFailed=False, includeCompleted=False,
			includeAll=False, includeForgotten=False):
		"""removes expired jobs from the UWS jobs table.

		The constructor arranged for this to be called now and then
		(cleanupFrequency class attribute, defaulting to 12*3600).

		The functionality is also exposed through gavo admin cleanuws; this
		also lets you use the includeFailed and includeCompleted flags.  These
		should not be used on production services since you'd probably nuke
		jobs still interesting to your users.
		"""
		phasesToKill = set()
		if includeFailed or includeAll:
			phasesToKill.add(ERROR)
			phasesToKill.add(ABORTED)
		if includeCompleted or includeAll:
			phasesToKill.add(COMPLETED)
		if includeAll:
			phasesToKill.add(PENDING)
			phasesToKill.add(QUEUED)
		if includeForgotten:
			phasesToKill.add(PENDING)

		now = datetime.datetime.utcnow()
		for jobId in self.getJobIds():
			job = self.getJob(jobId)
			if (job.destructionTime<now
					or job.phase in phasesToKill):
				try:
					self.destroy(jobId)
				except base.QueryCanceledError: # job locked by something, don't hang
					base.ui.notifyWarning("Postponing destruction of %s: Locked"%
						jobId)
				except JobNotFound:
					# Someone else has cleaned up -- that's ok
					pass

	def getURLForId(self, jobId):
		"""returns the handling URL for the job with jobId.

		You must override this in deriving classes.
		"""
		raise NotImplementedError("Incomplete UWS (getURLForId not overridden).")


class ParameterRef(object):
	"""A UWS parameter.that is (in effect) a URL.

	This always contains a URL.  In case of uploads, the tap renderer makes
	sure the upload is placed into the upload directory and generates a
	URL; in that case, local is True.

	You need this class when you want the byReference attribute in
	the UWS.parameter element to be true.
	"""
	def __init__(self, url, local=False):
		self.local = local
		self.url = url


class JobParameter(object):
	"""A UWS job parameter.

	Job parameters are (normally) elements of a job's parameters dictionary,
	i.e., usually elements of the job control language.  "Magic" parameters
	that allow automatic serialization or special effects on the job
	can be defined using the _parameter_name class attributes of
	UWSJobs.  They are employed when using the setSerializedPar and
	getSerializedPar interface.

	All methods of these are class or static methods since 
	ProtocolParameters are never instanciated.

	The default value setter enforces a maximum length of 50000 characters
	for incoming strings.  This is a mild shield against accidental DoS
	with, e.g., bad uploads in TAP.

	The serialization thing really belongs to the user-facing interface.
	However, since it's most convenient to have these parameters
	in the UWSJob classes, the class is defined here.

	Internal clients would read the parameters directly from the dictionary.

	Methods you can override:

		- addPar(value, job) -> None -- parse value and perform some action
			(typically, set an attribute) on job.  The default implementation
			puts value into the parameters dictionary _deserialized.
		- getPar(job) -> string -- infer a string representation of the
			job parameter on job.  The default implementation gets
			the value from the parameter from the parameters dictionary and
			_serializes it.
		- _deserialize(str) -> val -- turns something from an XML tree
		  into a python value as usable by the worker
		- _serialize(val) -> str -- yields some XML-embeddable serialization
		  of val

	The default implementation just dumps/gets name from the job's
	parameters dict.  This is the behaviour for non-magic parameters
	since (get|set)SerializedPar falls back to the base class.

	CAUTION: Do *not* say job.parameters[bla] = "ab" -- your changes
	will get lost because serialisation of the parameters dictioanry must
	be initiated manually.  Always manipulate the parameters dictionary
	by using cls.updatePar(name, value, job) or a suitable
	facade (job.setPar, job.setSerializedPar)
	"""
	_deserialize, _serialize = str, str

	@classmethod
	def updatePar(cls, name, value, job):
		"""enters name:value into job's parameter dict.

		See the uws.JobParameter's docstring.
		"""
		# this is a bit magic because job.parameters is only re-encoded
		# on demand
		parameters = job.parameters
		parameters[name] = value
		# see our docstring
		job.change(parameters=parameters)

	@classmethod
	def addPar(cls, name, value, job):
		# this is a somewhat lame protection against file uploads
		# gone haywire: ignore any values longer than 50k
		if isinstance(value, basestring) and len(value)>50000:
			base.ui.notifyWarning("UWS Parameter %s discarded as too long; first"
				" bytes: %s"%(name, repr(value[:20])))
		cls.updatePar(name, cls._deserialize(value), job)

	@classmethod
	def getPar(cls, name, job):
		return cls._serialize(job.parameters[name])


class UWSJobType(type):
	"""The metaclass for UWS jobs.

	We have the metaclass primarily because we want to delay loading
	the actual definition until it is actually needed (otherwise we
	might get interesting chicken-egg-problems with rscdesc at some point).

	A welcome side effect is that we can do custom constructors and
	similar cosmetic deviltry.
	"""
	@property
	def jobsTD(cls):
		try:
			return cls._jobsTDCache
		except AttributeError:
			cls._jobsTDCache = base.resolveCrossId(cls._jobsTDId, rscdef.TableDef)
			return cls._jobsTDCache
	

class BaseUWSJob(object):
	"""An abstract UWS job.

	UWS jobs are always instanciated with a row from the associated
	jobs table (i.e. a dictionary giving all the uws parameters).  You
	can read the properties as attributes.  UWSJobs also keep
	a (weak) reference to the UWS that made them.

	To alter uws parameters, use the change method.  This will fail unless
	the job was created giving writable=True.

	To make it concrete, you need to define:

	- a _jobsTDid attribute giving the (cross) id of the UWS jobs
	  table for this kind of job
	- a _transitions attribute giving a UWSTransitions instance that defines
	  what to do on transistions
	- as needed, class methods _default_<parName> if you need to default
	  job parameters in newly created jobs
	- as needed, methods _decode_<parName> and _encode_<parName>
	  to bring uws parameters (i.e., everything that has a DB column)
	  from and to the DB representation from *python* values.

	You may want to override:

	- a class method getNewId(uws, writableConn) -> str, a method 
	  allocating a unique id for a new job and returning it.  Beware
	  of races here; if your allocation is through the database table,
	  you'll have to lock it *and* write a preliminary record with your new
	  id.  The default implementation does this, but if you want
	  something in the file system, you probably don't want to
	  use that.

	If have have non-string items in the job parameters dictionary, define
	class attributes _parameters_<parname.lower()> with JobParameter
	values saying how they are serialized and deserialized.  You
	do not need to do this for string parameters.
	
	If you need to clean up before the job is torn down, redefine
	the prepareForDestruction method.
	"""
# Why no properties?  Well, I could do them from the metaclass, and
# that'd suck since I'd have to parse the resource descriptor on
# module import, and I don't want that.  So, it'd be major trickery
# and I don't think it's worth that kind of effort.
#
# Why the odd hoops with serialization and deserialization?
# Well, what's in the database is "directly" defined by the protocol.
# Thus, the protocol methods (e.g., speaking HTTP) will know about the
# external representations, and UWSJobs just return python values for them.
#
# For job parameters, the serialization is something about the job control
# language.  Thus, the serialization is better done by the job class
# rather than the code implementing the underlying protocol.  Hence
# the JobParameters magic.  See also the TAP job, where that kind of
# thing is actually used.

	__metaclass__ = UWSJobType

	def __init__(self, props, uws, writable=False):
		object.__setattr__(self, "_props", props)
		self.writable = writable
		self.uws = weakref.proxy(uws)

	def __getattr__(self, name):
		if name in self._props:
			return getattr(self, "_decode_"+name, utils.identity)(
				self._props[name])
		raise AttributeError("%s objects have no attribute '%s'"%(
			self.__class__.__name__, name))

	def __setattr__(self, name, value):
		# ward against tempting bugs, disallow assigning to names in _props:
		if name in self._props:
			raise TypeError("Use the change method to change the %s"
				" attribute."%name)
		object.__setattr__(self, name, value)

	@property
	def quote(self):
		"""Always returns None.

		Override if you have a queue management.
		"""
		return None

	@classmethod
	def getNewId(cls, uws, conn):
		cursor = conn.cursor()
		tableName = cls.jobsTD.getQName()
		cursor.execute("LOCK TABLE %s IN ACCESS SHARE MODE"%tableName)
		try:
			while True:
				newId = utils.getRandomString(10)
				cursor.execute("SELECT * FROM %s WHERE jobId=%%(jobId)s"%tableName,
					{"jobId": newId})
				if not list(cursor):
					cursor.execute(
						"INSERT INTO %s (jobId) VALUES (%%(jobId)s)"%tableName,
						{"jobId": newId})
					break
			cursor.close()
			conn.commit()
		except:
			conn.rollback()
			raise
		return newId

	@classmethod
	def getDefaults(cls, conn):
		"""returns a dictionary suitable for inserting into a jobsTD table.
		"""
		res = {}
		for column in cls.jobsTD:
			name = column.name
			res[name] = getattr(cls, "_default_"+name, lambda: None)()
		return res

	@classmethod
	def _default_phase(cls):
		return PENDING

	@classmethod
	def _default_executionDuration(cls):
		return base.getConfig("async", "defaultExecTime")
	
	@classmethod
	def _default_destructionTime(cls):
		return datetime.datetime.utcnow()+datetime.timedelta(
			seconds=base.getConfig("async", "defaultLifetime"))

	def _encode_error(self, value):
		"""returns a pickled dictionary with error information.

		value can either be an exception object or a dictionary as
		generated here.
		"""
		if value is None:
			return None
		if not isinstance(value, dict):
			value = {
				"type": value.__class__.__name__,
				"msg": unicode(value),
				"hint": getattr(value, "hint", None),
			}
		return pickle.dumps(value)

	def _decode_error(self, value):
		"""returns the unpickled three-item dictionary from the database string.
		"""
		if value is None:
			return None
		return pickle.loads(str(value))

	@classmethod
	def _default_parameters(cls):
		return pickle.dumps({}, protocol=2).encode("zlib").encode("base64")
	
	def _encode_parameters(self, value):
		"""(db format for parameters is a pickle)
		"""
		return pickle.dumps(value, protocol=2).encode("zlib").encode("base64")
	
	def _decode_parameters(self, value):
		"""(db format for parameters is a pickle)
		"""
		return pickle.loads(str(value).decode("base64").decode("zlib"))

	def _getParameterDef(self, parName):
		"""returns the job/uws parameter definition for parName and the name 
		the parameter will actually be stored as.

		All these parameters are forced to be lower case (and thus
		case-insensitive).  The actual storage name of the parameter is
		still returned in case saner conventions may be forthcoming.
		"""
		parName = parName.lower()
		name = "_parameter_"+parName
		if hasattr(self, name):
			return getattr(self, name), parName
		return JobParameter, parName

	def setSerializedPar(self, parName, parValue):
		"""enters parName:parValue into self.parameters after deserializing it.

		This is when input comes from text; use setPar for values already 
		parsed.
		"""
		parDef, name = self._getParameterDef(parName)
		parDef.addPar(name, parValue, self)

	def setPar(self, parName, parValue):
		"""enters parName:parValue into self.parameters.
		"""
		parDef, name = self._getParameterDef(parName)
		parDef.updatePar(name, parValue, self)

	def getSerializedPar(self, parName):
		"""returns self.parameters[parName] in text form.

		This is for use from a text-based interface.  Workers read from
		parameters directly.
		"""
		parDef, name = self._getParameterDef(parName)
		return parDef.getPar(name, self)

	def iterSerializedPars(self):
		"""iterates over the serialized versions of the parameters.
		"""
		for key in self.parameters:
			yield key, self.getSerializedPar(key)

	def getTransitionTo(self, newPhase):
		"""returns the action prescribed to push self to newPhase.

		A ValidationError is raised if no such transition is defined.
		"""
		return self._transitions.getTransition(self.phase, newPhase)

	def change(self, **kwargs):
		"""changes the property values to what's given by the keyword arguments.

		It is an AttributeError to try and change a property that is not defined.
		"""
		if not self.writable:
			raise TypeError("Read-only UWS job (You can only change UWSJobs"
				"obtained through changeableJob.")
		for propName, propValue in kwargs.iteritems():
			if propName not in self._props:
				raise AttributeError("%ss have no attribute %s"%(
					self.__class__.__name__, propName))
			self._props[propName] = getattr(self, "_encode_"+propName,
				utils.identity)(propValue)

	def getProperties(self):
		"""returns the properties of the job as they are stored in the
		database.

		Use attribute access to read them and change to change them.  Do
		*not* get values from the dictionary you get and do *not* change
		the dictionary.
		"""
		return self._props

	def update(self):
		"""fetches a new copy of the job props from the DB.

		You should in general not need this, since UWSJob objects are intended
		to be short-lived ("for the duration of an async request").  Still,
		for testing and similar, it's convenient to be able to update
		a UWS job from the database.
		"""
		self._props = self.uws.getJob(self.jobId)._props

	def prepareForDestruction(self):
		"""is called before the job's database row is torn down.

		Self is writable at this point.
		"""

	def getURL(self):
		"""returns the UWS URL for this job.
		"""
		return self.uws.getURLForId(self.jobId)

	@contextlib.contextmanager
	def getWritable(self):
		"""a context manager for a writeable version of the job.

		Changes will be written back at the end, and the job object itself
		will be updated from the database.
		"""
		with self.uws.changeableJob(self.jobId) as wjob:
			yield wjob
		self.update()


class UWSJobWithWD(BaseUWSJob):
	"""A UWS job with a working directory.

	This generates ids from directory names in a directory (the
	uwsWD) shared for all UWSes on the system.

	It also adds methods 
	
	- getWD() -> str returning the working directory
	- addResult(self, source, mimeType, name=None) to add a new
	  result
	- openResult(self, mimeType, name) -> file to get an open file in the
	  WD to write to in order to generate a result
	- getResult(self, resName) -> str to get the *path* of a result with
	  resName
	- getResults(self) -> list-of-dicts to get dicts describing all
	  results available
	- openFile(self) -> file to get a file letting you read an existing
	  result.
	"""
	@classmethod
	def getNewId(self, uws, conn):
		# our id is the base name of the jobs's temporary directory.
		uwsWD = base.getConfig("uwsWD")
		utils.ensureDir(uwsWD, mode=0775, setGroupTo=base.getGroupId())
		jobDir = tempfile.mkdtemp("", "", dir=uwsWD)
		return os.path.basename(jobDir)

	def getWD(self):
		return os.path.join(base.getConfig("uwsWD"), self.jobId)

	def prepareForDestruction(self):
		shutil.rmtree(self.getWD())

	# results management: We use a pickled list in the jobs dir to manage 
	# the results.  I once had a table of those in the DB and it just
	# wasn't worth it.  One issue, though: this potentially races
	# if two different processes/threads were to update the results
	# at the same time.  This could be worked around by writing
	# the results pickle only from within changeableJobs.
	# 
	# The list contains dictionaries having resultName and resultType keys.
	@property
	def _resultsDirName(self):
		return os.path.join(self.getWD(), "__RESULTS__")

	def _loadResults(self):
		try:
			with open(self._resultsDirName) as f:
				return pickle.load(f)
		except IOError:
			return []

	def _saveResults(self, results):
		handle, srcName = tempfile.mkstemp(dir=self.getWD())
		with os.fdopen(handle, "w") as f:
			pickle.dump(results, f)
		# The following operation will bomb on windows when the second
		# result is saved.  Tough luck.
		os.rename(srcName, self._resultsDirName)

	def _addResultInJobDir(self, mimeType, name):
		resTable = self._loadResults()
		resTable.append(
			{'resultName': name, 'resultType': mimeType})
		self._saveResults(resTable)

	def addResult(self, source, mimeType, name=None):
		"""adds a result, with data taken from source.

		source may be a file-like object or a byte string.

		If no name is passed, a name is auto-generated.
		"""
		if name is None:
			name = utils.intToFunnyName(id(source))
		with open(os.path.join(self.getWD(), name), "w") as destF:
			if isinstance(source, basestring):
				destF.write(source)
			else:
				utils.cat(source, destF)
		self._addResultInJobDir(mimeType, name)

	def openResult(self, mimeType, name):
		"""returns a writable file that adds a result.
		"""
		self._addResultInJobDir(mimeType, name)
		return open(os.path.join(self.getWD(), name), "w")

	def getResult(self, resName):
		"""returns a pair of file name and mime type for a named job result.

		If the result does not exist, a NotFoundError is raised.
		"""
		res = [r for r in self._loadResults() if resName==r["resultName"]]
		if not res:
			raise base.NotFoundError(resName, "job result",
				"uws job %s"%self.jobId)
		res = res[0]
		return os.path.join(self.getWD(), res["resultName"]), res["resultType"]

	def getResults(self):
		"""returns a list of this service's results.

		The list contains dictionaries having at least resultName and resultType
		keys.
		"""
		return self._loadResults()

	def openFile(self, name, mode="r"):
		"""returns an open file object for a file within the job's work directory.

		No path parts are allowed on name.
		"""
		if "/" in name:
			raise ValueError("No path components allowed on job files.")
		return open(os.path.join(self.getWD(), name), mode)


class UWSTransitions(object):
	"""An abstract base for classes defining the behaviour of a UWS.

	This basically is the definition of a finite state machine with
	arbitrary input (which is to say: the input "alphabet" is up to
	the transitions).
	
	A UWSTransitions instance is in the transitions attribute of a job
	class.

	The main interface to UWSTransitions is getTransition(p1, p2) -> callable
	It returns a callable that should push the automaton from phase p1
	to phase p2 or raise an ValidationError for a field phase.

	The callable has the signature f(desiredPhase, wjob, input) -> None.
	It must alter the uwsJob object as appropriate.  input is some object
	defined by the the transition.  The job passed is a changeable job,
	so the handlers actually hold locks to the job row.  Thus, be brief.

	The transitions are implemented as simple methods having the signature
	of the callables returned by getTransition.  
	
	To link transistions and methods, pass a vertices list to the constructor.
	This list consists of 3-tuples of strings (from, to, method-name).  From and
	to are phase names (use the symbols from this module to ward against typos).
	"""
	def __init__(self, name, vertices):
		self.name = name
		self._buildTransitions(vertices)
	
	def _buildTransitions(self, vertices):
		self.transitions = {}
		# set some defaults
		for phase in [PENDING, QUEUED, EXECUTING, ERROR, ABORTED, COMPLETED]:
			self.transitions.setdefault(phase, {})[ERROR] = "flagError"
		self.transitions.setdefault(EXECUTING, {})[COMPLETED
			] = "noteEndTime"

		for fromPhase, toPhase, methodName in vertices:
			self.transitions.setdefault(fromPhase, {})[toPhase] = methodName
	
	def getTransition(self, fromPhase, toPhase):
		if (fromPhase==toPhase or
				fromPhase in END_STATES):
			# ignore null or ignorable transitions
			return lambda p, job, input: None
		try:
			methodName = self.transitions[fromPhase][toPhase]
		except KeyError:
			raise base.ui.logOldExc(
				base.ValidationError("No transition from %s to %s defined"
				" for %s jobs"%(fromPhase, toPhase, self.name),
				"phase", hint="This almost always points to an implementation error"))
		try:
			return getattr(self, methodName)
		except AttributeError:
			raise base.ui.logOldExc(
				base.ValidationError("%s Transitions have no %s methods"%(self.name,
				methodName),
				"phase", hint="This is an error in an internal protocol definition."
				"  There probably is nothing you can do but complain."))

	def noOp(self, newPhase, job, ignored):
		"""a sample action just setting the new phase.

		This is a no-op baseline sometimes useful in user code.
		"""
		job.change(phase=newPhase)

	def flagError(self, newPhase, wjob, exception):
		"""the default action when transitioning to an error: dump exception and
		mark phase as ACTION.
		"""
		wjob.change(phase=ERROR)
		# Validation errors don't get logged -- for one, they probably
		# are the user's fault, and for a second, logging them upsets
		# trial during testing, since trial examines the log.
		if not isinstance(exception, base.ValidationError):
			base.ui.notifyError("Error during UWS execution of job %s"%wjob.jobId)
		wjob.change(error=exception)
		if wjob.endTime is None:
			wjob.change(endTime=datetime.datetime.utcnow())
	
	def noteEndTime(self, newPhase, wjob, ignored):
		wjob.change(endTime=datetime.datetime.utcnow())


class SimpleUWSTransitions(UWSTransitions):
	"""A UWSTransitions with sensible transitions pre-defined.
	
	See the source for what we consider sensible.

	The idea here is that you simply override (and usually up-call)
	the methods queueJob, markAborted, startJob, completeJob,
	killJob, errorOutJob, and ignoreAndLog.

	You will have to define startJob and provide some way to execute
	startJob on QUEUED jobs (there's nothing wrong with immediately
	calling self.startJob(...) if you don't mind the DoS danger).

	Once you have startJob, you'll probably want to define killJob as
	well.
	"""
	def __init__(self, name):
		UWSTransitions.__init__(self, name, [
			(PENDING, QUEUED, "queueJob"),
			(PENDING, ABORTED, "markAborted"),
			(QUEUED, ABORTED, "markAborted"),
			(QUEUED, EXECUTING, "startJob"),
			(EXECUTING, COMPLETED, "completeJob"),
			(EXECUTING, ABORTED, "killJob"),
			(EXECUTING, ERROR, "errorOutJob"),
			(COMPLETED, ERROR, "ignoreAndLog"),
			])

	def queueJob(self, newState, wjob, ignored):
		"""puts a job on the queue.
		"""
		wjob.change(phase=QUEUED)

	def markAborted(self, newState, wjob, ignored):
		"""simply marks job as aborted.

		This is what happens if you abort a job from QUEUED or
		PENDING.
		"""
		wjob.change(phase=ABORTED,
			endTime=datetime.datetime.utcnow())

	def ignoreAndLog(self, newState, wjob, exc):
		"""logs an attempt to transition when it's impossible but
		shouldn't result in an error.

		This is mainly so COMPLETED things don't fail just because of some
		mishap.
		"""
		base.ui.logErrorOccurred("Request to push %s job to ERROR: %s"%(
			wjob.phase, str(exc)))

	def errorOutJob(self, newPhase, wjob, ignored):
		"""pushes a job to an error state.

		This is called by a worker; leaving the error message itself
		is part of the worker's duty.
		"""
		wjob.change(phase=newPhase, endTime=datetime.datetime.utcnow())
		self.flagError(newPhase, wjob, ignored)

	def killJob(self, newPhase, wjob, ignored):
		"""should abort a job.

		There's really not much we can do here, so this is a no-op.

		Do not up-call here, you'll get a (then spurious) warning
		if you do.
		"""
		base.ui.notifyWarning("%s UWSes cannot kill jobs"%self.name)
	
	def completeJob(self, newPhase, wjob, ignored):
		"""pushes a job into the completed state.
		"""
		wjob.change(phase=newPhase, endTime=datetime.datetime.utcnow())


def _replaceFDs(inFName, outFName):
# This is used for clean forking and doesn't actually belong here.
# utils.ostricks should take this.
  """closes all (findable) file descriptors and replaces stdin with inF
  and stdout/err with outF.
  """
  for fd in range(255, -1, -1):
    try:
      os.close(fd)
    except os.error:
      pass
  ifF, outF = open(inFName), open(outFName, "w")
  os.dup(outF.fileno())



class _UWSBackendProtocol(protocol.ProcessProtocol):
	"""The protocol used for taprunners when spawning them under a twisted
	reactor.
	"""
	def __init__(self, jobId, workerSystem):
		self.jobId = jobId
		self.workerSystem = workerSystem

	def outReceived(self, data):
		base.ui.notifyInfo("TAP worker %s produced output: %s"%(
			self.jobId, data))
	
	def errReceived(self, data):
		base.ui.notifyInfo("TAP worker %s produced an error message: %s"%(
			self.jobId, data))
	
	def processEnded(self, statusObject):
		"""tries to ensure the job is in an admitted end state.
		"""
		try:
			job = self.workerSystem.getJob(self.jobId)
			if job.phase==QUEUED or job.phase==EXECUTING:
				try:
					raise UWSError("Job hung in %s"%job.phase, job.jobId)
				except UWSError, ex:
					self.workerSystem.changeToPhase(self.jobId, ERROR, ex)
		except JobNotFound: # job already deleted
			pass


class ProcessBasedUWSTransitions(SimpleUWSTransitions):
	"""A SimpleUWSTransistions that processes its stuff in a child process.

	Inheriting classes must implement the getCommandLine(wjob) method --
	it must return a command (suitable for reactor.spawnProcess and
	os.execlp and a list of arguments suitable for reactor.spawnProcess.

	The must also implement some sort of queue management.  The the simplest
	case, override queueJob and start the job from there (but set
	to QUEUED in there anyway).
	"""
	def getCommandLine(self, wjob):
		raise NotImplementedError("%s transitions do not define how"
			" to get a command line"%self.__class__.__name__)

	def _startJobTwisted(self, wjob):
		"""starts a job by forking a new process when we're running 
		within a twisted reactor.
		"""
		assert wjob.phase==QUEUED
		cmd, args = self.getCommandLine(wjob)
		pt = reactor.spawnProcess(_UWSBackendProtocol(wjob.jobId, wjob.uws),
			cmd, args=args,
				env=os.environ)
		wjob.change(pid=pt.pid, phase=EXECUTING)

	def _startJobNonTwisted(self, wjob):
		"""forks off a new process when (hopefully) a manual child reaper 
		is in place.
		"""
		cmd, args = self.getCommandLine(wjob)
		pid = os.fork()
		if pid==0:
			_replaceFDs("/dev/zero", "/dev/null")
			os.execlp(cmd, *args)
		elif pid>0:
			wjob.change(pid=pid, phase=EXECUTING)
		else:
			raise Exception("Could not fork")
	
	def startJob(self, newState, wjob, ignored):
		"""causes a process to be started that executes job.

		This dispatches according to whether or not we are within a twisted
		event loop, mostly for testing support.
		"""
		if reactor.running:
			return self._startJobTwisted(wjob)
		else:
			return self._startJobNonTwisted(wjob)

	def killJob(self, newState, wjob, ignored):
		"""tries to kill/abort job.

		Actually, there are two different scenarios here: Either the job as
		a non-NULL startTime.  In that case, the child job is in control 
		and will manage the state itself.  Then kill -INT will do the right 
		thing.

		However, if startTime is NULL, the child is still starting up.  Sending
		a kill -INT may to many things, and most of them we don't want.
		So, in this case we kill -TERM the child, do state management ourselves
		and hope for the best.
		"""
		try:
			pid = wjob.pid
			if pid is None:
				raise UWSError("Job is not running")
			if wjob.startTime is None:
				# the child job is not up yet, kill it brutally and manage
				# state ourselves
				os.kill(pid, signal.SIGTERM)
				self.markAborted(ABORTED, wjob, ignored)
			else:
				# child job is up, can manage state itself
				os.kill(pid, signal.SIGINT)
		except UWSError:
			raise
		except Exception, ex:
			raise UWSError(None, ex)
