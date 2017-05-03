"""
An abstract processor and some helping code.

Currently, I assume a plain text interface for those.  It might be
a good idea to use the event mechanism here.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from __future__ import with_statement

from cStringIO import StringIO
import os
import sys
import textwrap
import traceback

import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot

import Image

from gavo import base
from gavo import rsc
from gavo import rscdef
from gavo import utils
from gavo.helpers import anet
from gavo.helpers import fitstricks
from gavo.utils import fitstools
from gavo.utils import pyfits


class CannotComputeHeader(Exception):
	"""is raised when no header can be generated (_getHeader returns None).
	"""


class FileProcessor(object):
	"""An abstract base for a source file processor.

	Processors are constructed with an optparse Values instance that
	is later available as the attribute opts.

	You then need to define a process method receiving a source as
	returned by the dd (i.e., usually a file name).

	You can override the method _createAuxillaries(dataDesc) to compute
	things like source catalogues, etc.  Thus, you should not need to
	override the constructor.
	"""
	inputsDir = base.getConfig("inputsDir")

	def __init__(self, opts, dd):
		self.opts, self.dd = opts, dd
		self._createAuxillaries(dd)

	def _createAuxillaries(self, dd):
		pass

	def classify(self, fName):
		return "unknown"

	def process(self, fName):
		pass
	
	def addClassification(self, fName):
		label = self.classify(fName)
		self.reportDict.setdefault(label, []).append(os.path.basename(fName))

	def printTableSize(self):
		try:
			tableName = self.dd.makes[0].table.getQName()
			with base.AdhocQuerier(base.getAdminConn) as q:
				itemsInDB = list(q.query("SELECT count(*) from %s"%tableName))[0][0]
			print "Items currently in assumed database table: %d\n"%itemsInDB
		except (base.DBError, IndexError):
			pass

	def printReport(self, processed, ignored):
		print "\n\nProcessor Report\n================\n"
		if ignored:
			print "Warning: There were %d errors during classification"%ignored
		repData = zip(map(len, self.reportDict.values()), self.reportDict.keys())
		repData.sort()
		print utils.formatSimpleTable(repData)
		print "\n"
		self.printTableSize()

	def printVerboseReport(self, processed, ignored):
		print "\n\nProcessor Report\n================\n"
		if ignored:
			print "Warning: There were %d errors during classification"%ignored
		repData = zip(self.reportDict.values(), self.reportDict.keys())
		repData.sort(key=lambda v: -len(v[0]))
		print "\n%s\n%s\n"%(repData[0][1], "-"*len(repData[0][1]))
		print "%d items\n"%(len(repData[0][0]))
		for items, label in repData[1:]:
			print "\n%s\n%s\n"%(label, "-"*len(label))
			items.sort()
			print "%d items:\n"%(len(items))
			print "\n".join(textwrap.wrap(", ".join(items)))
		print "\n"
		self.printTableSize()

	@staticmethod
	def addOptions(parser):
		parser.add_option("--filter", dest="requireFrag", metavar="STR",
			help="Only process files with names containing STR", default=None)
		parser.add_option("--bail", help="Bail out on a processor error,"
			" dumping a traceback", action="store_true", dest="bailOnError",
			default=False)
		parser.add_option("--report", help="Output a report only",
			action="store_true", dest="doReport", default=False)
		parser.add_option("--verbose", help="Be more talkative",
			action="store_true", dest="beVerbose", default=False)
		parser.add_option("--n-procs", "-j", help="Run NUM processes in"
			" parallel", action="store", dest="nParallel", default=1,
			metavar="NUM", type=int)

	_doneSentinel = ("MAGIC: QUEUE DONE",)

	def iterJobs(self, nParallel):
		"""executes process() in parallel for all sources and iterates 
		over the results.

		We use this rather than multiprocessing's Pool, as that cannot
		call methods.  I'm working around this here.
		"""
		import multiprocessing

		taskQueue = multiprocessing.Queue(nParallel*4)
		doneQueue = multiprocessing.Queue()

		def worker(inQueue, outQueue):
			for srcId in iter(inQueue.get, None):
				if (self.opts.requireFrag is not None 
						and not self.opts.requireFrag in srcId):
					continue

				try:
					outQueue.put(self.process(srcId))
				except base.SkipThis:
					continue
				except Exception, ex:
					ex.source = srcId
					if self.opts.bailOnError:
						traceback.print_exc()
					outQueue.put(ex)
			outQueue.put(self._doneSentinel)

		# create nParallel workers
		activeWorkers = 0
		for i in range(nParallel):
			multiprocessing.Process(target=worker, 
				args=(taskQueue, doneQueue)).start()
			activeWorkers += 1

		# feed them their tasks
		toDo = self.iterIdentifiers()
		while True:
			try:
				taskQueue.put(toDo.next())
			except StopIteration:
				break

			while not doneQueue.empty():
				yield doneQueue.get()

		# ask them to quit and wait until all have said they're quitting
		for i in range(nParallel):
			taskQueue.put(None)
		taskQueue.close()
		while activeWorkers:
			item = doneQueue.get()
			if item==self._doneSentinel:
				activeWorkers -= 1
			else:
				yield item

	def _runProcessor(self, procFunc, nParallel=1):
		"""calls procFunc for all sources in self.dd.

		This is the default, single-tasking implementation.
		"""
		processed, ignored = 0, 0

		if nParallel==1:
			def iterProcResults():
				for source in self.iterIdentifiers():
					if (self.opts.requireFrag is not None 
							and not self.opts.requireFrag in source):
						continue

					try:
						yield procFunc(source)
					except base.SkipThis:
						continue
					except Exception, ex:
						ex.source = source
						if self.opts.bailOnError:
							traceback.print_exc()
						yield ex
			resIter = iterProcResults()
		else:
			resIter = self.iterJobs(nParallel)

		while True:
			try:
				res = resIter.next()
				if isinstance(res, Exception):
					raise res
			except StopIteration:
				break
			except KeyboardInterrupt:
				sys.exit(2)
			except Exception, msg:
				if self.opts.bailOnError:
					sys.exit(1)
				sys.stderr.write("Skipping source %s: (%s, %s)\n"%(
					getattr(msg, "source", "(unknown)"), msg.__class__.__name__, msg))
				ignored += 1
			processed += 1
			sys.stdout.write("%6d (-%5d)\r"%(processed, ignored))
			sys.stdout.flush()
		return processed, ignored

	def iterIdentifiers(self):
		"""iterates over all identifiers that should be processed.

		This is usually the paths of the files to be processed.
		You can, however, override it to do something else if that
		fits your problem (example: Previews in SSA use the accref).
		"""
		return iter(self.dd.sources)

	def processAll(self):
		"""calls the process method of processor for all sources of the data
		descriptor dd.
		"""
		if self.opts.doReport:
			self.reportDict = {}
			procFunc = self.addClassification
		else:
			procFunc = self.process
		processed, ignored = self._runProcessor(procFunc, 
			nParallel=self.opts.nParallel)
		if self.opts.doReport:
			if self.opts.beVerbose:
				self.printVerboseReport(processed, ignored)
			else:
				self.printReport(processed, ignored)
		return processed, ignored

	######### Utility methods

	def getProductKey(self, srcName):
		return utils.getRelativePath(srcName, self.inputsDir)


class HeaderProcessor(FileProcessor):
	"""is an abstract processor for FITS header manipulations.

	The processor builds naked FITS headers alongside the actual files, with an
	added extension .hdr.  The presence of a FITS header indicates that a file
	has been processed.  The headers on the actual FITS files are only replaced
	if necessary.

	The basic flow is: Check if there is a header.  If not, call
	_getNewHeader(srcFile) -> hdr.  Store hdr to cache.  Insert cached
	header in the new FITS if it's not there yet.

	You have to implement the _getHeader(srcName) -> pyfits header object
	function.  It must raise an exception if it cannot come up with a
	header.  You also have to implement _isProcessed(srcName) -> boolean
	returning True if you think srcName already has a processed header.

	This basic flow is influenced by the following opts attributes:

		- reProcess -- even if a cache is present, recompute header values
		- applyHeaders -- actually replace old headers with new headers
		- reHeader -- even if _isProcessed returns True, write a new header
		- compute -- perform computations

	The idea is that you can:

		- generate headers without touching the original files: proc
		- write all cached headers to files that don't have them
			proc --apply --nocompute
		- after a bugfix force all headers to be regenerated:
			proc --reprocess --apply --reheader
	
	All this leads to the messy logic.  Sorry 'bout this.
	"""
	headerExt = ".hdr"
	maxHeaderBlocks = 40

	def _makeCacheName(self, srcName):
		return srcName+self.headerExt

	def _writeCache(self, srcName, hdr):
		dest = self._makeCacheName(srcName)

		# nuke info on sizes that may still lurk; we don't want that in the
		# cache
		hdr = hdr.copy()
		hdr.update("BITPIX", 8)
		hdr.update("NAXIS", 0)
		if hdr.has_key("NAXIS1"):
			del hdr["NAXIS1"]
		if hdr.has_key("NAXIS2"):
			del hdr["NAXIS2"]

		hdr = fitstools.sortHeaders(hdr, commentFilter=self.commentFilter,
			historyFilter=self.historyFilter)

		with open(dest, "w") as f:
			f.write(fitstools.serializeHeader(hdr))
		hdus = pyfits.open(dest)
		hdus.verify()
		hdus.close()

	def _readCache(self, srcName):
		"""returns a pyfits header object for the cached result in srcName.

		If there is no cache, None is returned.
		"""
		src = self._makeCacheName(srcName)
		if os.path.exists(src):
			with open(src) as f:
				hdr = fitstools.readPrimaryHeaderQuick(f, self.maxHeaderBlocks)
			return hdr

	def _makeCache(self, srcName):
		if self.opts.compute:
			if self.opts.beVerbose:
				print "Now computing for", srcName
			hdr = self._getHeader(srcName)
			if hdr is None:
				raise CannotComputeHeader("_getHeader returned None")
			self._writeCache(srcName, hdr)

	# headers copied from original file rather than the cached header
	keepKeys = set(["SIMPLE", "BITPIX", "NAXIS", "NAXIS1", "NAXIS2",
			"EXTEND", "BZERO", "BSCALE"])

	def _fixHeaderDataKeys(self, srcName, header):
		oldHeader = self.getPrimaryHeader(srcName)
		for key in self.keepKeys:
			if oldHeader.has_key(key):
				header.update(key, oldHeader[key])

	def commentFilter(self, value):
		"""returns true if the comment value should be preserved.

		You may want to override this.
		"""
		return True
	
	def historyFilter(self, value):
		"""returns true if the history item value should be preserved.
		"""
		return True

	def _writeHeader(self, srcName, header):
		self._fixHeaderDataKeys(srcName, header)
		header = fitstools.sortHeaders(header, commentFilter=self.commentFilter,
			historyFilter=self.historyFilter)
		fitstools.replacePrimaryHeaderInPlace(srcName, header)

	def _isProcessed(self, srcName):
		"""override.
		"""
		return False

	def _mungeHeader(self, srcName, header):
		"""override this or _getHeader.
		"""
		return header

	def _getHeader(self, srcName):
		"""override this or _mungeHeader.
		"""
		return self._mungeHeader(srcName, self.getPrimaryHeader(srcName))

	@staticmethod
	def getPrimaryHeader(srcName):
		"""returns the primary header of srcName.

		This is a convenience function for user derived classes.
		"""
		f = open(srcName)
		hdr = utils.readPrimaryHeaderQuick(f)
		f.close()
		return hdr

	def process(self, srcName):
		if (not (self.opts.reProcess or self.opts.reHeader)
				and self._isProcessed(srcName)):
			return
		cache = self._readCache(srcName)
		if cache is None or self.opts.reProcess:
			self._makeCache(srcName)
			cache = self._readCache(srcName)
		if cache is None:
			return
		if not self.opts.applyHeaders:
			return
		if self.opts.reHeader or not self._isProcessed(srcName):
			self._writeHeader(srcName, cache)

	@staticmethod
	def addOptions(optParser):
		FileProcessor.addOptions(optParser)
		optParser.add_option("--reprocess", help="Recompute all headers",
			action="store_true", dest="reProcess", default=False)
		optParser.add_option("--no-compute", help="Only use cached headers",
			action="store_false", dest="compute", default=True)
		optParser.add_option("--apply", help="Write cached headers to"
			" source files", action="store_true", dest="applyHeaders",
			default=False)
		optParser.add_option("--reheader", help="Write cached headers"
			" to source files even if it looks like they already have"
			" been written", action="store_true", dest="reHeader",
			default=False)


class AnetHeaderProcessor(HeaderProcessor):
	"""A file processor for calibrating FITS frames using astrometry.net.

	It might provide calibration for "simple" cases out of the box.  You
	will usually want to override some solver parameters.  To do that,
	define class attributes sp_<parameter name>, where the parameters
	available are discussed in helpers.anet's docstring.  sp_indices is
	one thing you will typically need to override.
	
	To use SExtractor rather than anet's source extractor, override
	sexControl, to use an object filter (see anet.getWCSFieldsFor), override
	the objectFilter attribute.

	To add additional fields, override _getHeader and call the parent
	class' _getHeader method.  To change the way astrometry.net is
	called, override the _solveAnet method (it needs to return some
	result anet.of getWCSFieldsFor) and call _runAnet with your
	custom arguments for getWCSFieldsFor.
	"""
	sexControl = None
	objectFilter = None

	noCopyHeaders = set(["simple", "bitpix", "naxis", "imageh", "imagew",
		"naxis1", "naxis2", "datamin", "datamax", "date"])

	@staticmethod
	def addOptions(optParser):
		HeaderProcessor.addOptions(optParser)
		optParser.add_option("--no-anet", help="Do not run anet, fail if"
			" no cache is present to take anet headers from", action="store_false",
			dest="runAnet", default=True)
		optParser.add_option("--copy-to", help="Copy astrometry.net sandbox to"
			" this directory (WARNING: it will be deleted if it exists!)."
			"  Probably most useful with --bail", 
			action="store", dest="copyTo", default=None)

	def _isProcessed(self, srcName):
		return self.getPrimaryHeader(srcName).has_key("CD1_1")

	def _runAnet(self, srcName):
		return anet.getWCSFieldsFor(srcName, self.solverParameters,
			self.sexControl, self.objectFilter, self.opts.copyTo,
			self.opts.beVerbose)

	@property
	def solverParameters(self):
		return dict(
			(n[3:], getattr(self, n)) 
			for n in dir(self) if n.startswith("sp_"))

	def _solveAnet(self, srcName):
		if self.opts.runAnet:
			return self._runAnet(srcName)
		else:
			oldCards = self._readCache(srcName)
			if oldCards is None:
				raise CannotComputeHeader("No cached headers and you asked"
					" not to run astrometry.net")
			return oldCards.ascard

	def _shouldRunAnet(self, srcName, hdr):
		return True

	def _getHeader(self, srcName):
		hdr = self.getPrimaryHeader(srcName)
		if self._shouldRunAnet(srcName, hdr):
			wcsCards = self._solveAnet(srcName)
			if not wcsCards:
				raise CannotComputeHeader("astrometry.net did not"
					" find a solution")
			fitstricks.copyFields(hdr, wcsCards, self.noCopyHeaders)
		return self._mungeHeader(srcName, hdr)

	def commentFilter(self, value):
		return ( "Index name" in value or
			"Cxdx margin" in value or
			"Field scale lower" in value or
			"Field scale upper" in value or
			"Start obj" in value or
			"End obj" in value or
			"Tweak" in value or
			"code error" in value)

	def historyFilter(self, value):
		return ("suite" in value or
			"blind" in value)


class PreviewMaker(FileProcessor):
	def _createAuxillaries(self, dd):
		self.previewDir = dd.rd.getAbsPath(
			dd.getProperty("previewDir"))
		if not os.path.isdir(self.previewDir):
			os.makedirs(self.previewDir)

	def getPreviewPath(self, accref):
		return os.path.join(self.previewDir,
			rscdef.getFlatName(accref))

	def classify(self, accref):
		if os.path.exists(self.getPreviewPath(accref)):
			return "with"
		else:
			return "without"
	
	def process(self, accref):
		if self.classify(accref)=="with":
			return
		with utils.safeReplaced(self.getPreviewPath(accref)) as f:
			f.write(self.getPreviewData(accref))


class SpectralPreviewMaker(PreviewMaker):
	linearFluxes = False

	def _createAuxillaries(self, dd):
		PreviewMaker._createAuxillaries(self, dd)
		self.sdmDD = self.dd.rd.getById(self.sdmId)

	def iterIdentifiers(self):
		"""iterates over the accrefs in the first table of dd.
		"""
		tableId = self.dd.makes[0].table.getQName()
		with base.getTableConn() as conn:
			for r in conn.queryToDicts("select accref from %s"%tableId):
				yield r["accref"]

	def getPreviewData(self, accref):
		table = rsc.makeData(self.sdmDD, forceSource={
			"accref": accref}).getPrimaryTable()
		data = [(r["spectral"], r["flux"]) for r in table.rows]
		data.sort()

		fig = pyplot.figure(figsize=(4,2))
		ax = fig.add_axes([0,0,1,1], frameon=False)

		if self.linearFluxes:
			plotter = ax.plot
		else:
			plotter = ax.semilogy
		
		plotter(
			[r[0] for r in data], 
			[r[1] for r in data],
			color="black")
		ax.xaxis.set_major_locator(matplotlib.ticker.NullLocator())
		ax.yaxis.set_major_locator(matplotlib.ticker.NullLocator())
		ax.yaxis.set_minor_locator(matplotlib.ticker.NullLocator())

		rendered = StringIO()
		pyplot.savefig(rendered, format="png", dpi=50)
		pyplot.close()

		rendered = StringIO(rendered.getvalue())
		im = Image.open(rendered)
		im = im.convert("L")
		im = im.convert("P", palette=Image.ADAPTIVE, colors=8)
		compressed = StringIO()
		im.save(compressed, format="png", bits=3)
		return compressed.getvalue()


def procmain(processorClass, rdId, ddId):
	"""is a "standard" main function for scripts manipulating source files.

	The function returns the instanciated processor so you can communicate
	from your processor back to your own "main".

	makeProcessorArgs is an iterator that returns argName, argValue pairs
	for addition constructor keyword arguments.  Use this to pass in
	plate catalogs or similar.
	"""
	import optparse
	from gavo import rscdesc  #noflake: for registration
	rd = base.caches.getRD(rdId)
	dd = rd.getById(ddId)
	parser = optparse.OptionParser()
	processorClass.addOptions(parser)
	opts, args = parser.parse_args()
	if args:
		parser.print_help(file=sys.stderr)
		sys.exit(1)
	proc = processorClass(opts, dd)
	processed, ignored = proc.processAll()
	print "%s files processed, %s files with errors"%(processed, ignored)
	return proc
