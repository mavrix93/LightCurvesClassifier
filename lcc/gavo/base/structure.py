"""
Representation of structured data deserializable from XML.

We want all the managed attribute stuff since the main user input comes
from resource descriptors, and we want relatively strong input validation
here.  Also, lots of fancy copying and crazy cross-referencing is
going on in our resource definitions, so we want a certain amount of
rigorous structure.  Finally, a monolithic parser for that stuff
becomes *really* huge and tedious, so I want to keep the XML parsing
information in the constructed objects themselves.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import new

from gavo import utils
from gavo.base import attrdef
from gavo.base import common
from gavo.base import parsecontext


def sortAttrs(attrSeq):
	"""evaluates the before attributes on the AttributeDefs in attrsSeq
	and returns a sequence satisfying them.

	It returns a reference to attrSeq for convenience.
	"""
	beforeGraph = []
	for att in attrSeq:
		if att.before:
			beforeGraph.append((att.name_, att.before))
	if beforeGraph:
		attDict = dict((a.name_, a) for a in attrSeq)
		sortedNames = utils.topoSort(beforeGraph)
		sortedAtts = [attDict[n] for n in sortedNames]
		attrSeq = sortedAtts+list(set(attrSeq)-set(sortedAtts))
	return attrSeq
	

class StructType(type):
	"""is a metaclass for the representation of structured data.

	StructType classes with this will be called structures within
	the DC software.

	Structures do quite a bit of the managed attribute nonsense to
	meaningfully catch crazy user input.

	Basically, you give a Structure class attributes (preferably with
	underscores in front) specifying the attributes the instances
	should have and how they should be handled.

	Structures must be constructed with a parent (for the root
	element, this is None).  All other arguments should be keyword
	arguments.  If given, they have to refer to existing attributes,
	and their values will directly give the the values of the
	attribute (i.e., parsed values).

	Structures should always inherit from StructBase below and
	arrange for its constructor to be called, since, e.g., default
	processing happens there.

	Structures have a managedAttrs dictionary containing names and
	attrdef.AttributeDef objects for the defined attributes.
	"""
	def __init__(cls, name, bases, dict):
		type.__init__(cls, name, bases, dict)
		cls._collectManagedAttrs()
		cls._insertAttrMethods()
	
	def _collectManagedAttrs(cls):
		"""collects a dictionary of managed attributes in managedAttrs.
		"""
		managedAttrs, completedCallbacks, attrSeq = {}, [], []
		for name in dir(cls):
			if not hasattr(cls, name):
				continue
			val = getattr(cls, name)
			if isinstance(val, attrdef.AttributeDef):
				managedAttrs[val.name_] = val
				attrSeq.append(val)
				if hasattr(val, "xmlName_"):
					managedAttrs[val.xmlName_] = val
				if val.aliases:
					for alias in val.aliases:
						managedAttrs[alias] = val
		cls.attrSeq = sortAttrs(attrSeq)
		cls.managedAttrs = managedAttrs
		cls.completedCallbacks = completedCallbacks
	
	def _insertAttrMethods(cls):
		"""adds methods defined by cls's managedAttrs for the parent to
		cls.
		"""
		for val in set(cls.managedAttrs.itervalues()):
			for name, meth in val.iterParentMethods():
				if isinstance(meth, property):
					setattr(cls, name, meth)
				else:
					setattr(cls, name, new.instancemethod(meth, None, cls))


class DataContent(attrdef.UnicodeAttribute):
	"""A magic attribute that allows character content to be added to
	a structure.

	You can configure it with all the arguments available for UnicodeAttribute.

	Since parsers may call characters with an empty string for
	empty elements, the empty string will not be fed (i.e., the default
	will be preserved).  This makes setting an empty string as an element content
	impossible (you could use DataContent with strip=True, though), but that's
	probably not a problem.
	"""
	typeDesc_ = "string"

	def __init__(self, default="", 
			description="Undocumented", **kwargs):
		attrdef.UnicodeAttribute.__init__(self, "content_", default=default, 
			description=description, **kwargs)

	def feed(self, ctx, instance, value):
		if value=='':
			return
		return attrdef.UnicodeAttribute.feed(self, ctx, instance, value)

	def makeUserDoc(self):
		return ("Character content of the element (defaulting to %s) -- %s"%(
			repr(self.default_), self.description_))


class StructureBase(object):
	"""is a base class for all structures.

	You must arrange for calling its constructor from classes inheriting
	this.

	The constructor receives a parent (another structure, or None)
	and keyword arguments containing values for actual attributes
	(which will be set without any intervening consultation of the
	AttributeDef).

	The attribute definitions talking about structures let you
	set parent to None when constructing default values; they will
	then insert the actual parent.
	"""

	__metaclass__ = StructType

	name_ = attrdef.Undefined

	_id = parsecontext.IdAttribute("id", 
		description="Node identity for referencing")

	def __init__(self, parent, **kwargs):
		self.parent = parent
		
		# set defaults
		for val in self.attrSeq:
			try:
				if not hasattr(self, val.name_): # don't clobber properties
				                                 # set up by attributes.
					setattr(self, val.name_, val.default_)
			except AttributeError: # default on property given
				raise utils.logOldExc(common.StructureError(
					"%s attributes on %s have builtin defaults only."%(
						val.name_, self.name_)))
		
		# set keyword arguments
		for name, val in kwargs.iteritems():
			if name in self.managedAttrs:
				if not hasattr(self.managedAttrs[name], "computed_"):
					self.managedAttrs[name].feedObject(self, val)
			else:
				raise common.StructureError("%s objects have no attribute %s"%(
					self.__class__.__name__, name))

	def _nop(self, *args, **kwargs):
		pass

	def getAttributes(self, attDefsFrom=None):
		"""returns a dict of the current attributes, suitable for making
		a shallow copy of self.

		Struct attributes will not be reparented, so there are limits to
		what you can do with such shallow copies.
		"""
		if attDefsFrom is None:
			attrs = set(self.managedAttrs.values())
		else:
			attrs = set(attDefsFrom.managedAttrs.itervalues())
		try:
			return dict([(att.name_, getattr(self, att.name_))
				for att in attrs])
		except AttributeError, msg:
			raise common.logOldExc(common.StructureError(
				"Attempt to copy from invalid source: %s"%unicode(msg)))

	def getCopyableAttributes(self, ignoreKeys=set()):
		"""returns a dictionary mapping attribute names to copyable children.

		ignoreKeys can be a set or dict of additional attribute names to ignore.
		The children are orphan deep copies.
		"""
		return dict((att.name_, att.getCopy(self, None))
			for att in self.attrSeq
				if att.copyable and att.name_ not in ignoreKeys)

	def change(self, **kwargs):
		"""returns a copy of self with all attributes in kwargs overridden with
		the passed values.
		"""
		parent = kwargs.pop("parent_", self.parent)
		attrs = self.getCopyableAttributes(kwargs)
		attrs.update(kwargs)
		return self.__class__(parent, **attrs).finishElement(None)

	def copy(self, parent):
		"""returns a deep copy of self, reparented to parent.
		"""
		return self.__class__(parent, 
			**self.getCopyableAttributes()).finishElement(None)

	def adopt(self, struct):
		struct.parent = self
		return struct

	def iterChildren(self):
		"""iterates over structure children of self.

		To make this work, attributes containing structs must define
		iterChildren methods (and the others must not).
		"""
		for att in self.attrSeq:
			if hasattr(att, "iterChildren"):
				for c in att.iterChildren(self):
					yield c

	@classmethod
	def fromStructure(cls, newParent, oldStructure):
		consArgs = dict([(att.name_, getattr(oldStructure, att.name_))
			for att in oldStructure.attrSeq])
		return cls(newParent, **consArgs)


class ParseableStructure(StructureBase, common.Parser):
	"""is a base class for Structures parseable from EventProcessors (and
	thus XML).
	
	This is still abstract in that you need at least a name_ attribute.
	But it knows how to be fed from a parser, plus you have feed and feedObject
	methods that look up the attribute names and call the methods on the
	respective attribute definitions.
	"""
	_pristine = True

	def __init__(self, parent, **kwargs):
		StructureBase.__init__(self, parent, **kwargs)

	def finishElement(self, ctx):
		return self

	def getAttribute(self, name):
		"""Returns an attribute instance from name.

		This function will raise a StructureError if no matching attribute 
		definition is found.
		"""
		if name in self.managedAttrs:
			return self.managedAttrs[name]
		if name=="content_":
			raise common.StructureError("%s elements must not have character data"
				" content."%(self.name_))
		raise common.StructureError(
			"%s elements have no %s attributes or children."%(self.name_, name))

	def end_(self, ctx, name, value):
		try:
			self.finishElement(ctx)
		except common.Replace, ex:
			if ex.newName is not None:
				name = ex.newName
			if ex.newOb.id is not None:
				ctx.registerId(ex.newOb.id, ex.newOb)
			self.parent.feedObject(name, ex.newOb)
		except common.Ignore, ex:
			pass
		else:
			if self.parent:
				self.parent.feedObject(name, self)
		# del self.feedEvent (at some point we might selectively reclaim parsers)
		return self.parent

	def value_(self, ctx, name, value):
		attDef = self.getAttribute(name)
		try:
			attDef.feed(ctx, self, value)
		except common.Replace, ex:
			return ex.newOb
		self._pristine = False
		return self
	
	def start_(self, ctx, name, value):
		attDef = self.getAttribute(name)
		if hasattr(attDef, "create"):
			return attDef.create(self, ctx, name)
		else:
			return name

	def feed(self, name, literal, ctx=None):
		"""feeds the literal to the attribute name.

		If you do not have a proper parse context ctx, so there
		may be restrictions on what literals can be fed.
		"""
		self.managedAttrs[name].feed(ctx, self, literal)
	
	def feedObject(self, name, ob):
		"""feeds the object ob to the attribute name.
		"""
		self.managedAttrs[name].feedObject(self, ob)

	def iterEvents(self):
		"""yields an event sequence that transfers the copyable information
		from self to something receiving the events.

		If something is not copyable, it is ignored (i.e., keeps its default
		on the target object).
		"""
		for att in self.attrSeq:
			if not att.copyable:
				continue
			if hasattr(att, "iterEvents"):
				for ev in att.iterEvents(self):
					yield ev
			else:
				val = getattr(self, att.name_)
				if val!=att.default_:  
					yield ("value", att.name_, att.unparse(val))

	def feedFrom(self, other, ctx=None, suppress=set()):
		"""feeds parsed objects from another structure.

		This only works if the other structure is a of the same or a superclass
		of self.
		"""
		from gavo.base import xmlstruct
		if ctx is None:
			ctx = parsecontext.ParseContext()
		evProc = xmlstruct.EventProcessor(None, ctx)
		evProc.setRoot(self)
		for ev in other.iterEvents():
			evProc.feed(*ev)


class Structure(ParseableStructure):
	"""is the base class for user-defined structures.

	It will do some basic validation and will call hooks to complete elements
	and compute computed attributes, based on ParseableStructure's finishElement
	hook.

	Also, it supports onParentComplete callbacks; this works by checking
	if any managedAttr has a onParentComplete method and calling it
	with the current value of that attribute if necessary.
	"""
	def callCompletedCallbacks(self):
		for attName, attType in self.managedAttrs.iteritems():
			if hasattr(attType, "onParentComplete"):
				attVal = getattr(self, attType.name_)
				if attVal!=attType.default_:
					attType.onParentComplete(attVal)

	def finishElement(self, ctx=None):
		self.completeElement(ctx)
		self.validate()
		self.onElementComplete()
		self.callCompletedCallbacks()
		return self

	def _makeUpwardCaller(methName):
		def _callNext(self, cls):
			try:
				pc = getattr(super(cls, self), methName)
			except AttributeError:
				pass
			else:
				pc()
		return _callNext

	def _makeUpwardCallerOneArg(methName):
		def _callNext(self, cls, arg):
			try:
				pc = getattr(super(cls, self), methName)
			except AttributeError:
				pass
			else:
				pc(arg)
		return _callNext

	def completeElement(self, ctx):
		self._completeElementNext(Structure, ctx)

	_completeElementNext = _makeUpwardCallerOneArg("completeElement")

	def validate(self):
		for val in set(self.managedAttrs.itervalues()):
			if getattr(self, val.name_) is attrdef.Undefined:
				raise common.StructureError("You must set %s on %s elements"%(
					val.name_, self.name_))
			if hasattr(val, "validate"):
				val.validate(self)
		self._validateNext(Structure)

	_validateNext = _makeUpwardCaller("validate")

	def onElementComplete(self):
		self._onElementCompleteNext(Structure)

	_onElementCompleteNext = _makeUpwardCaller("onElementComplete")


class RestrictionMixin(object):
	"""A mixin for structure classes not allowed in untrusted RDs.
	"""
	def completeElement(self, ctx):
		if getattr(ctx, "restricted", False):
			raise common.RestrictedElement(self.name_)
		self._completeElementNext(RestrictionMixin, ctx)


def makeStruct(structClass, **kwargs):
	"""creates a parentless instance of structClass with **kwargs, going
	through all finishing actions.

	You can pass in a parent_ kwarg to force a parent.
	"""
	parent = None
	if "parent_" in kwargs:
		parent = kwargs.pop("parent_")
	return structClass(parent, **kwargs).finishElement(None)
