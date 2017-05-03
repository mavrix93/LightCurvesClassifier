"""
Base classes and common code for grammars.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import codecs
import gzip
import re
import os
import select
import subprocess

from gavo import base
from gavo import rscdef
from gavo import utils
from gavo.rscdef import procdef
from gavo.rscdef import rowtriggers


class ParseError(base.Error):
	"""is an error raised by grammars if their input is somehow wrong.
	"""
	def __init__(self, msg, location=None, record=None):
		base.Error.__init__(self, msg)
		self.location, self.record = location, record
		self.args = [msg, location, record]


class REAttribute(base.UnicodeAttribute):
	"""is an attribute containing (compiled) RE
	"""
	def parse(self, value):
		if value is None or not value:
			return None
		try:
			return re.compile(value)
		except re.error, msg:
			raise base.ui.logOldExc(base.LiteralParseError(self.name_, value,
				hint="A python regular expression was expected here.  Compile"
					" complained: %s"%unicode(msg)))
	
	def unparse(self, value):
		if value is None:
			return ""
		else:
			return value.pattern


class FilteredInputFile(object):
	"""a pseudo-file that allows piping data thorugh a shell command.

	It supports read, readline, and close.  Close closes the original
	file, too.

	Warning: the command passed in will be shell-expanded (which is fair
	since you can pass in any command you want anyway).

	If you pass silent=True, stderr will be redirected to /dev/null.
	This is probably only attractive for unit tests and such.
	"""
	def __init__(self, filterCommand, origFile, silent=False):
		self.filterCommand, self.origFile = filterCommand, origFile

		processArgs = {"shell": True,
			"stdin": subprocess.PIPE, 
			"stdout": subprocess.PIPE, 
			"close_fds": True}
		if silent:
			processArgs["stderr"] = open("/dev/null", "w")
		self.process = subprocess.Popen([self.filterCommand], **processArgs)
		self.fromChild, self.toChild = self.process.stdout, self.process.stdin
		self.buffer = utils.StreamBuffer(2**14)

		try:
			self.PIPE_BUF = select.PIPE_BUF
		except AttributeError:
			# use POSIX guarantee for python<2.7
			self.PIPE_BUF = 512

	def _fillChildBuffer(self):
		"""feeds the child new data, closing the source file if all data
		has been fed.
		"""
		data = self.origFile.read(self.PIPE_BUF)
		if data=="":
			# source file exhausted, tell child we're done
			self.toChild.close()
			self.toChild = None 
		else:
			self.toChild.write(data)

	def _readAll(self):
		allChunks = []
		while True:
			data = self.read(2**20)
			if data=="":
				break
			allChunks.append(data)
		return "".join(allChunks)

	def _fillBuffer(self):
		"""tries to obtain another chunk of data from the child, feeding
		it new data if possible.
		"""
		if self.toChild:
			writeList = [self.toChild]
		else:
			writeList = []
		readReady, writeReady, _ = select.select(
			[self.fromChild], writeList, [])
		
		if writeReady:
			self._fillChildBuffer()

		if readReady:
			data = self.fromChild.read(self.PIPE_BUF)
			if data=="":
				self.buffer.doneWriting()
				if self.process.wait():
					raise IOError("Child exited with return code %s"%
						self.process.wait())
			self.buffer.add(data)

	def read(self, nBytes=None):
		if nBytes is None:
			return self._readAll()

		while self.buffer.curSize<nBytes and not self.buffer.finished:
			self._fillBuffer()

		return self.buffer.get(nBytes) or ""

	def readline(self):
		# let's do a quick one ourselves rather than inherit from file
		# just for this; this just works with unix line ends.
		while True:
			val = self.buffer.getToChar("\n")
			if val is None:
				if self.buffer.finished:
					return self.buffer.getRest()
				else:
					self._fillBuffer()
			else:
				return val

	def close(self):
		if self.process.returncode is None:
			self.process.terminate()
			# not checking the return code here; if the client closed
			# while the child was still running, an error from it would
			# not count as an error.
			self.process.wait()
		self.origFile.close()


class Rowfilter(procdef.ProcApp):
	"""A generator for rows coming from a grammar.

	Rowfilters receive rows (i.e., dictionaries) as yielded by a grammar
	under the name row.  Additionally, the embedding row iterator is
	available under the name rowIter.

	Macros are expanded within the embedding grammar.

	The procedure definition must result in a generator, i.e., there must
	be at least one yield.  Otherwise, it may swallow or create as many
	rows as desired.

	Here, you can only access whatever comes from the grammar.  You can
	access grammar keys in late parameters as row[key] or, if key is 
	like an identifier, as @key.
	"""
	name_ = "rowfilter"
	requiredType="rowfilter"
	formalArgs = "row, rowIter"

	def getFuncCode(self):
		return rscdef.replaceProcDefAt(procdef.ProcApp.getFuncCode(self), "row")


def compileRowfilter(filters):
	"""returns an iterator that "pipes" the rowfilters in filters.

	This means that the output of filters[0] is used as arguments to
	filters[1] and so on.

	If filters is empty, None is returned.
	"""
	if not filters:
		return
	iters = [f.compile() for f in filters] #noflake: code gen
	src = [
		"def iterPipe(row, rowIter):",
		"  for item0 in iters[0](row, rowIter):"]
	for ind in range(1, len(filters)):
		src.append("%s  for item%d in iters[%d](item%d, rowIter):"%(
			"  "*ind, ind, ind, ind-1))
	src.append("%s  yield item%d"%("  "*len(filters), len(filters)-1))
	d = locals()
	exec "\n".join(src) in d
	return d["iterPipe"]


class SourceFieldApp(rscdef.ProcApp):
	"""A procedure application that returns a dictionary added to all 
	incoming rows.
	
	Use this to programmatically provide information that can be computed
	once but that is then added to all rows coming from a single source, usually
	a file.  This could be useful to add information on the source of a
	record or the like.

	The code must return a dictionary.  The source that is about to be parsed is
	passed in as sourceToken.  When parsing from files, this simply is the file
	name.  The data the rows will be delivered to is available as "data", which
	is useful for adding or retrieving meta information.
	"""
	name_ = "sourceFields"

	requriedType = "sourceFields"
	formalArgs = "sourceToken, data"


class MapKeys(base.Structure):
	"""Mapping of names, specified in long or short forms.

	mapKeys is necessary in grammars like keyValueGrammar or fitsProdGrammar.
	In these, the source files themselves give key names.  Within the GAVO
	DC, keys are required to be valid python identifiers (i.e., match
	``[A-Za-z\_][A-Za-z\_0-9]*``).  If keys coming in do not have this form, 
	mapping can force proper names.

	mapKeys could also be used to make incoming names more suitable for
	matching with shell patterns (like in rowmaker idmaps).
	"""
	name_ = "mapKeys"

	_content = base.DataContent(description="Simple mappings in the form"
		"<dest>:<src>{,<dest>:<src>}")
	_mappings = base.DictAttribute("maps", keyName="dest", description=
		"Map source names given in content to the name given in dest.", 
		itemAttD=base.UnicodeAttribute("map"), inverted=True,
		copyable=True)

	def _parseShortenedMap(self, literal):
		try:
			for dest, src in (p.split(":") for p in literal.split(",")):
				if dest not in self.maps:
					self.maps[src.strip()] = dest.strip()
				else:
					raise base.LiteralParseError(self.name_, literal, 
						hint="%s clobbers an existing map within the row maker."%dest)
		except ValueError:
			raise base.ui.logOldExc(base.LiteralParseError(self.name_, literal,
				hint="A key-value enumeration of the format k:v {,k:v}"
				" is expected here"))

	def onElementComplete(self):
		if self.content_:
			self._parseShortenedMap(self.content_)
		self._onElementCompleteNext(MapKeys)

	def doMap(self, aDict):
		"""returns dict with the keys mapped according to the defined mappings.
		"""
		if self.maps:
			newDict = {}
			for k, v in aDict.iteritems():
				newDict[self.maps.get(k, k)] = v
			return newDict
		else:
			return aDict


class RowIterator(object):
	"""An object that encapsulates the a source being parsed by a
	grammar.

	RowIterators are returned by Grammars' parse methods.  Iterate
	over them to retrieve the rows contained in the source.

	You can also call getParameters on them to retrieve document-global
	values (e.g., the parameters of a VOTable, a global header of
	a FITS table).

	The getLocator method should return some string that aids the user
	in finding out why something went wrong (file name, line number, etc.)

	This default implementation works for when source is a sequence
	of dictionaries.  You will, in general, want to override 
	_iteRows and getLocator, plus probably __init__ (to prepare external
	resources) and getParameters (if you have them; make sure to update
	any parameters you have with self.sourceRow as shown in the default
	getParameters implementation).

	RowIterators are supposed to be self-destructing, i.e., they should 
	release any external resources they hold when _iterRows runs out of
	items.

	_iterRows should arrange for the instance variable recNo to be incremented
	by one for each item returned.
	"""
	notify = True

	def __init__(self, grammar, sourceToken, sourceRow=None):
		self.grammar, self.sourceToken = grammar, sourceToken
		self.sourceRow = sourceRow
		self.recNo = 0

	@property
	def recordNumber(self):
		# compatibility alias
		return self.recNo

	def __iter__(self):
		if self.notify:
			base.ui.notifyNewSource(self.sourceToken)
		if hasattr(self, "rowfilter"):
			baseIter = self._iterRowsProcessed()
		else:
			baseIter = self._iterRows()
		if self.grammar.ignoreOn:
			rowSource = self._filteredIter(baseIter)
		else:
			rowSource = baseIter

		try:
			for row in rowSource:
				# handle dispatched grammars here, too
				if isinstance(row, tuple):
					d = row[1]
				else:
					d = row

				if isinstance(d, dict):
					# else it could be a sentinel like FLUSH, which we leave alone
					if self.sourceRow:
						d.update(self.sourceRow)
					d["parser_"] = self

				yield row
		except:
			base.ui.notifySourceError()
			raise

		if self.notify:
			base.ui.notifySourceFinished()

	def _filteredIter(self, baseIter):
		for row in baseIter:
			if not self.grammar.ignoreOn(row):
				yield row

	def _iterRowsProcessed(self):
		if self.grammar.isDispatching:
			for dest, row in self._iterRows():
				for procRow in self.rowfilter(row, self):
					yield dest, procRow
		else:
			for row in self._iterRows():
				for procRow in self.rowfilter(row, self):
					yield procRow

	def _iterRows(self):
		if False:
			yield None
		self.grammar = None # don't wait for garbage collection

	def getParameters(self):
		res = {"parser_": self}
		if self.sourceRow:
			res.update(self.sourceRow)
		return res
	
	def getLocator(self):
		return "(unknown position -- locator missing)"


class FileRowIterator(RowIterator):
	"""is a RowIterator base for RowIterators reading files.

	It analyzes the sourceToken to see if it's a string, in which case
	it opens it as a file name and leaves the file object in self.inputFile.

	Otherwise, it assumes sourceToken already is a file object and binds
	it to self.inputFile.  It then tries to come up with a sensible designation
	for sourceToken.

	It also inspects the parent grammar for a gunzip attribute.  If it is
	present and true, the input file will be unzipped transparently.
	"""
	def __init__(self, grammar, sourceToken, **kwargs):
		RowIterator.__init__(self, grammar, sourceToken, **kwargs)
		self.curLine = 1
		try:
			self._openFile()
		except IOError, ex:
			raise base.ui.logOldExc(
				base.SourceParseError("I/O operation failed (%s)"%str(ex),
					source=str(sourceToken), location="start"))
	
	def _openFile(self):
		if isinstance(self.sourceToken, basestring):
			if self.grammar.enc:
				self.inputFile = codecs.open(self.sourceToken, "r", self.grammar.enc)
			else:
				self.inputFile = open(self.sourceToken)
		else:
			self.inputFile = self.sourceToken
			self.sourceToken = getattr(self.inputFile, "name", repr(self.sourceToken))

		if hasattr(self.grammar, "preFilter") and self.grammar.preFilter:
			self.inputFile = FilteredInputFile(
				self.grammar.preFilter, self.inputFile)

		elif hasattr(self.grammar, "gunzip") and self.grammar.gunzip:
			self.inputFile = gzip.GzipFile(fileobj=self.inputFile)


class FileRowAttributes(object):
	"""A mixin for grammars with FileRowIterators.

	This provides some attributes that FileRowIterators interpret, e.g.,
	preFilter.
	"""
	_gunzip = base.BooleanAttribute("gunzip", description="Unzip sources"
		" while reading? (Deprecated, use preFilter='zcat')", default=False)
	_preFilter = base.UnicodeAttribute("preFilter", description="Shell"
		" command to pipe the input through before passing it on to the"
		" grammar.  Classical examples include zcat or bzcat, but you"
		" can commit arbitrary shell atrocities here.",
		copyable=True)

	def completeElement(self, ctx):
		if ctx.restricted:
			if self.preFilter is not None:
				raise base.RestrictedElement("preFilter")
		self._completeElementNext(FileRowAttributes, ctx)


class GrammarMacroMixin(base.StandardMacroMixin):
	"""A collection of macros available to rowfilters.

	NOTE: All macros should return only one single physical python line,
	or they will mess up the calculation of what constructs caused errors.
	"""
	def macro_inputRelativePath(self, liberalChars="True"):
		"""returns an expression giving the current source's path
		relative to inputsDir

		liberalChars can be a boolean literal (True, False, etc); if false,
		a value error is raised if characters that will result in trouble
		with the product mixin are within the result path.
		"""
		return ('utils.getRelativePath(rowIter.sourceToken,'
			' base.getConfig("inputsDir"), liberalChars=%s)'%(
				base.parseBooleanLiteral(liberalChars)))

	def macro_fullDLURL(self, dlService):
		r"""returns a python expression giving a link pullling the standard 
		PubDID of the current source through the datalink service dlService.

		You would write \fullDLURL{dlsvc} here, and the macro will expand into
		something like http://yourserver/currd/dlget?ID=ivo://whatever.

		dlService is the id of the datalink service in the current RD.
		"""
		baseURL = self.rd.getById(dlService).getURL("dlget")
		return ("'%%s?ID=%%s'%%(%s,"
			" urllib.quote_plus(getStandardPubDID(rowIter.sourceToken)))"%(
				repr(baseURL)))

	def macro_standardPreviewPath(self):
		"""returns an expression for the standard path for a custom preview.

		This consists of resdir, the name of the previewDir property on the
		embedding DD, and the flat name of the accref (which this macro
		assumes to see in its namespace as accref; this is usually the
		case in //products#define, which is where this macro would typically be
		used).
		
		See the introduction to custom previews for details.
		"""
		constantPrefix = os.path.join(
			rscdef.getInputsRelativePath(self.parent.rd.resdir),
			self.parent.getProperty("previewDir"))+"/"
		return (repr(constantPrefix)
			+"+getFlatName(accref)")

	def macro_rowsProcessed(self):
		"""returns an expression giving the number of records already
		ingested for this source.
		"""
		return 'rowIter.line'

	def macro_sourceDate(self):
		"""returns an expression giving the timestamp of the current source.
		"""
		return 'datetime.utcfromtimestamp(os.path.getmtime(rowIter.sourceToken))'
		
	def macro_srcstem(self):
		"""returns the stem of the source file currently parsed.
		
		Example: if you're currently parsing /tmp/foo.bar, the stem is foo.
		"""
		return 'os.path.splitext(os.path.basename(rowIter.sourceToken))[0]'

	def macro_lastSourceElements(self, numElements):
		"""returns an expression calling rmkfuncs.lastSourceElements on
		the current input path.
		"""
		return 'lastSourceElements(rowIter.sourceToken, int(numElements))'

	def macro_rootlessPath(self):
		"""returns an expression giving the current source's path with
		the resource descriptor's root removed.
		"""
		return ('utils.getRelativePath(rowIter.grammar.rd.resdir,'
			' rowIter.sourceToken)')

	def macro_inputSize(self):
		"""returns an expression giving the size of the current source.
		"""
		return 'os.path.getsize(rowIter.sourceToken)'

	def macro_colNames(self, tableRef):
		"""returns a comma-separated list of column names for a table reference.

		This is convenient if an input file matches the table structure; you
		can then simply say things like <reGrammar names="\\\\colName{someTable}"/>.
		"""
		return ",".join(c.name for c in self.rd.getById(tableRef))

	def macro_property(self, property):
		"""returns the value of property on the parent DD.
		"""
		return self.parent.getProperty(property)


class Grammar(base.Structure, GrammarMacroMixin):
	"""An abstract grammar.

	Grammars are configured via their structure parameters.  Their 
	parse(sourceToken) method returns an object that iterates over rawdicts
	(dictionaries mapping keys to (typically) strings) that can then be fed
	through rowmakers; it also has a method getParameters that returns
	global properties of the whole document (like parameters in VOTables;
	this will be empty for many kinds of grammars).

	RowIterators will return a reference to themselves in the raw dicts in the
	parser_ key unless you override their _iterRowsProcessed method (which you
	shouldn't).  This is used by rowmaker macros.

	What exactly sourceToken is is up to the concrete grammar.  While
	typically it's a file name, it might be a sequence of dictionaries,
	a nevow context, or whatever.
	
	To derive a concrete Grammar, define a RowIterator for your source
	and set the rowIterator class attribute to it.
	"""
	name_ = "grammar"

	_encoding = base.UnicodeAttribute("enc", default=None, description=
		"Encoding of strings coming in from source.", copyable=True)
	_rowfilters = base.StructListAttribute("rowfilters", 
		description="Row filters for this grammar.", 
		childFactory=Rowfilter, copyable=True)
	_ignoreOn = base.StructAttribute("ignoreOn", default=None, copyable=True,
		description="Conditions for ignoring certain input records.  These"
			" triggers drop an input record entirely.  If you feed multiple"
			" tables and just want to drop a row from a specific table, you"
			" can use ignoreOn in a rowmaker.",
		childFactory=rowtriggers.IgnoreOn)
	_sourceFields = base.StructAttribute("sourceFields", default=None,
		copyable=True, description="Code returning a dictionary of values"
		" added to all returned rows.", childFactory=SourceFieldApp)
	_properties = base.PropertyAttribute(copyable=True)
	_original = base.OriginalAttribute()
	_rd = rscdef.RDAttribute()

	# isDispatching is used by various special grammars to signify the
	# grammar returns rowdicts for multiple makers.  See those.
	# Here, we just fix it to false so clients can rely on the attribute's
	# existance.
	isDispatching = False

	rowIterator = RowIterator

	def getSourceFields(self, sourceToken, data):
		"""returns a dict containing user-defined fields to be added to
		all results.
		"""
		if self.sourceFields is None:
			return None
		if not hasattr(self, "_compiledSourceFields"):
			self._compiledSourceFields = self.sourceFields.compile()
		return self._compiledSourceFields(sourceToken, data)

	def parse(self, sourceToken, targetData=None):
		ri = self.rowIterator(self, sourceToken, 
			sourceRow=self.getSourceFields(sourceToken, targetData))
		if self.rowfilters:
			ri.rowfilter = compileRowfilter(self.rowfilters)
		return ri


class NullGrammar(Grammar):
	"""A grammar that never returns any rows.
	"""
	name_ = "nullGrammar"
