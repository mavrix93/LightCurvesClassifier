"""
TAP: schema maintenance, job/parameter definition incl. upload and UWS actions.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from __future__ import with_statement

import datetime
import os
import threading

from gavo import base
from gavo import rsc
from gavo import svcs
from gavo import utils
from gavo.imp.pyparsing import ParseException
from gavo.protocols import uws
from gavo.protocols import uwsactions
from gavo.utils import codetricks
from gavo.utils import stanxml


RD_ID = "__system__/tap"

# used in the computation of quote
EST_TIME_PER_JOB = datetime.timedelta(minutes=10)

# A mapping of values of TAP's FORMAT parameter to our formats.format codes,
# IANA mimes and user-readable labels.
# Used below (1st element of value tuple) and for registry purposes.
FORMAT_CODES = {
	base.votableType:
		("votable", base.votableType, "VOTable, binary", 
			"ivo://ivoa.net/std/TAPRegExt#output-votable-binary"),
	"text/xml": 
		("votable", "text/xml", "VOTable, binary",
			"ivo://ivoa.net/std/TAPRegExt#output-votable-binary"),
	"votable": 
		("votable", base.votableType, "VOTable, binary",
			"ivo://ivoa.net/std/TAPRegEXT#output-votable-binary"),
	"application/x-votable+xml;serialization=binary2": 
		("votableb2", "application/x-votable+xml;serialization=binary2", 
			"VOTable, new binary", 
			"ivo://ivoa.net/std/TAPRegExt#output-votable-binary2"),
	"votable/b2": 
		("votableb2", "application/x-votable+xml;serialization=binary2", 
			"VOTable, new binary", 
			"ivo://ivoa.net/std/TAPRegExt#output-votable-binary2"),
	"application/x-votable+xml;serialization=tabledata":
		("votabletd", "application/x-votable+xml;serialization=tabledata", 
			"VOTable, tabledata",
			"ivo://ivoa.net/std/TAPRegEXT#output-votable-td"),
	"votable/td":
		("votabletd", "application/x-votable+xml;serialization=tabledata", 
			"VOTable, tabledata",
			"ivo://ivoa.net/std/TAPRegEXT#output-votable-td"),
	"text/csv": 
		("csv", "text/csv", "CSV without column labels", None),
	"csv": ("csv_header", "text/csv;header=present", 
			"CSV with column labels", None),
	"text/csv;header=present": 
		("csv_header", "text/csv;header=present",
			"CSV with column labels", None),
	"text/tab-separated-values": 
		("tsv", "text/tab-separated-values", 
			"Tab separated values", None),
	"tsv": 
		("tsv", "text/tab-separated-values", 
			"Tab separated values", None),
	"text/plain": 
		("tsv", "text/plain",
			"Tab separated values", None),
	"application/fits": 
		("fits", "application/fits", "FITS binary table", None),
	"fits":
		("fits", "application/fits", "FITS binary table", None),
	"text/html": 
		("html", "text/html", "HTML table", None),
	"html": 
		("html", "text/html", "HTML table", None),
	"json": 
		("json", "application/json", "JSON", None),
	"application/json": 
		("json", "application/json", "JSON", None),

}


# this is used below in for registry purposes (values are pairs of
# IVOA id and a human-readable label).
SUPPORTED_LANGUAGES = {
	"ADQL": ("ivo://ivoa.net/std/ADQL#v2.0", "ADQL 2.0"),
	"ADQL-2.0": ("ivo://ivoa.net/std/ADQL#v2.0", "ADQL 2.0"),
}


# A list of supported upload methods.  This is only used in the registry
# interface right now.
UPLOAD_METHODS = {
	"upload-inline": "POST inline upload",
	"upload-http": "http URL",
	"upload-https": "https URL",
	"upload-ftp": "ftp URL",
}


class TAPError(uws.UWSError):
	"""here for backward compatibility.

	Deprecated.
	"""


######################## registry interface helpers

def getSupportedLanguages():
	"""returns a list of tuples for the supported languages.

	This is tap.SUPPORTED_LANGUAGES in a format suitable for the
	TAP capabilities element.

	Each tuple is made up of (name, version, description, ivo-id).
	"""
	langs = []
	for fullName, (ivoId,descr) in SUPPORTED_LANGUAGES.iteritems():
		try:
			name, version = fullName.split("-", 1)
		except ValueError: 
			# fullName has no version info, there must be at least one entry
			# that includes a version, so skip this one.
			continue
		langs.append((name, version, descr, ivoId))
	return langs


def getSupportedOutputFormats():
	"""yields tuples for the supported output formats.

	This is tap.OUTPUT_FORMATS in a format suitable for the
	TAP capabilities element.

	Each tuple is made up of (mime, aliases, description, ivoId).
	"""
	codes, descrs, ivoIds = {}, {}, {}
	for code, (_, outputMime, descr, ivoId) in FORMAT_CODES.iteritems():
		codes.setdefault(outputMime, set()).add(code)
		descrs[outputMime] = descr
		ivoIds[outputMime] = ivoId
	for mime in codes:
		# mime never is an alias of itself
		codes[mime].discard(mime)
		yield mime, codes[mime], descrs[mime], ivoIds[mime]


######################## maintaining TAP schema

def publishToTAP(rd, connection):
	"""publishes info for all ADQL-enabled tables of rd to the TAP_SCHEMA.
	"""
	# first check if we have any adql tables at all, and don't attempt
	# anything if we don't (this is cheap optimizing and keeps TAP_SCHEMA
	# from being created on systems that don't do ADQL.
	for table in rd.tables:
		if table.adql:
			break
	else:
		return
	tapRD = base.caches.getRD(RD_ID)
	for ddId in ["importTablesFromRD", "importColumnsFromRD", 
			"importFkeysFromRD", "importGroupsFromRD"]:
		dd = tapRD.getById(ddId)
		rsc.makeData(dd, forceSource=rd, parseOptions=rsc.parseValidating,
			connection=connection)


def unpublishFromTAP(rd, connection):
	"""removes all information originating from rd from TAP_SCHEMA.
	"""
	rd.setProperty("moribund", "True") # the embedded grammar take this
	                                   # to mean "kill this"
	publishToTAP(rd, connection)
	rd.clearProperty("moribund")


def getAccessibleTables():
	"""returns a list of qualified table names for the TAP-published tables.
	"""
	tapRD = base.caches.getRD(RD_ID)
	td = tapRD.getById("tables")
	table = rsc.TableForDef(td)
	res = [r["table_name"] for r in 
		table.iterQuery([td.getColumnByName("table_name")], "",
			limits=("order by table_name", {}))]
	table.close()
	return res


########################## Maintaining TAP jobs


class TAPTransitions(uws.ProcessBasedUWSTransitions):
	"""The transition function for TAP jobs.

	There's a hack here: After each transition, when you've released
	your lock on the job, call checkProcessQueue (in reality, only
	PhaseAction does this).
	"""
	def __init__(self):
		uws.SimpleUWSTransitions.__init__(self, "TAP")

	def getCommandLine(self, wjob):
		return "gavo", ["gavo", "tap", "--", str(wjob.jobId)]

	def queueJob(self, newState, wjob, ignored):
		"""puts a job on the queue.
		"""
		uws.SimpleUWSTransitions.queueJob(self, newState, wjob, ignored)
		wjob.uws.scheduleProcessQueueCheck()

	def errorOutJob(self, newPhase, wjob, ignored):
		uws.SimpleUWSTransitions.errorOutJob(self, newPhase, wjob, ignored)
		wjob.uws.scheduleProcessQueueCheck()

	def completeJob(self, newPhase, wjob, ignored):
		uws.SimpleUWSTransitions.completeJob(self, newPhase, wjob, ignored)
		wjob.uws.scheduleProcessQueueCheck()

	def killJob(self, newPhase, wjob, ignored):
		try:
			uws.ProcessBasedUWSTransitions.killJob(self, newPhase, wjob, ignored)
		finally:
			wjob.uws.scheduleProcessQueueCheck()


########################## The TAP UWS job


@utils.memoized
def getUploadGrammar():
	from gavo.imp.pyparsing import (Word, ZeroOrMore, Suppress, StringEnd,
		alphas, alphanums, CharsNotIn)
	# Should we allow more tableNames?
	with utils.pyparsingWhitechars(" \t"):
		tableName = Word( alphas+"_", alphanums+"_" )
		# What should we allow/forbid in terms of URIs?
		uri = CharsNotIn(" ;,")
		uploadSpec = tableName("name") + "," + uri("uri")
		uploads = uploadSpec + ZeroOrMore(
			Suppress(";") + uploadSpec) + StringEnd()
		uploadSpec.addParseAction(lambda s,p,t: (t["name"], t["uri"]))
		return uploads


def parseUploadString(uploadString):
	"""iterates over pairs of tableName, uploadSource from a TAP upload string.
	"""
	try:
		res = utils.pyparseString(getUploadGrammar(), uploadString).asList()
		return res
	except ParseException, ex:
		raise base.ValidationError(
			"Syntax error in UPLOAD parameter (near %s)"%(ex.loc), "UPLOAD",
			hint="Note that we only allow regular SQL identifiers as table names,"
				" i.e., basically only alphanumerics are allowed.")


class LangParameter(uws.JobParameter):
	@classmethod
	def addPar(cls, name, value, job):
		if value not in SUPPORTED_LANGUAGES:
			raise base.ValidationError("This service does not support the"
				" query language %s"%value, "LANG")
		uws.JobParameter.updatePar(name, value, job)


class MaxrecParameter(uws.JobParameter):
	name = "MAXREC"
	_serialize, _deserialize = str, int


class LocalFile(object):
	"""A sentinel class representing a file within a job work directory
	(as resulting from an upload).
	"""
	def __init__(self, jobId, wd, fileName):
		self.jobId, self.fileName = jobId, fileName
		self.fullPath = os.path.join(wd, fileName)

	def __str__(self):
		# stringify to a URL for easy UPLOAD string generation.
		# This smells of a bad idea.  If you change it, change UPLOAD.getParam.
		return self.getURL()

	def getURL(self):
		"""returns the URL the file is retrievable under for the life time of
		the job.
		"""
		return base.caches.getRD(RD_ID).getById("run").getURL("tap",
			absolute=True)+"/async/%s/results/%s"%(
				self.jobId,
				self.fileName)


class UploadParameter(uws.JobParameter):
# the way this is specified, inline uploads are quite tricky. 
# To obtain the data, we must access the request, which we don't have
# here.  So, I just grab in from upstack (which of course is bound
# to fail if we're not being called from within a proper web request).
# It's not pretty, but then this kind of interdependency between
# HTTP parameters sucks whatever you do.
#
# We assume uploads come in the request's special files dictionary.
# This is created in taprender.TAPRenderer.gatherUploadFiles.

	_deserialize, _serialize = utils.identity, utils.identity

	@classmethod
	def addPar(cls, name, value, job):
		if not value.strip():
			return
		newUploads = []
		for tableName, upload in parseUploadString(value):
			if upload.startswith("param:"):
				newUploads.append(
					(tableName, cls._saveUpload(job, upload[6:])))
			else:
				newUploads.append((tableName, upload))
		newVal = job.parameters.get(name, [])+newUploads
		uws.JobParameter.updatePar(name, newVal, job)

	@classmethod
	def getPar(cls, name, job):
		return ";".join("%s,%s"%p for p in job.parameters["upload"])

	@classmethod
	def _cleanName(cls, rawName):
		# returns a name hopefully suitable for the file system
		return rawName.encode("quoted-printable").replace('/', "=2F")

	@classmethod
	def _saveUpload(cls, job, uploadName):
		try:
			uploadData = codetricks.stealVar("request").files[uploadName]
		except KeyError:
			raise base.ui.logOldExc(
				base.ValidationError("No upload '%s' found"%uploadName, "UPLOAD"))

		destFName = cls._cleanName(uploadData.filename)
		with job.openFile(destFName, "w") as f:
			f.write(uploadData.file.read())
		return LocalFile(job.jobId, job.getWD(), destFName)


class TAPJob(uws.UWSJobWithWD):
	_jobsTDId = "//tap#tapjobs"
	_transitions = TAPTransitions()

	_parameter_maxrec = MaxrecParameter
	_parameter_lang = LangParameter
	_parameter_upload = UploadParameter

	@property
	def quote(self):
		"""returns an estimation of the job completion.

		This currently is very naive: we give each job that's going to run
		before this one 10 minutes.

		This method needs to be changed when the dequeueing algorithm
		is changed.
		"""
		with base.getTableConn() as conn:
			nBefore = self.uws.runCanned('countQueuedBefore',
				{'dt': self.destructionTime}, conn)[0]["count"]
		return datetime.datetime.utcnow()+nBefore*EST_TIME_PER_JOB



#################### The TAP worker system

from gavo.utils.stanxml import Element, registerPrefix, schemaURL

class Plan(object):
	"""A container for the XML namespace for query plans.
	"""
	class PlanElement(Element):
		_prefix = "plan"
		_mayBeEmpty = True
	
	class plan(PlanElement): pass
	class operation(PlanElement): pass
	class query(PlanElement): pass
	class min(PlanElement): pass
	class max(PlanElement): pass
	class value(PlanElement): pass
	class description(PlanElement): pass
	class rows(PlanElement): pass
	class cost(PlanElement): pass


registerPrefix("plan", "http://docs.g-vo.org/std/TAPPlan.xsd",
	schemaURL("TAPPlan.xsd"))


class PlanAction(uwsactions.JobAction):
	"""retrieve a query plan.

	This is actually a TAP action; as we add UWSes, we'll need to think
	about how we can customize uwsactions my UWS type.
	"""
	name = "plan"

	def _formatRange(self, data):
		if data is None:
			return
		elif isinstance(data, tuple):
			yield Plan.min[str(data[0])]
			yield Plan.max[str(data[1])]
		else:
			yield Plan.value[str(data)]

	def _makePlanDoc(self, planTree, query):
		def recurse(node):
			(opName, attrs), children = node[:2], node[2:]
			res = Plan.operation()[
				Plan.description[opName],
				Plan.rows[self._formatRange(attrs.get("rows"))],
				Plan.cost[self._formatRange(attrs.get("cost"))]]
			for child in children:
				res[recurse(child)]
			return res
		return Plan.plan[
			Plan.query[query],
			recurse(planTree)]

	def doGET(self, job, request):
		from gavo.protocols import taprunner
		qTable = taprunner.getQTableFromJob(job.parameters,
			job.jobId, "untrustedquery", 1)
		request.setHeader("content-type", "text/xml")
		plan = qTable.getPlan()
		return stanxml.xmlrender(
			self._makePlanDoc(plan, qTable.query),
			"<?xml-stylesheet "
				"href='/static/xsl/plan-to-html.xsl' type='text/xsl'?>")


class TAPUWS(uws.UWS):
	# processQueueDirty is set by TAPTransitions whenever it's likely
	# QUEUED jobs could be promoted to executing.
	_processQueueDirty = False
	_baseURLCache = None

	joblistPreamble = ("<?xml-stylesheet href='/static"
		"/xsl/tap-joblist-to-html.xsl' type='text/xsl'?>")
	jobdocPreamble = ("<?xml-stylesheet href='/static/xsl/"
		"tap-job-to-html.xsl' type='text/xsl'?>")

	def __init__(self):
		# processQueue shouldn't need a lock, but it's wasteful to
		# run more unqueuers, so we only run one at a time.
		self._processQueueLock = threading.Lock()
		uws.UWS.__init__(self, TAPJob, uwsactions.JobActions(
			PlanAction))

	def _makeMoreStatements(self, statements, jobsTable):
		td = jobsTable.tableDef

		countField = base.makeStruct(
			svcs.OutputField, name="count", type="integer", select="count(*)")

		statements["countQueuedBefore"] = jobsTable.getQuery(
			[countField],
			"phase='QUEUED' and destructionTime<=%(dt)s",
			{"dt": None})

		statements["getIdsScheduledNext"] = jobsTable.getQuery(
			[jobsTable.tableDef.getColumnByName("jobId")],
			"phase='QUEUED'",
			limits=('ORDER BY destructionTime ASC', {}))

		statements["getHungCandidates"] = jobsTable.getQuery([
			td.getColumnByName("jobId"),
			td.getColumnByName("pid")],
			"phase='EXECUTING'")

	def scheduleProcessQueueCheck(self):
		"""tells the TAP UWS to try and dequeue jobs next time checkProcessQueue
		is called.

		This function exists since during the TAPTransistions there's
		a writable job and processing the queue might deadlock.  So, rather
		than processing right away, we just note something may need to be
		done.
		"""
		self._processQueueDirty = True

	def checkProcessQueue(self):
		"""sees if any QUEUED process can be made EXECUTING.

		This must be called while you're not holding any changeableJob.
		"""
		if self._processQueueDirty:
			self._processQueueDirty = False
			self._processQueue()

	def _processQueue(self):
		"""tries to take jobs from the queue.

		This function is called from checkProcessQueue when we think
		from EXECUTING so somewhere else.

		Currently, the jobs with the earliest destructionTime are processed
		first.  That's, of course, completely ad-hoc.
		"""
		if not self._processQueueLock.acquire(False):
			# There's already an unqueuer running, don't need a second one
			# Note that other processes (taprunner!) might still be manipulating
			# the jobs table, so don't rely on the tables not changing here.
			return
		else:
			try:
				if self.countQueuedJobs()==0:
					return
				runcountGoal = base.getConfig("async", "maxTAPRunning")

				try:
					started = 0
					with base.getTableConn() as conn:
						toStart = [row["jobId"] for row in
							self.runCanned('getIdsScheduledNext', {}, conn)]
					while toStart:
						if self.countRunningJobs()>=runcountGoal:
							break
						self.changeToPhase(toStart.pop(0), uws.EXECUTING)
						started += 1
					
					if started==0:
						# No jobs could be started.  This may be fine when long-runnning
						# jobs  block job submission, but for catastrophic taprunner
						# failures we want to make sure all jobs we think are executing
						# actually are.  If they've silently died, we log that and
						# push them to error.
						# We only want to do that if we're the server -- any other
						# process couldn't see the pids anyway.
						if base.IS_DACHS_SERVER:
							self._ensureJobsAreRunning()
				except Exception:
					base.ui.notifyError("Error during queue processing, TAP"
						" is probably botched now.")
			finally:
				self._processQueueLock.release()

	def _ensureJobsAreRunning(self):
		"""pushes all executing jobs that silently died to ERROR.
		"""
		with base.getTableConn() as conn:
			for row in self.runCanned("getHungCandidates", {}, conn):
				jobId, pid = row["jobId"], row["pid"]

				if pid is None:
					self.changeToPhase(jobId, "ERROR",
						uws.UWSError("EXECUTING job %s had no pid."%jobId, jobId))
					base.ui.notifyError("Stillborn taprunner %s"%jobId)
				else:
					pass
# We should be checking if the process is still running.  Alas,
# there's serious syncing issues here that need to be investigated.
# Let's rely on the taprunners cleaning up behind themselves.
#					try:
#						os.waitpid(pid, os.WNOHANG)
#					except os.error, ex: # child presumably is dead
#						# the following doesn't hurt if the job has gone to COMPLETED
#						# in the meantime -- we don't transition *from* COMPLETED.
#						self.changeToPhase(jobId, "ERROR",
#							uws.UWSError("EXECUTING job %s has silently died."%jobId, jobId))
#						base.ui.notifyError("Zombie taprunner: %s"%jobId)
	
	def changeToPhase(self, jobId, newPhase, input=None, timeout=10):
		"""overridden here to hook in queue management.
		"""
		uws.UWS.changeToPhase(self, jobId, newPhase, input, timeout)
		self.checkProcessQueue()

	def getParamsFromRequest(self, wjob, request, service):
		"""Feeds parameters from request into wjob.

		We assume uwsactions.lowercaseProtocolArgs has already been applied
		to request.args.

		For now everything in args, including protocol arguments, is stuffed 
		into parameters; the only real UWS parameter we may want to look at 
		is PHASE for when the job is to be queued immediately.
		"""
		for key, valueList in request.args.iteritems():
			if valueList:
				# TODO: deal with possible list-valued parameters.
				wjob.setSerializedPar(key, valueList[0])

	@property
	def baseURL(self):
		if self._baseURLCache is None:
			self._baseURLCache = base.caches.getRD(
				RD_ID).getById("run").getURL("tap")
		return self._baseURLCache

	def getURLForId(self, jobId):
		"""returns a fully qualified URL for the job with jobId.
		"""
		return "%s/%s/%s"%(self.baseURL, "async", jobId)

WORKER_SYSTEM = TAPUWS()
# TODO: deprecated name, fix this and delete the alias
workerSystem = WORKER_SYSTEM
