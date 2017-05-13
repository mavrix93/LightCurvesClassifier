"""
Functions dealing with compilation and introspection of python and 
external code.
"""

#c Copyright 2008-2016, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from __future__ import with_statement

import compiler
import compiler.ast
import contextlib
import imp
import itertools
import inspect
import functools
import linecache
import os
import re
import shutil
import string
import sys
import tempfile
import threading
import weakref
from cStringIO import StringIO

from gavo.utils import algotricks
from gavo.utils import misctricks
from gavo.utils import excs


class CachedGetter(object):
	"""A cache for a callable.

	This is basically memoization, except that these are supposed
	to be singletons;  CachedGetters should be used where the
	construction of a resource (e.g., a grammar) should be deferred
	until it is actually needed to save on startup times.

	The resource is created on the first call, all further calls
	just return references to the original object.

	You can also leave out the getter argument and add an argumentless
	method impl computing the value to cache.

	Using a CachedGetter also serializes generation, so you can also
	use it when getter isn't thread-safe.

	At construction, you can pass a f(thing) -> bool in an isAlive
	keyword argument.  If you do, the function will be called with the
	cache before the cache is being returned.  If it returns false,
	the resource is re-made (no concurrency control is enforced here).
	"""
	def __init__(self, getter, *args, **kwargs):
		if getter is None:
			getter = self.impl
		self.cache, self.getter = None, getter
		
		self.isAlive = kwargs.pop("isAlive", None)
		self.args, self.kwargs = args, kwargs
		self.lock = threading.Lock()
	
	def __call__(self):
		if (self.isAlive is not None
				and self.cache is not None 
				and not self.isAlive(self.cache)):
			self.cache = None

		if self.cache is None:
			with self.lock:
				# Second and following in already have the cache set and return here
				if self.cache is not None:
					return self.cache
				self.cache = self.getter(*self.args, **self.kwargs)

				# If the cache is immortal, do away with the stuff needed
				# for its creation 
				if self.isAlive is None:
					del self.args
					del self.kwargs
					del self.lock
		
		return self.cache


class CachedResource(object):
	"""is like CachedGetter but with a built-in getter.

	Here, you define your class and have a class method impl returning
	what you want.
	"""
	cache = None

	@classmethod 
	def __new__(cls, arg):
		if cls.cache is None:
			cls.cache = cls.impl()
		return cls.cache


class DeferredImport(object):
	"""A trivial deferred module loader.

	Use this to delay the actual import of a module until it's actually
	needed.

	Use this like this::
	
		pywcs = utils.DeferredImport("pywcs")
	"""
	loadedModule = None

	def __init__(self, moduleName):
		self.moduleName = moduleName
	
	def __getattr__(self, *args):
		module = importModule(self.moduleName)
		globals()[self.moduleName] = module
		return getattr(module, *args)


class IdManagerMixin(object):
	"""
	A mixin for objects requiring unique IDs.
	
	The primaray use case is XML generation, where you want stable IDs
	for objects, but IDs must be unique over an entire XML file.
	
	The IdManagerMixin provides some methods for doing that:
		
		- makeIdFor(object) -- returns an id for object, or None if makeIdFor has
			already been called for that object (i.e., it presumably already is
			in the document).

		- getIdFor(object) -- returns an id for object if makeIdFor has already
			been called before.  Otherwise, a NotFoundError is raised

		- getOrMakeIdFor(object) -- returns an id for object; if object has
			been seen before, it's the same id as before.  Identity is by equality
			for purposes of dictionaries.

		- getForId(id) -- returns the object belonging to an id that has
			been handed out before.  Raises a NotFoundError for unknown ids.

		- cloneFrom(other) -- overwrites the self's id management dictionaries 
			with those from other.  You want this if two id managers must work
			on the same document.
	"""
	__cleanupPat = re.compile("[^A-Za-z0-9_]+")
# Return a proxy instead of raising a KeyError here?  We probably no not
# really want to generate xml with forward references, but who knows?
	def __getIdMaps(self):
		try:
			return self.__objectToId, self.__idsToObject
		except AttributeError:
			self.__objectToId, self.__idsToObject = {}, {}
			return self.__objectToId, self.__idsToObject

	def _fixSuggestion(self, suggestion, invMap):
		for i in itertools.count():
			newId = suggestion+str(i)
			if newId not in invMap:
				return newId

	def cloneFrom(self, other):
		"""takes the id management dictionaries from other.
		"""
		self.__objectToId, self.__idsToObject = other.__getIdMaps()

	def makeIdFor(self, ob, suggestion=None):
		map, invMap = self.__getIdMaps()
		if suggestion:
			suggestion = self.__cleanupPat.sub("", suggestion)
		if id(ob) in map:
			return None

		if suggestion is not None: 
			if suggestion in invMap:
				newId = self._fixSuggestion(suggestion, invMap)
			else:
				newId = suggestion
		else:
			newId = intToFunnyWord(id(ob))

		# register id(ob) <-> newId map, avoiding refs to ob
		map[id(ob)] = newId
		try:
			invMap[newId] = weakref.proxy(ob)
		except TypeError:  # something we can't weakref to
			invMap[newId] = ob
		return newId
	
	def getIdFor(self, ob):
		try:
			return self.__getIdMaps()[0][id(ob)]
		except KeyError:
			raise excs.NotFoundError(repr(ob), what="object",
				within="id manager %r"%(self,), hint="Someone asked for the"
				" id of an object not managed by the id manager.  This usually"
				" is a software bug.")

	def getOrMakeIdFor(self, ob, suggestion=None):
		try:
			return self.getIdFor(ob)
		except excs.NotFoundError:
			return self.makeIdFor(ob, suggestion)

	def getForId(self, id):
		try:
			return self.__getIdMaps()[1][id]
		except KeyError:
			raise excs.NotFoundError(id, what="id", within="id manager %r"%(self,),
				hint="Someone asked for the object belonging to an id that has"
				" been generated externally (i.e., not by this id manager).  This"
				" usually is an internal error of the software.")


class NullObject(object):
	"""A Null object, i.e. one that accepts any method call whatsoever.

	This mainly here for use in scaffolding.
	"""
	def __getattr__(self, name):
		return self
	
	def __call__(self, *args, **kwargs):
		pass


class _CmpType(type):
	"""is a metaclass for *classes* that always compare in one way.
	"""
# Ok, the class thing is just posing.  It's fun anyway.
	def __cmp__(cls, other):
		return cls.cmpRes


class _Comparer(object):
	__metaclass__ = _CmpType
	def __init__(self, *args, **kwargs):
		raise excs.Error(
			"%s classes can't be instanciated."%self.__class__.__name__)


class Infimum(_Comparer):
	"""is a *class* smaller than anything.

	This will only work as the first operand.

	>>> Infimum<-2333
	True
	>>> Infimum<""
	True
	>>> Infimum<None
	True
	>>> Infimum<Infimum
	True
	"""
	cmpRes = -1


class Supremum(_Comparer):
	"""is a *class* larger than anything.

	This will only work as the first operand.

	>>> Supremum>1e300
	True
	>>> Supremum>""
	True
	>>> Supremum>None
	True
	>>> Supremum>Supremum
	True
	"""
	cmpRes = 1


class AllEncompassingSet(set):
	"""a set that contains everything.

	Ok, so this doesn't exist.  Yes, I've read my Russell.  You see, this
	is a restricted hack for a reason.  And even the docstring is 
	contradictory.

	Sort-of.  This now works for intersection and containing.
	Should this reject union?
	>>> s = AllEncompassingSet()
	>>> s & set([1,2])
	set([1, 2])
	>>> "gooble" in s
	True
	>>> s in s
	True
	>>> s not in s
	False
	"""
	def __init__(self):
		set.__init__(self, [])
	
	def __nonzero__(self):
		return True

	def __and__(self, other):
		return other
	
	intersection = __and__

	def __contains__(self, el):
		return True


def iterDerivedClasses(baseClass, objects):
	"""iterates over all subclasses of baseClass in the sequence objects.
	"""
	for cand in objects:
		try:
			if issubclass(cand, baseClass) and cand is not baseClass:
				yield cand
		except TypeError:  # issubclass wants a class
			pass


def iterDerivedObjects(baseClass, objects):
	"""iterates over all instances of baseClass in the sequence objects.
	"""
	for cand in objects:
		if isinstance(cand, baseClass):
			yield cand


def buildClassResolver(baseClass, objects, instances=False,
		key=lambda obj: getattr(obj, "name", None), default=None):
	"""returns a function resolving classes deriving from baseClass
	in the sequence objects by their names.

	This is used to build registries of Macros and RowProcessors.  The
	classes in question have to have a name attribute.

	objects would usually be something like globals().values()

	If instances is True the function will return instances instead
	of classes.

	key is a function taking an object and returning the key under which
	you will later access it.  If this function returns None, the object
	will not be entered into the registry.
	"""
	if instances:
		registry = algotricks.DeferringDict()
	else:
		registry = {}
	for cls in iterDerivedClasses(baseClass, objects):
		clsKey = key(cls)
		if clsKey is not None:
			registry[clsKey] = cls
	def resolve(name, registry=registry):
		try:
			return registry[name]
		except KeyError:
			if default is not None:
				return default
			raise
	resolve.registry = registry
	return resolve


def formatDocs(docItems, underliner):
	"""returns RST-formatted docs for docItems.

	docItems is a list of (title, doc) tuples.  doc is currently
	rendered in a preformatted block.
	"""
	def formatDocstring(docstring):
		"""returns a docstring with a consistent indentation.

		Rule (1): any whitespace in front of the first line is discarded.
		Rule (2): if there is a second line, any whitespace at its front
		  is the "governing whitespace"
		Rule (3): any governing whitespace in front of the following lines
		  is removed
		Rule (4): All lines are indented by 2 blanks.
		"""
		lines = docstring.split("\n")
		newLines = [lines.pop(0).lstrip()]
		if lines:
			whitespacePat = re.compile("^"+re.match(r"\s*", lines[0]).group())
			for line in lines:
				newLines.append(whitespacePat.sub("", line))
		return "  "+("\n  ".join(newLines))

	docLines = []
	for title, body in docItems:
		docLines.extend([title, underliner*len(title), "", "::", "",
			formatDocstring(body), ""])
	docLines.append("\n.. END AUTO\n")
	return "\n".join(docLines)


def makeClassDocs(baseClass, objects):
	"""prints hopefully RST-formatted docs for all subclasses
	of baseClass in objects.

	The function returns True if it finds arguments it expects ("docs"
	and optionally a char to build underlines from) in the command line,
	False if not (and it doesn't print anything in this case) if not.

	Thus, you'll usually use it like this::

		if __name__=="__main__":	
			if not makeClassDocs(Macro, globals().values()):
				_test()
	"""
	if len(sys.argv) in [2,3] and sys.argv[1]=="docs":
		if len(sys.argv)==3:
			underliner = sys.argv[2][0]
		else:
			underliner = "."
	else:
		return False
	docs = []
	for cls in iterDerivedClasses(baseClass, objects):
		try:
			title = cls.name
		except AttributeError:
			title = cls.__name__
		docs.append((title, cls.__doc__))
	docs.sort()
	print formatDocs(docs, underliner)
	return True


@contextlib.contextmanager
def silence(errToo=False):
	"""a context manager to temporarily redirect stdout to /dev/null.

	This is used to shut up some versions of pyparsing and pyfits that
	insist on spewing stuff to stdout from deep within in relatively
	normal situations.
	"""
	realstdout = sys.stdout
	sys.stdout = open("/dev/null", "w")
	if errToo:
		realstderr = sys.stderr
		sys.stderr = sys.stdout

	try:
		yield
	finally:
		sys.stdout.close()
		sys.stdout = realstdout
		if errToo:
			sys.stderr = realstderr 


@contextlib.contextmanager
def in_dir(destDir):
	"""executes the controlled block within destDir and then returns
	to the previous directory.

	Think "within dir".  Haha.
	"""
	owd = os.getcwd()
	os.chdir(destDir)
	try:
		yield owd
	finally:
		os.chdir(owd)


@contextlib.contextmanager
def sandbox(tmpdir=None, debug=False):
	"""sets up and tears down a sandbox directory within tmpdir.

	This is is a context manager.  The object returned is the original
	path (which allows you to copy stuff from there).  The working
	directory is the sandbox created while in the controlled block.

	If tmpdir is None, the *system* default is used (usually /tmp),
	rather than dachs' tmpdir.  So, you will ususally want to call
	this as sandbox(base.getConfig("tempDir"))

	This is obviously not thread-safe -- you'll not usually want
	to run this in the main server process.  Better fork before
	running this.
	"""
	owd = os.getcwd()
	wd = tempfile.mkdtemp("sandbox", dir=tmpdir)
	os.chdir(wd)
	try:
		yield owd
	finally:
		os.chdir(owd)
		if not debug:
			shutil.rmtree(wd)


def runInSandbox(setUp, func, tearDown, *args, **kwargs):
	"""runs func in a temporary ("sandbox") directory.

	func is called with args and kwargs.  setUp and tearDown are
	two functions also called with args and kwargs; in addition, they
	are passed the path of the tempdir (setUp) or the path of the
	original directory (teardown) in the first argument.
	
	setUp is called after the directory has been created,
	but the process is still in the current WD.
	
	tearDown is called before the temp dir is deleted and in this directory.
	Its return value is the return value of runInSandbox, which is the
	preferred way of getting data out of the sandbox.

	If any of the handlers raise exceptions, the following handlers will not
	be called.  The sandbox will be torn down, though.

	This is only present for legacy code.  Use the sandbox context manager
	now.
	"""
	owd = os.getcwd()
	# within DaCHS, this should be within tempDir, but we don't bother to
	# get access to DaCHS' config.  So there.
	wd = tempfile.mkdtemp("sandbox")  
	try:
		if setUp:
			setUp(wd, *args, **kwargs)
		os.chdir(wd)
		func(*args, **kwargs)
		result = tearDown(owd, *args, **kwargs)
	finally:
		os.chdir(owd)
		shutil.rmtree(wd)
	return result


class _FunctionCompiler(object):
	"""A singleton to keep compileFunction's state somewhat localised.

	The state currently is a counter used to build unique ids for
	stuff compiled.
	"""
	compiledCount = 0

	@classmethod
	def _compile(cls, src, funcName, useGlobals=None, debug=False):
		"""runs src through exec and returns the item funcName from the resulting
		namespace.

		This is typically used to define functions, like this:

		>>> resFunc = compileFunction("def f(x): print x", "f")
		>>> resFunc(1); resFunc("abc")
		1
		abc
		"""
		if isinstance(src, unicode):
			src = src.encode("utf-8")
		src = src+"\n"

		locals = {}
		if useGlobals is None:
			useGlobals = globals()

		uniqueName = "<generated code %s>"%cls.compiledCount
		cls.compiledCount += 1

		try:
			code = compile(src, uniqueName, 'exec')
			exec code in useGlobals, locals
		except Exception, ex:
			misctricks.sendUIEvent("Warning", "The code that failed to compile was:"
				"\n%s"%src)
			raise misctricks.logOldExc(excs.BadCode(src, "function", ex))
		func = locals[funcName]

		# this makes our compiled lines available to the traceback writer.
		# we might want to do sys.excepthook = traceback.print_exception
		# somewhere so the post mortem dumper uses this, too.  Let's see
		# if it's worth the added rist of breaking things.
		linecache.cache[uniqueName] = len(src), None, src.split("\n"), uniqueName
		func._cleanup = weakref.ref(func, 
			lambda _, key=uniqueName: linecache.cache.pop(key, None))

		if debug:
			debugLocals = {}
			embSrc = "\n".join([
				"def compileFunctionDebugWrapper(*args, **kwargs):",
				"  try:",
				"    return %s(*args, **kwargs)"%funcName,
				"  except:",
				'    notify("Failing source:\\n%s"%src)',
				"    raise"])
			debugLocals["src"] = src
			debugLocals["notify"] = lambda msg: misctricks.sendUIEvent("Warning", msg)
			debugLocals[funcName] = func
			exec embSrc+"\n" in debugLocals
			return debugLocals["compileFunctionDebugWrapper"]
				
		return func

compileFunction = _FunctionCompiler._compile


def ensureExpression(expr, errName="unknown"):
	"""raises a LiteralParserError if expr is not a parseable python expression.
	"""
	# bizarre bug in the compiler modules: naked strings are compiled into
	# just a module name.  Fix it by forcing an expression on those:
	if expr.startswith("'") or expr.startswith('"'):
		expr = "''+"+expr
	try:
		ast = compiler.parse(expr)
	except SyntaxError, msg:
		raise misctricks.logOldExc(excs.BadCode(expr, "expression", msg))
	# An ast for an expression is a Discard inside at Stmt inside the
	# top-level Module
	try:
		exprNodes = ast.node.nodes
		if len(exprNodes)!=1:
			raise ValueError("Not a single statement")
		if not isinstance(exprNodes[0], compiler.ast.Discard):
			raise ValueError("Not an expression")
	except (ValueError, AttributeError), ex:
		raise misctricks.logOldExc(excs.BadCode(expr, "expression", ex))


def importModule(modName):
	"""imports a module from the module path.

	Use this to programmatically import "normal" modules, e.g., dc-internal
	ones.  It uses python's standard import mechanism and returns the
	module object.

	We're using exec and python's normal import, so the semantics
	should be identical to saying import modName except that the
	caller's namespace is not changed.

	The function returns the imported module.
	"""
	# ward against exploits (we're about to use exec): check syntax
	if not re.match("([A-Za-z_]+)(\.[A-Za-z_]+)*", modName):
		raise excs.Error("Invalid name in internal import: %s"%modName)
	parts = modName.split(".")
	vars = {}
	if len(parts)==1:
		exec "import %s"%modName in vars
	else:
		exec "from %s import %s"%(".".join(parts[:-1]), parts[-1]) in vars
	return vars[parts[-1]]


def loadPythonModule(fqName):
	"""imports fqName and returns the module with a module description.

	The module description is what what find_module returns; you may
	need this for reloading and similar.

	Do not use this function to import DC-internal modules; this may
	mess up singletons since you could bypass python's mechanisms
	to prevent multiple imports of the same module.

	fqName is a fully qualified path to the module without the .py.

	The python path is temporarily amended with the path part of the
	source module.
	"""
	moduleName = os.path.basename(fqName)
	modpath = os.path.dirname(fqName)
	sys.path.append(modpath)

	moddesc = imp.find_module(moduleName, [modpath])
	try:
		imp.acquire_lock()
		modNs = imp.load_module(moduleName, *moddesc)
	finally:
		imp.release_lock()

	try:
		sys.path.append(modpath)
	except IndexError: # don't fail just because someone fudged the path
		pass
	return modNs, moddesc


def loadInternalObject(relativeName, objectName):
	"""gets a name from an internal module.

	relativeName is the python module path (not including "gavo."),
	objectName the name of something within the module.

	This is used for "manual" registries (grammars, cores,...).
	"""
	modName = "gavo."+relativeName
	module = importModule(modName)
	return getattr(module, objectName)


def memoized(origFun):
	"""a trivial memoizing decorator.

	Use this for plain functions; see memoizedMethod for instance methods.
	No cache expiry, no non-hashable arguments, nothing.
	"""
	cache = {}
	def fun(*args):
		if args not in cache:
			cache[args] = origFun(*args)
		return cache[args]
	fun._cache = cache
	return functools.update_wrapper(fun, origFun)


class memoizedMethod(object):
	"""a trivial memoizing decorator for instance methods.

	See memoized for the same thing for functions.  This uses a single
	persistent cache for all instances, so there's not terribly much
	the wrapped method is allowed to do with its self.
	"""
	def __init__(self, meth):
		cache = {}
		@functools.wraps(meth)
		def wrapped(obj, *args):
			try:
				return cache[args]
			except KeyError:
				cache[args] = meth(obj, *args)
				return cache[args]
		self.wrapped = wrapped

	def __get__(self, obj, objtype=None):
		if obj is None:
			return self.wrapped
		return functools.partial(self.wrapped, obj)


def document(origFun):
	"""is a decorator that adds a "buildDocsForThis" attribute to its argument.

	This attribute is evaluated by documentation generators.
	"""
	origFun.buildDocsForThis = True
	return origFun


def iterConsecutivePairs(sequence):
	"""returns pairs of consecutive items from sequence.

	If the last item cannot be paired, it is dropped.

	>>> list(iterConsecutivePairs(range(6)))
	[(0, 1), (2, 3), (4, 5)]
	>>> list(iterConsecutivePairs(range(5)))
	[(0, 1), (2, 3)]
	"""
	iter1, iter2 = iter(sequence), iter(sequence)
	iter2.next()
	return itertools.izip(
		itertools.islice(iter1, None, None, 2),
		itertools.islice(iter2, None, None, 2))


def getKeyNoCase(dict, key):
	"""returns a key of dict matching key case-insensitively.

	This is sometimes useful with protocols that stupidly define keys
	as case-insensitive.

	If no matching key exists, a KeyError is raised.
	"""
	for k in dict:
		if k.lower()==key.lower():
			return k
	raise KeyError(key)


def identity(x):
	return x


def intToFunnyWord(anInt, translation=string.maketrans(
		"-0123456789abcdef", 
		"zaeiousmnthwblpgd")):
	"""returns a sometimes funny (but unique) word from an arbitrary integer.
	"""
	return "".join(reversed(("%x"%anInt).translate(translation)))


def addDefaults(dataDict, defaultDict):
	"""adds key-value pairs from defaultDict to dataDict if the key is missing
	in dataDict.
	"""
	for key, value in defaultDict.iteritems():
		if key not in dataDict:
			dataDict[key] = value


def memoizeOn(onObject, generatingObject, generatingFunction, *args):
	"""memoizes the result of generatingFunction on onObject.

	This is for caching things that adapt to onObjects; see procdefs
	and rowmakers for examples why this is useful.
	"""
	cacheName = "_cache%s%s"%(generatingObject.__class__.__name__, 
		str(id(generatingObject)))
	if getattr(onObject, cacheName, None) is None:
		setattr(onObject, cacheName, generatingFunction(*args))
	return getattr(onObject, cacheName)


def forgetMemoized(ob):
	"""clears things memoizeOn-ed on ob or @utils.memoize-ed.

	This is sometimes necessary to let the garbage collector free
	ob, e.g., when closures have been memoized.
	"""
	for n in dir(ob):
		child = getattr(ob, n)
		# this is for @memoized things
		if hasattr(child, "_cache"):
			child._cache.clear()
		# this is for memoizedOn-ed things
		if n.startswith("_cache"):
			delattr(ob, n)


def stealVar(varName):
	"""returns the first local variable called varName in the frame stack
	above my caller.

	This is obviously abominable.  This is only used within the DC code where
	the author deemed the specification ugly.  Ah.  Almost.
	"""
	frame = inspect.currentframe().f_back.f_back
	while frame:
		if varName in frame.f_locals:
			return frame.f_locals[varName]
		frame = frame.f_back
	raise ValueError("No local %s in the stack"%varName)


def printFrames():
	"""prints a compact list of frames.

	This is an aid for printf debugging.
	"""
	frame = inspect.currentframe().f_back.f_back
	if inspect.getframeinfo(frame)[2]=="getJobsTable":
		return
	while frame:
		print "[%s,%s], [%s]"%inspect.getframeinfo(frame)[:3]
		frame = frame.f_back


def getTracebackAsString():
	import traceback
	f = StringIO()
	traceback.print_exc(file=f)
	return f.getvalue()


def _test():
	import doctest, codetricks
	doctest.testmod(codetricks)


if __name__=="__main__":
	_test()
