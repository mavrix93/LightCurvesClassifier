"""
Structure definition of resource descriptors.

The stuff they are describing is not a resource in the VO sense (whatever
that is) or in the Dublin Core sense, but simply stuff held together
by common metadata.  If it's got the same creator, the same base title,
the same keywords, etc., it's described by one RD.

In the DaCHS, a resource descriptor typically sets up a schema in
the database.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import datetime
import grp
import os
import pkg_resources
import time
import threading
import weakref

from gavo import base
from gavo import registry
from gavo import rscdef
from gavo import svcs
from gavo import utils
from gavo.rscdef import common
from gavo.rscdef import regtest
from gavo.rscdef import scripting
from gavo.rscdef import executing


class RD(base.Structure, base.ComputedMetaMixin, scripting.ScriptingMixin,
		base.StandardMacroMixin, common.PrivilegesMixin, registry.DateUpdatedMixin):
	"""A resource descriptor (RD); the root for all elements described here.
	
	RDs collect all information about how to parse a particular source (like a
	collection of FITS images, a catalogue, or whatever), about the database
	tables the data ends up in, and the services used to access them.
	"""
	name_ = "resource"

	_resdir = base.FunctionRelativePathAttribute("resdir", 
		default=None, 
		baseFunction=lambda instance: base.getConfig("inputsDir"),
		description="Base directory for source files and everything else"
			" belonging to the resource.", 
		copyable=True)

	_schema = base.UnicodeAttribute("schema", 
		default=base.Undefined,
		description="Database schema for tables defined here.  Follow the rule"
		" 'one schema, one RD' if at all possible.  If two RDs share the same"
		" schema, the must generate exactly the same permissions for that"
		" schema; this means, in particular, that if one has an ADQL-published"
		" table, so must the other.  In a nutshell: one schema, one RD.",
		copyable=True,
		callbacks=["_inferResdir"])

	_dds = base.StructListAttribute("dds", 
		childFactory=rscdef.DataDescriptor,
		description="Descriptors for the data generated and/or published"
		" within this resource.", 
		copyable=True, 
		before="outputTables")

	_tables = base.StructListAttribute("tables",
		childFactory=rscdef.TableDef, 
		description="A table used or created by this resource", 
		copyable=True, 
		before="dds")

	_outputTables = base.StructListAttribute("outputTables",
		childFactory=svcs.OutputTableDef, 
		description="Canned output tables for later reference.", 
		copyable=True)

	_rowmakers = base.StructListAttribute("rowmakers",
		childFactory=rscdef.RowmakerDef, 
		description="Transformations for going from grammars to tables."
			" If specified in the RD, they must be referenced from make"
			" elements to become active.",
		copyable=True, 
		before="dds")

	_procDefs = base.StructListAttribute("procDefs", 
		childFactory=rscdef.ProcDef,
		description="Procedure definintions (rowgens, rowmaker applys)",
		copyable=True, before="rowmakers")

	_condDescs = base.StructListAttribute("condDescs", 
		childFactory=svcs.CondDesc,
		description="Global condition descriptors for later reference", 
		copyable=True, 
		before="cores")

	_resRecs = base.StructListAttribute("resRecs",
		childFactory=registry.ResRec,
		description="Non-service resources for the IVOA registry.  They will"
			" be published when gavo publish is run on the RD.")

	_services = base.StructListAttribute("services", 
		childFactory=svcs.Service, 
		description="Services exposing data from this resource.", 
		copyable=True)

	_macDefs = base.MacDefAttribute(before="tables", 
		description="User-defined macros available on this RD")

	_mixinDefs = base.StructListAttribute("mixdefs",
		childFactory=rscdef.MixinDef,
		description="Mixin definitions (usually not for users)")

	_require = base.ActionAttribute("require", 
		methodName="importModule",
		description="Import the named gavo module (for when you need something"
		" registred)")

	_cores = base.MultiStructListAttribute("cores", 
		childFactory=svcs.getCore, 
		childNames=svcs.CORE_REGISTRY.keys(),
		description="Cores available in this resource.", copyable=True,
		before="services")

	_jobs = base.StructListAttribute("jobs",
		childFactory=executing.Execute,
		description="Jobs to be run while this RD is active.")

	_tests = base.StructListAttribute("tests",
		childFactory=regtest.RegTestSuite,
		description="Suites of regression tests connected to this RD.")

	# These replace themselves with expanded tables
	_viewDefs = base.StructAttribute("simpleView",
		childFactory=rscdef.SimpleView, 
		description="Definitions of views created from natural joins", 
		default=None)

	_properties = base.PropertyAttribute()

	def __init__(self, srcId, **kwargs):
		# RDs never have parents, so contrary to all other structures they
		# are constructed with with a srcId instead of a parent.  You
		# *can* have that None, but such RDs cannot be used to create
		# non-temporary tables, services, etc, since the srcId is used
		# in the construction of identifiers and such.
		self.sourceId = srcId
		base.Structure.__init__(self, None, **kwargs)
		# The rd attribute is a weakref on self.  Always.  So, this is the class
		# that roots common.RDAttributes
		self.rd = weakref.proxy(self)
		# real dateUpdated is set by getRD, this is just for RDs created
		# on the fly.
		self.dateUpdated = datetime.datetime.utcnow()
		# if an RD is parsed from a disk file, this gets set to its path
		# by getRD below
		self.srcPath = None
		# this is for modified-since and friends.
		self.loadedAt = time.time()
		# keep track of RDs depending on us for the registry code
		# (only read this)
		self.rdDependencies = set()

	def __iter__(self):
		return iter(self.dds)

	def __repr__(self):
		return "<resource descriptor for %s>"%self.sourceId

	def isDirty(self):
		"""returns true if the RD on disk has a timestamp newer than
		loadedAt.
		"""
		if isinstance(self.srcPath, PkgResourcePath):
			# stuff from the resource package should not change underneath us.
			return False

		try:
			if self.srcPath is not None:
				return os.path.getmtime(self.srcPath)>self.loadedAt
		except os.error:
			# this will ususally mean the file went away
			return True
		return False

	def importModule(self, ctx):
		# this is a callback for the require attribute
		utils.loadInternalObject(self.require, "__doc__")

	def onElementComplete(self):
		for table in self.tables:
			self.readProfiles = self.readProfiles | table.readProfiles
			table.setMetaParent(self)

		self.serviceIndex = {}
		for svc in self.services:
			self.serviceIndex[svc.id] = svc
			svc.setMetaParent(self)

		for dd in self.dds:
			dd.setMetaParent(self)

		if self.resdir and not os.path.isdir(self.resdir):
			base.ui.notifyWarning("RD %s: resource directory '%s' does not exist"%(
				self.sourceId, self.resdir))

		self._onElementCompleteNext(RD)

	def _inferResdir(self, value):
		if self.resdir is None:
			self._resdir.feedObject(self, value)

	def iterDDs(self):
		return iter(self.dds)

	def getService(self, id):
		return self.serviceIndex.get(id, None)

	def getTableDefById(self, id):
		return self.getById(id, rscdef.TableDef)
	
	def getDataDescById(self, id):
		return self.getById(id, rscdef.DataDescriptor)
	
	def getById(self, id, forceType=None):
		try:
			res = self.idmap[id]
		except KeyError:
			raise base.NotFoundError(
				id, "Element with id", "RD %s"%(self.sourceId))
		if forceType:
			if not isinstance(res, forceType):
				raise base.StructureError("Element with id '%s' is not a %s"%(
					id, forceType.__name__))
		return res

	def getAbsPath(self, relPath):
		"""returns the absolute path for a resdir-relative relPath.
		"""
		return os.path.join(self.resdir, relPath)

	def openRes(self, relPath, mode="r"):
		"""returns a file object for relPath within self's resdir.

		Deprecated.  This is going to go away, use getAbsPath and a context 
		manager.
		"""
		return open(self.getAbsPath(relPath), mode)

	def getTimestampPath(self):
		"""returns a path to a file that's accessed by Resource each time 
		a bit of the described resource is written to the db.
		"""
		return os.path.join(base.getConfig("stateDir"), "updated_"+
			self.sourceId.replace("/", "+"))

	def touchTimestamp(self):
		"""updates the timestamp on the rd's state file.
		"""
		fn = self.getTimestampPath()
		try:
			try: 
				os.unlink(fn)
			except os.error: 
				pass
			f = open(fn, "w")
			f.close()
			os.chmod(fn, 0664)
			try:
				os.chown(fn, -1, grp.getgrnam(base.getConfig("GavoGroup")[2]))
			except (KeyError, os.error):
				pass
		except (os.error, IOError):
			base.ui.notifyWarning(
				"Could not update timestamp on RD %s"%self.sourceId)

	def _computeIdmap(self):
		res = {}
		for child in self.iterChildren():
			if hasattr(child, "id"):
				res[child.id] = child
		return res

	def addDependency(self, rd, prereq):
		"""declares that rd needs the RD prereq to properly work.

		This is used in the generation of resource records to ensure that, e.g.
		registred data have added their served-bys to the service resources.
		"""
		if rd.sourceId!=prereq.sourceId:
			self.rdDependencies.add((rd.sourceId, prereq.sourceId))

	def copy(self, parent):
		base.ui.notifyWarning("Copying an RD -- this may not be a good idea")
		new = base.Structure.copy(self, parent)
		new.idmap = new._computeIdmap()
		new.sourceId = self.sourceId
		return new

	def invalidate(self):
		"""make the RD fail on every attribute read.

		See rscdesc._loadRDIntoCache for why we want this.
		"""
		errMsg = ("Loading of %s failed in another thread; this RD cannot"
			" be used here")%self.sourceId

		class BrokenClass(object):
			"""A class that reacts to all attribute requests with a some exception.
			"""
			def __getattribute__(self, attributeName):
				raise base.ReportableError(errMsg)

		self.__class__ = BrokenClass

	def macro_RSTccby(self, stuffDesignation):
		"""expands to a declaration that stuffDesignation is available under
		CC-BY.
		
		This only works in reStructured text (though it's still almost
		readable as source).
		"""
		return ("%s is licensed under the `Creative Commons Attribution 3.0"
			" License <http://creativecommons.org/licenses/by/3.0/>`_\n\n"
			".. image:: /static/img/ccby.png\n\n"
			)%stuffDesignation


class RDParseContext(base.ParseContext):
	"""is a parse context for RDs.

	It defines a couple of attributes that structures can ask for (however,
	it's good practice not to rely on their presence in case someone wants
	to parse XML snippets with a standard parse context, so use 
	getattr(ctx, "doQueries", True) or somesuch.
	"""
	def __init__(self, forImport=False, doQueries=True, dumpTracebacks=False, 
			restricted=False, forRD=None):
		self.forImport, self.doQueries = forImport, doQueries
		self.dumpTracebacks = dumpTracebacks
		base.ParseContext.__init__(self, restricted, forRD)


class PkgResourcePath(str):
	"""A sentinel class used to mark an RD as coming from pkg_resources.
	"""
	def __str__(self):
		return self


def canonicalizeRDId(srcId):
	"""returns a standard rd id for srcId.

	srcId may be a file system path, or it may be an "id".  The canonical
	basically is "inputs-relative path without .rd extension".  Everything
	that's not within inputs or doesn't end with .rd is handed through.
	// is expanded to __system__/.  The path to built-in RDs,
	/resources/inputs, is treated analoguous to inputsDir.

	TODO: We should probably reject everything that's neither below inputs
	nor below resources.
	"""
	if srcId.startswith("//"):
		srcId = "__system__"+srcId[1:]

	for inputsDir in (base.getConfig("inputsDir"), "/resources/inputs"):
		if srcId.startswith(inputsDir):
			srcId = srcId[len(inputsDir):].lstrip("/")
	
	if srcId.endswith(".rd"):
		srcId = srcId[:-3]

	return srcId


def _getFilenamesForId(srcId):
	"""helps getRDInputStream by iterating over possible files for srcId.
	"""
	if srcId.startswith("/"):
		yield srcId+".rd"
		yield srcId
	else:
		inputsDir = base.getConfig("inputsDir")
		yield os.path.join(inputsDir, srcId)+".rd"
		yield os.path.join(inputsDir, srcId)
		yield "/resources/inputs/%s.rd"%srcId
		yield "/resources/inputs/%s"%srcId


def getRDInputStream(srcId):
	"""returns a read-open stream for the XML source of the resource
	descriptor with srcId.

	srcId is already normalized; that means that absolute paths must
	point to a file (sans possibly .rd), relative paths are relative
	to inputsDir or pkg_resources(/resources/inputs).

	This function prefers files with .rd to those without, and
	inputsDir to pkg_resources (the latter allowing the user to
	override built-in system RDs).
	"""
	for fName in _getFilenamesForId(srcId):
		if os.path.isfile(fName):
			return fName, open(fName)
		if (pkg_resources.resource_exists('gavo', fName)
				and not pkg_resources.resource_isdir('gavo', fName)):
			return (PkgResourcePath(fName), 
				pkg_resources.resource_stream('gavo', fName))
	raise base.RDNotFound(srcId)


def setRDDateTime(rd, inputFile):
	"""guesses a date the resource was updated.

	This uses either the timestamp on inputFile or the rd's import timestamp,
	whatever is newer.
	"""
# this would look better as a method on RD, and maybe it would be cool
# to just try to infer the inputFile from the ID?
	rdTimestamp = utils.fgetmtime(inputFile)
	try:
		dataTimestamp = os.path.getmtime(rd.getTimestampPath())
	except os.error: # no timestamp yet
		dataTimestamp = rdTimestamp
	rd.timestampUpdated = max(dataTimestamp, rdTimestamp)
	rd.dateUpdated = datetime.datetime.utcfromtimestamp(
		rd.timestampUpdated)


USERCONFIG_RD_PATH = os.path.join(base.getConfig("configDir"), "userconfig")


class _UserConfigFakeRD(object):
	"""A fake object that's in the RD cache as "%".

	This is used by the id resolvers in parsecontext; this certainly is
	of no use as an RD otherwise.
	"""

	def getRealRD(self):
		return base.caches.getRD(USERCONFIG_RD_PATH)

	def getById(self, id, forceType=None):
		"""returns an item from userconfig.

		This first tries to resolve id in gavo/etc/userconfig.rd, then in the
		fallback //userconfig.rd.
		"""
		try:
			try:
				return base.caches.getRD(
					os.path.join(base.getConfig("configDir"), "userconfig.rd")
					).getById(id, forceType=forceType)
			except base.NotFoundError:
				pass
			except Exception, msg:
				base.ui.notifyError("Bad userconfig: (%s), ignoring it.  Run"
					" 'gavo val %%' to see actual errors."%repr(msg))

			return base.caches.getRD("//userconfig"
				).getById(id, forceType=forceType)
		except base.NotFoundError:
			raise base.NotFoundError(id, "Element with id", 
				"etc/userconfig.rd")


def getRD(srcId, forImport=False, doQueries=True, 
		dumpTracebacks=False, restricted=False, useRD=None):
	"""returns a ResourceDescriptor for srcId.

	srcId is something like an input-relative path; you'll generally
	omit the extension (unless it's not the standard .rd).

	getRD furnishes the resulting RD with an idmap attribute containing
	the mapping from id to object collected by the parse context.

	The useRD parameter is for _loadRDIntoCache exclusively and is
	used by it internally.  It is strictly an ugly implementation detail.
	"""
	if srcId=='%':
		return _UserConfigFakeRD()

	if useRD is None:
		rd = RD(canonicalizeRDId(srcId))
	else:
		rd = useRD

	srcPath, inputFile = getRDInputStream(rd.sourceId)
	context = RDParseContext(forImport, doQueries, dumpTracebacks, restricted)

	if not isinstance(srcPath, PkgResourcePath):
		srcPath = os.path.abspath(srcPath)
	rd.srcPath = context.srcPath = srcPath
	context.forRD = rd.sourceId
	rd.idmap = context.idmap

	try:
		rd = base.parseFromStream(rd, inputFile, context=context)
	except Exception, ex:
		ex.srcPath = srcPath
		raise
	setRDDateTime(rd, inputFile)
	return rd


# in _currentlyParsing, getRD keeps track of what RDs are currently being
# parsed.  The keys are the canonical sourceIds, the values are pairs of
# an unfinished RD and RLocks protecting it.
_currentlyParsingLock = threading.Lock()
_currentlyParsing = {}
import threading


class CachedException(object):
	"""An exception that occurred while parsing an RD.

	This will remain in the cache until the underlying RD is changed.
	"""
	def __init__(self, exception, sourcePath):
		self.exception = exception
		self.sourcePath = sourcePath
		# this can race a bit in that we won't catch saves done between
		# we started parsing and we came up with the exception, but
		# these are easy to fix by saving again, so we won't bother.
		try:
			self.timestamp = os.path.getmtime(self.sourcePath)
		except (TypeError, os.error):
			# If there's no file at all, or the file doesn't exist, never
			# dirty the exception
			self.sourcePath = None
	
	def isDirty(self):
		if self.sourcePath is None:
			# see above
			return False
		if not os.path.exists(self.sourcePath): 
			# someone has removed the file, kill cache
			return True
		return os.path.getmtime(self.sourcePath)>self.timestamp
	
	def raiseAgain(self):
		# XXX TODO: do we want to fix the traceback here?
		raise self.exception


def _loadRDIntoCache(canonicalRDId, cacheDict):
	"""helps _makeRDCache.

	This function contains the locking logic that makes sure multiple
	threads can load RDs.
	"""
	with _currentlyParsingLock:
		if canonicalRDId in _currentlyParsing:
			lock, rd = _currentlyParsing[canonicalRDId]
			justWait = True
		else:
			lock, rd = threading.RLock(), RD(canonicalRDId)
			_currentlyParsing[canonicalRDId] = lock, rd
			justWait = False

	if justWait:
		# Someone else is already parsing.  If it's the current thread,
		# go on (lock is an RLock!) so we can resolve circular references
		# (as long as they are backward references).  All other threads
		# just wait for the parsing thread to finish
		lock.acquire()
		lock.release()
		return rd

	lock.acquire()
	try:
		try:
			cacheDict[canonicalRDId] = getRD(canonicalRDId, useRD=rd)
		except Exception, ex:
			# Importing failed, invalidate the RD (in case other threads still
			# see it from _currentlyParsing)
			cacheDict[canonicalRDId] = CachedException(ex, 
				getattr(rd, "srcPath", None))
			rd.invalidate()
			raise
	finally:
		del _currentlyParsing[canonicalRDId]
		lock.release()
	return cacheDict[canonicalRDId]


def _makeRDCache():
	"""installs the cache for RDs.

	One trick here is to handle "aliasing", i.e. making sure that
	you get identical objects regardless of whether you request
	__system__/adql.rd, __system__/adql, or //adql.

	Then, we're checking for "dirty" RDs (i.e., those that should
	be reloaded).

	The messiest part is the support for getting RDs in the presence of
	threads while still supporting recursive references, though.
	"""
# TODO: Maybe unify this again with caches._makeCache?  That stuff could
# do with a facility to invalidate cached entries, too.
	rdCache = {}

	def getRDCached(srcId, **kwargs):
		if kwargs:
			return getRD(srcId, **kwargs)
		srcId = canonicalizeRDId(srcId)

		if (srcId in rdCache 
				and getattr(rdCache[srcId], "isDirty", lambda: False)()):
			base.caches.clearForName(srcId)

		try:
			cachedOb = rdCache[srcId]
			if isinstance(cachedOb, CachedException):
				cachedOb.raiseAgain()
			else:
				return cachedOb
		except KeyError:
			return _loadRDIntoCache(srcId, rdCache)

	getRDCached.cacheCopy = rdCache
	base.caches.registerCache("getRD", rdCache, getRDCached)

_makeRDCache()


def openRD(relPath):
	"""returns a (cached) RD for relPath.

	relPath is first interpreted as a file system path, then as an RD id.
	the first match wins.
	"""
	try:
		return base.caches.getRD(os.path.join(os.getcwd(), relPath), forImport=True)
	except base.RDNotFound:
		return base.caches.getRD(relPath, forImport=True)
