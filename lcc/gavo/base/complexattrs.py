"""
Attributes with structure (i.e., containing structures or more than one
atom).

These come with parsers of their own, in some way or other.

Structure attributes, which do not have string literals and have some sort
of internal structure, add methods

	- create(instance, ctx, name) -> structure -- creates a new object suitable
		as attribute value and returns it (for stuctures, instance becomes the
		parent of the new structure as a side effect of this operation).  This 
		is what should later be fed to feedObject.  It must work as a parser,
		i.e., have a feedEvent method. The name argument gives the name of 
		the element that caused the create call, allowing for polymorphic attrs.
	- replace(instance, oldVal, newVal) -> None -- replaces oldVal with newVal; this
		works like feedObject, except that an old value is overwritten.
	- iterEvents(instance) -> events -- yields events to recreate its value
		on another instance.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from gavo.base import attrdef
from gavo.base import common
from gavo.base import literals

__docformat__ = "restructuredtext en"


class CollOfAtomsAttribute(attrdef.AtomicAttribute):
	"""A base class for simple collections of atomic attributes.
	"""
	def __init__(self, name, default=[], 
			itemAttD=attrdef.UnicodeAttribute("listItem"), 
			**kwargs):
		attrdef.AttributeDef.__init__(self, name, 
			default=attrdef.Computed, **kwargs)
		self.xmlName_ = itemAttD.name_
		self.itemAttD = itemAttD
		self.realDefault = default

	def iterEvents(self, instance):
		for item in getattr(instance, self.name_):
			yield ("start", self.xmlName_, None)
			yield ("value", "content_", self.itemAttD.unparse(item))
			yield ("end", self.xmlName_, None)


class ListOfAtomsAttribute(CollOfAtomsAttribute):
	"""is an attribute definition for an item containing many elements
	of the same type.

	It is constructed with an AttributeDef for the items.  Note that it's
	safe to pass in lists as defaults since they are copied before being
	added to the instances, so you won't (and can't) have aliasing here.
	"""

	@property
	def default_(self):
		return self.realDefault[:]

	@property
	def typeDesc_(self):
		return "Zero or more %s-typed *%s* elements"%(
			self.itemAttD.typeDesc_,
			self.itemAttD.name_)
			
	def feed(self, ctx, instance, value):
		getattr(instance, self.name_).append(self.itemAttD.parse(value))

	def feedObject(self, instance, value):
		if isinstance(value, list):
			for item in value:
				self.feedObject(instance, item)
		else:
			getattr(instance, self.name_).append(value)
			self.doCallbacks(instance, value)

	def getCopy(self, instance, newParent):
		return getattr(instance, self.name_)[:]

	def unparse(self, value):
		return unicode(value)


class SetOfAtomsAttribute(CollOfAtomsAttribute):
	"""is an attribute definition for an item containing many elements
	of the same type, when order doesn't matter but lookup times do.

	It is constructed with an AttributeDef for the items.  Note that it's
	safe to pass in lists as defaults since they are copied before being
	added to the instances, so you won't (and can't) have aliasing here.
	"""
	@property
	def default_(self):
		return set(self.realDefault)

	@property
	def typeDesc_(self):
		return "Set of %ss"%self.itemAttD.typeDesc_

	def feed(self, ctx, instance, value):
		getattr(instance, self.name_).add(self.itemAttD.parse(value))

	def feedObject(self, instance, value):
		if isinstance(value, set):
			for item in value:
				self.feedObject(instance, value)
		else:
			getattr(instance, self.name_).add(value)
			self.doCallbacks(instance, value)

	def getCopy(self, instance, newParent):
		return set(getattr(instance, self.name_))


class _DictAttributeParser(common.Parser):
	"""a parser for DictAttributes.

	These need a custom parser since they accept some exotic features, as 
	discussed in DictAttribute's docstring.

	The parser keeps state in the _key and _adding attributes and needs to
	be _reset after use.
	"""
	def __init__(self, dict, nextParser, parseValue, keyName, inverted=False):
		self.dict, self.nextParser, self.parseValue = (
			dict, nextParser, parseValue)
		self.keyName, self.inverted = keyName, inverted
		self._reset()

	def _reset(self):
		self._key, self._adding = attrdef.Undefined, False

	def addPair(self, key, value):
		if self.inverted:
			key, value = value, key
		if self._adding:
			self.dict[key] = self.dict.get(key, "")+value
		else:
			self.dict[key] = value

	def value_(self, ctx, name, value):
		if name=="key" or name==self.keyName:
			self._key = value
		elif name=="cumulate":
			self._adding = literals.parseBooleanLiteral(value)
		elif name=="content_":
			if self._key is attrdef.Undefined:
				raise common.StructureError("Content '%s' has no %s attribute"%(
					value, self.keyName))
			self.addPair(self._key, self.parseValue(value))
			self._reset()
		else:
			raise common.StructureError("No %s attributes on mappings"%name)
		return self
	
	def start_(self, ctx, name, value):
		raise common.StructureError("No %s elements in mappings"%name)
	
	def end_(self, ctx, name, value):
		if self._key is not attrdef.Undefined:
			self.addPair(self._key, None)
			self._reset()
		return self.nextParser


class DictAttribute(attrdef.AttributeDef):
	"""an attribute containing a mapping.

	DictAttributes are fairly complex beasts supporting a number of input
	forms.

	The input to those looks like <d key="foo">abc</d>; they are constructed
	with an itemAttD (like StructAttributes), but the name on those
	is ignored; they are just used for parsing from the strings in the
	element bodies, which means that itemAttDs must be derived from 
	AtomicAttribute.
	
	You can give a different keyNames; the key attribute is always
	accepted, though.

	For sufficiently exotic situations, you can construct DictAttributes
	with inverted=True; the resulting dictionary will then have the keys as 
	values and vice versa (this is a doubtful feature; let us know when
	you use it).

	You can also add to existing values using the cumulate XML attribute;
	<d key="s">a</d><d key="s" cumulate="True">bc</a> will leave
	abc in s.
	"""
	def __init__(self, name, description="Undocumented", 
			itemAttD=attrdef.UnicodeAttribute("value"), 
			keyName="key", 
			inverted=False, **kwargs):
		attrdef.AttributeDef.__init__(self, name, 
			attrdef.Computed, description, **kwargs)
		self.xmlName_ = itemAttD.name_
		self.itemAttD = itemAttD
		self.keyName = keyName
		self.inverted = inverted

	@property
	def typeDesc_(self):
		return "Dict mapping strings to %s"%self.itemAttD.typeDesc_

	@property
	def default_(self):
		return {}

	def feedObject(self, instance, value):
		setattr(instance, self.name_, value)
		self.doCallbacks(instance, value)

	def create(self, parent, ctx, name):
		return _DictAttributeParser(getattr(parent, self.name_), 
			parent, self.itemAttD.parse, keyName=self.keyName,
			inverted=self.inverted)

	def iterEvents(self, instance):
		for key, value in getattr(instance, self.name_).iteritems():
			yield ("start", self.xmlName_, None)
			yield ("value", "key", key)
			yield ("value", "content_", self.itemAttD.unparse(value))
			yield ("end", self.xmlName_, None)
	
	def getCopy(self, instance, newParent):
		return getattr(instance, self.name_).copy()

	def makeUserDoc(self):
		if self.inverted:
			expl = ("the key is the element content, the value is in the 'key'"
				" (or, equivalently, %s) attribute"%self.keyName)
		else:
			expl = ("the value is the element content, the key is in the  'key'"
				" (or, equivalently, %s) attribute"%self.keyName)

		return "**%s** (mapping; %s) -- %s"%(
			 self.xmlName_, expl, self.description_)


class PropertyAttribute(DictAttribute):
	"""adds the property protocol to the parent instance.

	The property protocol consists of the methods 
	- setProperty(name, value),
	- getProperty(name, default=Undefined)
	- clearProperty(name)
	- hasProperty(name)
	
	getProperty works like dict.get, except it will raise a KeyError 
	without a default.

	This is provided for user information and, to some extent, some 
	DC-internal purposes.
	"""
	def __init__(self, description="Properties (i.e., user-defined"
			" key-value pairs) for the element.", **kwargs):
		DictAttribute.__init__(self, "properties", description=description, 
			keyName="name", **kwargs)
		self.xmlName_ = "property"
	
	def iterParentMethods(self):
		def setProperty(self, name, value):
			self.properties[name] = value
		yield "setProperty", setProperty

		def getProperty(self, name, default=attrdef.Undefined):
			if default is attrdef.Undefined:
				return self.properties[name]
			else:
				return self.properties.get(name, default)
		yield "getProperty", getProperty

		def clearProperty(self, name):
			if name in self.properties:
				del self.properties[name]
		yield "clearProperty", clearProperty
		
		def hasProperty(self, name):
			return name in self.properties
		yield "hasProperty", hasProperty

	def makeUserDoc(self):
		return ("**property** (mapping of user-defined keywords in the"
			" name attribute to string values) -- %s"%self.description_)


class StructAttribute(attrdef.AttributeDef):
	"""describes an attribute containing a Structure

	These are constructed with a childFactory that must have a feedEvent
	method.  Otherwise, they are normal structs, i.e., the receive a
	parent as the first argument and keyword arguments for values.
	
	In addition, you can pass a onParentComplete callback that
	are collected in the completedCallback list by the struct decorator.
	ParseableStruct instances call these when they receive their end
	event during XML deserialization.
	"""
	def __init__(self, name, childFactory, default=attrdef.Undefined, 
			description="Undocumented", **kwargs):
		xmlName = kwargs.pop("xmlName", None)
		attrdef.AttributeDef.__init__(self, name, default, description, **kwargs)
		self.childFactory = childFactory
		if xmlName is not None:
			self.xmlName_ = xmlName
		elif self.childFactory is not None:
			self.xmlName_ = self.childFactory.name_
			if getattr(self.childFactory, "aliases", None):
				if self.aliases:
					self.aliases.extend(self.childFactory.aliases)
				else:
					self.aliases = self.childFactory.aliases[:]

	@property
	def typeDesc_(self):
		return getattr(self.childFactory, "docName_", self.childFactory.name_)

	def feedObject(self, instance, value):
		if value and value.parent is None:  # adopt if necessary
			value.parent = instance
		setattr(instance, self.name_, value)
		self.doCallbacks(instance, value)

	def feed(self, ctx, instance, value):
		# if the child factory actually admits content_ (and needs nothing
		# else), allow attributes to be fed in, too.
		if "content_" in self.childFactory.managedAttrs:
			child = self.childFactory(instance, content_=value).finishElement(ctx)
			return self.feedObject(instance, child)

		raise common.LiteralParseError(self.name_,
			value, hint="These attributes have no literals at all, i.e.,"
				" they are for internal use only.")

	def create(self, structure, ctx, name):
		if self.childFactory is attrdef.Recursive:
			res = structure.__class__(structure)
		else:
			res = self.childFactory(structure)
		return res

	def getCopy(self, instance, newParent):
		val = getattr(instance, self.name_)
		if val is not None:
			return val.copy(newParent)
	
	def replace(self, instance, oldStruct, newStruct):
		setattr(instance, self.name_, newStruct)

	def iterEvents(self, instance):
		val = getattr(instance, self.name_)
		if val is common.NotGiven:
			return
		if val is None:
			return
		yield ("start", val.name_, None)
		for ev in val.iterEvents():
			yield ev
		yield ("end", val.name_, None)

	def iterChildren(self, instance):
		if getattr(instance, self.name_) is not None:
			yield getattr(instance, self.name_)

	def remove(self, child):
		setattr(child.parent, self.name_, self.default)

	def onParentComplete(self, val):
		if hasattr(val, "onParentComplete"):
			val.onParentComplete()

	def makeUserDoc(self):
		if self.childFactory is attrdef.Recursive:
			contains = "(contains an instance of the embedding element)"
		else:
			contains = "(contains `Element %s`_)"%self.typeDesc_
		return "%s %s -- %s"%(
			self.name_,  contains, self.description_)


class MultiStructAttribute(StructAttribute):
	"""describes an attribute containing one of a class of Structures.

	This is to support things like grammars or cores -- these can
	be of many types.

	This works like StructAttribute, except that childFactory now is
	a *function* returning elements (i.e., it's a childFactoryFactory).
	"""
	def __init__(self, name, childFactory, childNames, **kwargs):
		StructAttribute.__init__(self, name, None, **kwargs)
		self.childFactory = childFactory
		self.aliases = childNames

	@property
	def typeDesc_(self):
		return ("one of %s"%", ".join(self.aliases))
	
	def create(self, structure, ctx, name):
		res = self.childFactory(name)(structure)
		return res

	def makeUserDoc(self):
		return "%s (contains one of %s) -- %s"%(
			self.name_, ", ".join(self.aliases), self.description_)


class StructListAttribute(StructAttribute):
	"""describes an attribute containing a homogeneous list of structures.
	"""
	def __init__(self, name, childFactory, description="Undocumented",
			**kwargs):
		StructAttribute.__init__(self, name, childFactory, attrdef.Computed,
			description, **kwargs)

	@property
	def default_(self):
		return []

	@property
	def typeDesc_(self):
		if self.childFactory is attrdef.Recursive:
			return "Recursive element list"
		else:
			return "List of %s"%self.childFactory.name_
	
	def feedObject(self, instance, value):
		if isinstance(value, list):
			for item in value:
				self.feedObject(instance, item)
		else:
			if value.parent is None:  # adopt if necessary
				value.parent = instance
			getattr(instance, self.name_).append(value)
			self.doCallbacks(instance, value)
	
	def getCopy(self, instance, newParent):
		res = [c.copy(newParent) for c in getattr(instance, self.name_)]
		return res

	def replace(self, instance, oldStruct, newStruct):
		# This will only replace the first occurrence of oldStruct if
		# multiple identical items are in the list.  Any other behaviour
		# would be about as useful, so let's leave it at this for now.
		curContent = getattr(instance, self.name_)
		ind = curContent.index(oldStruct)
		curContent[ind] = newStruct

	def iterEvents(self, instance):
		for val in getattr(instance, self.name_):
			yield ("start", val.name_, None)
			for ev in val.iterEvents():
				yield ev
			yield ("end", val.name_, None)

	def iterChildren(self, instance):
		return iter(getattr(instance, self.name_))

	def remove(self, child):
		getattr(child.parent, self.name_).remove(child)

	def onParentComplete(self, val):
		if val:
			for item in val:
				if hasattr(item, "onParentComplete"):
					item.onParentComplete()

	def makeUserDoc(self):
		if self.childFactory is attrdef.Recursive:
			contains = "(contains an instance of the embedding element"
		else:
			contains = "(contains `Element %s`_"%self.childFactory.name_
		return ("%s %s and may be repeated zero or more"
			" times) -- %s")%(self.name_, contains, self.description_)


# Ok, so the inheritance here is evil.  I'll fix it if it needs more work.
class MultiStructListAttribute(StructListAttribute, MultiStructAttribute):
	"""describes a list of polymorphous children.

	See rscdesc cores as to why one could want this; the arguments are
	as for MultiStructAttribute.
	"""
	def __init__(self, name, childFactory, childNames, **kwargs):
		StructListAttribute.__init__(self, name, None, **kwargs)
		self.childFactory = childFactory
		self.aliases = childNames

	@property
	def typeDesc_(self):
		return "List of any of %s"%(", ".join(self.aliases))

	def create(self, structure, ctx, name):
		return MultiStructAttribute.create(self, structure, ctx, name)

	def makeUserDoc(self):
		if self.childFactory is attrdef.Recursive:
			contains = "(contains an instance of the embedding element"
		else:
			contains = "(contains any of %s"%",".join(self.aliases)
		return ("%s %s and may be repeated zero or more"
			" times) -- %s")%(self.name_, contains, self.description_)


__all__ = ["ListOfAtomsAttribute", "DictAttribute", "StructAttribute",
	"MultiStructAttribute", "StructListAttribute", "MultiStructListAttribute",
	"SetOfAtomsAttribute", "PropertyAttribute"]
