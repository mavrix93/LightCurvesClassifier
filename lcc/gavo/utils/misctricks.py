"""
Various helpers that didn't fit into any other xTricks.
"""

#c Copyright 2008-2016, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from __future__ import with_statement

import collections
import contextlib
import itertools
import os
import re
import struct
import threading
import urllib2
from cStringIO import StringIO

from gavo.utils import excs

class NotInstalledModuleStub(object):
	"""A stub that raises some more or less descriptive error on attribute
	access.

	This is used in some places no replace non-essential modules.
	"""
	def __init__(self, modName):
		self.modName = modName

	def __getattr__(self, name):
		raise RuntimeError("%s not installed"%self.modName)



BIBCODE_PATTERN = re.compile("[012]\d\d\d\w[^ ]{14}$")

def couldBeABibcode(s):
	"""returns true if we think that the string s is a bibcode.

	This is based on matching against BIBCODE_PATTERN.
	"""
	return bool(BIBCODE_PATTERN.match(s))


try:
	from docutils import core as rstcore

	from docutils import nodes
	from docutils import utils as rstutils
	from docutils.parsers.rst import roles
	from docutils.parsers.rst import directives

	class RSTExtensions(object):
		"""a register for local RST extensions.

		This is for both directives and interpreted text roles.  

		We need these as additional markup in examples; these always
		introduce local rst interpreted text roles, which always
		add some class to the node in question (modifications are possible).

		These classes are then changed to properties as the HTML fragments
		from RST translation are processed by the _Example nevow data factory.

		To add a new text role, say::

			RSTExtensions.addRole(roleName, roleFunc=None)

		You can pass in a full role function as discussed in
		/usr/share/doc/python-docutils/docs/howto/rst-roles.html (Debian systems).
		It must, however, add a dachs-ex-<roleName> class to the node. The
		default funtion produces a nodes.emphasis item with the proper class.

		In a pinch, you can pass a propertyName argument to addRole if the
		desired property name is distinct from the role name in the RST.
		This is used by tapquery and taprole since we didn't want to change
		our examples when the standard changed.

		To add a directive, say::

			RSTExtensions.addDirective(dirName, dirClass)

		In HTML, these classes become properties named like the role name
		(except you can again use propertyName in a pinch).
		"""
		classToProperty = {}

		@classmethod
		def addDirective(cls, name, implementingClass, propertyName=None):
			directives.register_directive(name, implementingClass)
			cls.classToProperty["dachs-ex-"+name] = propertyName or name

		@classmethod
		def makeTextRole(cls, roleName, roleFunc=None, propertyName=None):
			"""creates a new text role for roleName.

			See class docstring.
			"""
			if roleFunc is None:
				roleFunc = cls._makeDefaultRoleFunc(roleName)
			roles.register_local_role(roleName, roleFunc)
			cls.classToProperty["dachs-ex-"+roleName] = propertyName or roleName
		
		@classmethod
		def _makeDefaultRoleFunc(cls, roleName):
			"""returns an RST interpeted text role parser function returning
			an emphasis node with a dachs-ex-roleName class.
			"""
			def roleFunc(name, rawText, text, lineno, inliner, 
					options={}, content=[]):
				node = nodes.emphasis(rawText, text)
				node["classes"] = ["dachs-ex-"+roleName]
				return [node], []

			return roleFunc

	# Generally useful RST extensions (for roles useful in examples, 
	# see examplesrender)
	def _bibcodeRoleFunc(name, rawText, text, lineno, inliner,
			options={}, content=[]):
		if not couldBeABibcode(text):
			raise ValueError("Probably not a bibcode: '%s'"%text)
		node = nodes.reference(rawText, text,
			refuri="http://adsabs.harvard.edu/abs/%s"%text) 
		node["classes"] = ["bibcode-link"]
		return [node], []

	RSTExtensions.makeTextRole("bibcode", _bibcodeRoleFunc)
	del _bibcodeRoleFunc

	# RST extensions for documention writing

	_explicitTitleRE = re.compile(r'^(.+?)\s*(?<!\x00)<(.*?)>$', re.DOTALL)

	def _dachsdocRoleFunc(name, rawText, text, lineno, inliner, 
			options={}, content=[]):
		# inspired by sphinx extlinks
		text = rstutils.unescape(text)
		mat = _explicitTitleRE.match(text)
		if mat:
			title, url = mat.groups()
		else:
			title, url = text.split("/")[-1], text
		url = "http://docs.g-vo.org/DaCHS/"+url
		return [nodes.reference(title, title, internal=False, refuri=url)
			], []

	RSTExtensions.makeTextRole("dachsdoc", _dachsdocRoleFunc)
	del _dachsdocRoleFunc

	def _dachsrefRoleFunc(name, rawText, text, lineno, inliner, 
			options={}, content=[]):
		# this will guess a link into the ref documentation
		text = rstutils.unescape(text)
		fragId = re.sub("[^a-z0-9]+", "-", text.lower())
		url = "http://docs.g-vo.org/DaCHS/ref.html#"+fragId
		return [nodes.reference(text, text, internal=False, refuri=url)
			], []

	RSTExtensions.makeTextRole("dachsref", _dachsrefRoleFunc)
	del _dachsrefRoleFunc

	def _samplerdRoleFunc(name, rawText, text, lineno, inliner, 
			options={}, content=[]):
		# this will turn into a link to a file in the GAVO svn
		# (usually for RDs)
		text = rstutils.unescape(text)
		url = "http://svn.ari.uni-heidelberg.de/svn/gavo/hdinputs/"+text
		return [nodes.reference(text, text, internal=False, refuri=url)
			], []

	RSTExtensions.makeTextRole("samplerd", _samplerdRoleFunc)
	del _samplerdRoleFunc

except ImportError:
	rstcore = NotInstalledModuleStub("docutils") #noflake: conditional import


class _UndefinedType(type):
	"""the metaclass for Undefined.

	Used internally.
	"""
	def __str__(cls):
		raise excs.StructureError("%s cannot be stringified."%cls.__name__)

	__unicode__ = __str__

	def __repr__(cls):
		return "<Undefined>"

	def __nonzero__(cls):
		return False


class Undefined(object):
	"""a sentinel for all kinds of undefined values.

	Do not instantiate.

	>>> Undefined()
	Traceback (most recent call last):
	TypeError: Undefined cannot be instantiated.
	>>> bool(Undefined)
	False
	>>> repr(Undefined)
	'<Undefined>'
	>>> str(Undefined)
	Traceback (most recent call last):
	StructureError: Undefined cannot be stringified.
	"""
	__metaclass__ = _UndefinedType

	def __init__(self):
		raise TypeError("Undefined cannot be instantiated.")


class QuotedName(object):
	"""A string-like thing basically representing SQL delimited identifiers.

	This has some features that make handling these relatively painless
	in ADQL code.

	The most horrible feature is that these hash and compare as their embedded
	names, except to other QuotedNamess.

	SQL-92, in 5.2, roughly says:

	delimited identifiers compare literally with each other,
	delimited identifiers compare with regular identifiers after the
	latter are all turned to upper case.  But since postgres turns everything
	to lower case, we do so here, too.

	>>> n1, n2, n3 = QuotedName("foo"), QuotedName('foo"l'), QuotedName("foo")
	>>> n1==n2,n1==n3,hash(n1)==hash("foo")
	(False, True, True)
	>>> print n1, n2
	"foo" "foo""l"
	"""
	def __init__(self, name):
		self.name = name
	
	def __hash__(self):
		return hash(self.name)
	
	def __eq__(self, other):
		if isinstance(other, QuotedName):
			return self.name==other.name
		elif isinstance(other, basestring):
			return self.name==other.lower()
		else:
			return False

	def __ne__(self, other):
		return not self==other

	def __str__(self):
		return '"%s"'%(self.name.replace('"', '""'))

	def __repr__(self):
		return 'QuotedName(%s)'%repr(self.name)

	def lower(self):  # service to ADQL name resolution
		return self

	def flatten(self): # ADQL query serialization
		return str(self)

	def capitalize(self):  # service for table head and such
		return self.name.capitalize()
	
	def __add__(self, other):  # for disambiguateColumns
		return QuotedName(self.name+other)


class StreamBuffer(object):
	"""a buffer that takes data in arbitrary chunks and returns
	them in chops of chunkSize bytes.

	There's a lock in place so you can access add and get from
	different threads.

	When everything is written, you must all doneWriting.
	"""
	# XXX TODO: Can we make a reasoned  choice for (default) chunkSize?
	chunkSize = 50000

	def __init__(self, chunkSize=None):
		self.buffer = collections.deque()
		if chunkSize is not None:
			self.chunkSize = chunkSize
		self.curSize = 0
		self.lock = threading.Lock()
		self.finished = False
	
	def add(self, data):
		with self.lock:
			self.buffer.append(data)
			self.curSize += len(data)
	
	def get(self, numBytes=None):
		if numBytes is None:
			numBytes = self.chunkSize

		if self.curSize<numBytes and not self.finished:
			return None
		if not self.buffer:
			return None

		with self.lock:
			items, sz = [], 0
			# collect items till we've got a chunk
			while self.buffer:
				item = self.buffer.popleft()
				sz += len(item)
				self.curSize -= len(item)
				items.append(item)
				if sz>=numBytes:
					break

			# make a chunk and push back what we didn't need
			chunk = "".join(items)
			leftOver = chunk[numBytes:]
			if leftOver:
				self.buffer.appendleft(leftOver)
			self.curSize += len(leftOver)
			chunk = chunk[:numBytes]

		return chunk

	# XXX TODO: refactor get and getToChar to use as much common code
	# as sensible
	def getToChar(self, char):
		"""returns the the buffer up to the first occurrence of char.

		If char is not present in the buffer, the function returns None.
		"""
		with self.lock:
			items, sz = [], 0
			# collect items till we've got our character
			while self.buffer:
				item = self.buffer.popleft()
				sz += len(item)
				self.curSize -= len(item)
				items.append(item)
				if char in item:
					break
			else:
				# didn't break out of the loop, i.e., no char found.
				# items now contains the entire buffer.
				self.buffer.clear()
				self.buffer.append("".join(items))
				self.curSize = sz
				return None

			# char is in the last element of items
			items[-1], leftOver = items[-1].split(char, 1)
			chunk = "".join(items)
			if leftOver:
				self.buffer.appendleft(leftOver)
			self.curSize += len(leftOver)
			return chunk+char

		raise AssertionError("This cannot happen")
	
	
	def getRest(self):
		"""returns the entire buffer as far as it is left over.
		"""
		result = "".join(self.buffer)
		self.buffer = []
		return result

	def doneWriting(self):
		self.finished = True


def grouped(n, seq):
	"""yields items of seq in groups n elements.

	If len(seq)%n!=0, the last elements are discarded.

	>>> list(grouped(2, range(5)))
	[(0, 1), (2, 3)]
	>>> list(grouped(3, range(9)))
	[(0, 1, 2), (3, 4, 5), (6, 7, 8)]
	"""
	return itertools.izip(*([iter(seq)]*n))


def getfirst(args, key, default=Undefined):
	"""returns the first value of key in the web argument-like object args.

	args is a dictionary mapping keys to lists of values.  If key is present,
	the first element of the list is returned; else, or if the list is
	empty, default if given.  If not, a Validation error for the requested
	column is raised.

	Finally, if args[key] is neither list nor tuple (in an ininstance
	sense), it is returned unchanged.

	>>> getfirst({'x': [1,2,3]}, 'x')
	1
	>>> getfirst({'x': []}, 'x')
	Traceback (most recent call last):
	ValidationError: Field x: Missing mandatory parameter x
	>>> getfirst({'x': []}, 'y')
	Traceback (most recent call last):
	ValidationError: Field y: Missing mandatory parameter y
	>>> print(getfirst({'x': []}, 'y', None))
	None
	>>> getfirst({'x': 'abc'}, 'x')
	'abc'
	"""
	try:
		val = args[key]
		if isinstance(val, (list, tuple)):
			return val[0]
		else:
			return val
	except (KeyError, IndexError):
		if default is Undefined:
			raise excs.ValidationError("Missing mandatory parameter %s"%key,
				colName=key)
		return default


def sendUIEvent(eventName, *args):
	"""sends an eventName to the DC event dispatcher.

	If no event dispatcher is available, do nothing.

	The base.ui object that DaCHS uses for event dispatching
	is only available to sub-packages above base.  Other code should not
	use or need it under normal circumstances, but if it does, it can
	use this.

	All other code should use base.ui.notify<eventName>(*args) directly.
	"""
	try:
		from gavo.base import ui
		getattr(ui, "notify"+eventName)(*args)
	except ImportError:
		pass


def logOldExc(exc):
	"""logs the mutation of the currently handled exception to exc.

	This just does a notifyExceptionMutation using sendUIEvent; it should
	only be used by code at or below base.
	"""
	sendUIEvent("ExceptionMutation", exc)
	return exc


def getFortranRec(f):
	"""reads a "fortran record" from f and returns the payload.

	A "fortran record" comes from an unformatted file and has a
	4-byte payload length before and after the payload.  Native endianess
	is assumed here.

	If the two length specs do not match, a ValueError is raised.
	"""
	try:
		startPos = f.tell()
	except IOError:
		startPos = "(stdin)"
	rawLength = f.read(4)
	if rawLength=='': # EOF
		return None
	recLen = struct.unpack("i", rawLength)[0]
	data = f.read(recLen)
	rawPost = f.read(4)
	if not rawPost:
		raise ValueError("Record starting at %s has no postamble"%startPos)
	postambleLen = struct.unpack("i", rawPost)[0]
	if recLen!=postambleLen:
		raise ValueError("Record length at record (%d) and did not match"
			" postamble declared length (%d) at %s"%(
				recLen, postambleLen, startPos))
	return data


def iterFortranRecs(f, skip=0):
	"""iterates over the fortran records in f.

	For details, see getFortranRec.
	"""
	while True:
		rec = getFortranRec(f)
		if rec is None:
			break
		if skip>0:
			skip -= 1
			continue
		yield rec


def getWithCache(url, cacheDir, extraHeaders={}):
	"""returns the content of url, from a cache if possible.

	Of course, you only want to use this if there's some external guarantee
	that the resource behing url doesn't change.  No expiry mechanism is
	present here.
	"""
	if not os.path.isdir(cacheDir):
		os.makedirs(cacheDir)
	cacheName = os.path.join(cacheDir, re.sub("[^\w]+", "", url)+".cache")
	if os.path.exists(cacheName):
		with open(cacheName) as f:
			return f.read()
	else:
		f = urllib2.urlopen(url)
		doc = f.read()
		f.close()
		with open(cacheName, "w") as f:
			f.write(doc)
		return doc


def rstxToHTMLWithWarning(source, **userOverrides):
	"""returns HTML and a string with warnings for a piece of ReStructured 
	text.

	source can be a unicode string or a byte string in utf-8.

	userOverrides will be added to the overrides argument of docutils'
	core.publish_parts.
	"""
	sourcePath, destinationPath = None, None
	if not isinstance(source, unicode):
		source = source.decode("utf-8")
	
	warnAccum = StringIO()
	overrides = {'input_encoding': 'unicode',
		'raw_enabled': True,
		'doctitle_xform': None,
		'warning_stream': warnAccum,
		'initial_header_level': 4}
	overrides.update(userOverrides)

	parts = rstcore.publish_parts(
		source=source+"\n", source_path=sourcePath,
		destination_path=destinationPath,
		writer_name='html', settings_overrides=overrides)
	return parts["fragment"], warnAccum.getvalue()


def rstxToHTML(source, **userOverrides):
	"""returns HTML for a piece of ReStructured text.

	source can be a unicode string or a byte string in utf-8.

	userOverrides will be added to the overrides argument of docutils'
	core.publish_parts.
	"""
	return rstxToHTMLWithWarning(source, **userOverrides)[0]


class CaseSemisensitiveDict(dict):
	"""A dictionary allowing case-insensitive access to its content.

	This is used for DAL renderers which, unfortunately, are supposed
	to be case insensitive.  Since case insensitivity is at least undesirable
	for service-specific keys, we go a semi-insenstitve approach here:
	First, we try literal matches, if that does not work, we try matching
	against an all-uppercase version.

	Name clashes resulting from different names being mapped to the
	same normalized version are handled in some random way.  Don't do this.
	And don't rely on case normalization if at all possible.

	Only strings are allowed as keys here.  This class is not concerned
	with the values.
	>>> d = CaseSemisensitiveDict({"a": 1, "A": 2, "b": 3})
	>>> d["a"], d["A"], d["b"], d["B"]
	(1, 2, 3, 3)
	>>> d["B"] = 9; d["b"], d["B"]
	(3, 9)
	>>> del d["b"]; d["b"], d["B"]
	(9, 9)
	>>> "B" in d, "b" in d, "u" in d
	(True, True, False)
	"""
	def __init__(self, *args, **kwargs):
		dict.__init__(self, *args, **kwargs)
		self._normCasedCache = None

	def __getitem__(self, key):
		try:
			return dict.__getitem__(self, key)
		except KeyError:
			pass # try again with normalized case.
		return self._normCased[key.upper()]

	def __setitem__(self, key, value):
		self._normCasedCache = None
		dict.__setitem__(self, key, value)

	def __contains__(self, key):
		return dict.__contains__(self, key) or key.upper() in self._normCased

	@property
	def _normCased(self):
		if self._normCasedCache is None:
			self._normCasedCache = dict((k.upper(), v) 
				for k, v in self.iteritems())
		return self._normCasedCache


####################### Pyparsing hacks
# This may not be the best place to put this, but I don't really have a
# better one at this point.  We need some configuration of pyparsing, and
# this is probably imported by all modules doing pyparsing.
#
# (1) When building grammars, always do so using the pyparsingWhitechars
# context manager.  Building grammars is thread-safe, but different
# grammars here use different whitespace conventions, so without
# the c.m., you might get those messed up.
#
# (2) When parsing strings, *always* go through pyparseString(grammar,
# string) and fellow functions whenever your code could run from within
# the server (i.e., basically always outside of tests).
# pyparsing is not thread-safe, and thus we'll need to shoehorn some
# locking on top of it; I don't want to change the pyparsing methods
# themselves since they may be called very frequently.

try:
	from gavo.imp.pyparsing import ParserElement
	ParserElement.enablePackrat()
	# Hack to get around behaviour swings of setParseAction; we use
	# addParseAction throughout and retrofit it to pyparsings that don't have it.
	if not hasattr(ParserElement, "addParseAction"):
		ParserElement.addParseAction = ParserElement.setParseAction

	_PYPARSE_LOCK = threading.RLock()

	@contextlib.contextmanager
	def pyparsingWhitechars(whiteChars):
		"""a context manager that serializes pyparsing grammar compilation
		and manages its whitespace chars.

		We need different whitespace definitions in some parts of DaCHS.
		(The default used to be " \\t" for a while, so this is what things
		get reset to).

		Since whitespace apparently can only be set globally for pyparsing,
		we provide this c.m.  Since it is possible that grammars will be
		compiled in threads (e.g., as a side effect of getRD), this is
		protected by a lock.  This, in turn, means that this can 
		potentially block for a fairly long time.

		Bottom line: When compiling pyparsing grammars, *always* set
		the whitespace chars explicitely, and do it through this c.m.
		"""
		_PYPARSE_LOCK.acquire()
		ParserElement.setDefaultWhitespaceChars(whiteChars)
		try:
			yield
		finally:
			ParserElement.setDefaultWhitespaceChars(" \t")
			_PYPARSE_LOCK.release()

	def pyparseString(grammar, string, **kwargs):
		"""parses a string using a pyparsing grammar thread-safely.
		"""
		with _PYPARSE_LOCK:
			res = grammar.parseString(string, **kwargs)
			grammar.resetCache()
			return res

	def pyparseTransform(grammar, string, **kwargs):
		"""calls grammar's transformString method thread-safely.
		"""
		with _PYPARSE_LOCK:
			return grammar.transformString(string, **kwargs)


	######################### pyparsing-based key-value lines.  

	def _makeKVLGrammar():
		from gavo.imp.pyparsing import (
			Word,alphas, QuotedString, Regex, OneOrMore)

		with pyparsingWhitechars(" \t"):
			keyword = Word(alphas+"_")("key")
			keyword.setName("Keyword")
			value = (QuotedString(quoteChar="'", escChar='\\')
				| Regex("[^'= \t]*"))("value")
			value.setName("Simple value or quoted string")
			pair = keyword - "=" - value
			pair.setParseAction(lambda s,p,t: (t["key"], t["value"]))
			line = OneOrMore(pair)
			line.setParseAction(lambda s,p,t: dict(list(t)))

		return line

	_KVL_GRAMMAR = _makeKVLGrammar()

	def parseKVLine(aString):
		"""returns a dictionary for a "key-value line".

		key-value lines represent string-valued dictionaries
		following postgres libpq/dsn (see PQconnectdb docs;
		it's keyword=value, whitespace-separated, with
		whitespace allowed in values through single quoting,
		and backslash-escaping
		"""
		return pyparseString(_KVL_GRAMMAR, aString, parseAll=True)[0]

	_IDENTIFIER_PATTERN = re.compile("[A-Za-z_]+$")

	def makeKVLine(aDict):
		"""serialized a dictionary to a key-value line.

		See parseKVLine for details.
		"""
		parts = []
		for key, value in aDict.iteritems():
			if not _IDENTIFIER_PATTERN.match(key):
				raise ValueError("'%s' not allowed as a key in key-value lines"%key)
			value = str(value)
			if not _IDENTIFIER_PATTERN.match(value):
				value = "'%s'"%value.replace("\\", "\\\\"
					).replace("'", "\\'")
			parts.append("%s=%s"%(key, value))
		return " ".join(sorted(parts))

except ImportError, ex:  # no pyparsing, let clients bomb if they need it.
	@contextlib.contextmanager #noflake: conditional definition
	def pyparsingWhitechars(arg): 
		raise ex
		yield




def _test():
	import doctest, misctricks
	doctest.testmod(misctricks)


if __name__=="__main__":
	_test()
