"""
ParseContexts for parsing into structures.

A Context is a scratchpad for struct parsing.  It always provides an idmap, but
you're free to insert additional attributes.

Based on this, we provide some attribute definitions.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from gavo import utils
from gavo.base import attrdef
from gavo.base import caches
from gavo.base import common


def assertType(id, ob, forceType):
	"""raises a StructureError if forceType is not None and ob is not of
	type forceType, returns ob otherwise.
	"""
	if forceType:
		if not isinstance(ob, forceType):
			raise common.StructureError("Reference to '%s' yielded object of type"
				" %s, expected %s"%(id, ob.__class__.__name__, 
				forceType.__name__))
	return ob


def resolveCrossId(id, forceType=None):
	"""resolves id, where id is of the form rdId#id.
	"""
	try:
		rdId, rest = id.split("#")
	except ValueError:
		raise common.LiteralParseError("id", id, hint="There must be exactly"
			" one hash sign ('#') in cross ids, separating the rd identifier"
			" from the rd-internal id")

	try:
		srcRd = caches.getRD(rdId)
	except common.RDNotFound:
		raise common.NotFoundError(id, "Element with id", "RD "+rdId,
			hint="The RD referenced cannot be opened")
	return resolveId(srcRd, rest, forceType=forceType)


def resolveNameBased(container, id, forceType=None):
	"""Tries to find a thing with name id within container.

	If container defines a method getElementForName, it will be called; it
	must either return some element with this name or raise a NotFoundError.

	If no such method exists, the function iterates over container until
	it finds an element with el.name==id.  If no such element exists,
	it again raises a NotFoundError.

	The function raises a NotFoundError when no such thing exists.
	"""
	if hasattr(container, "getElementForName"):
		return container.getElementForName(id)
	
	ob = None
	try:
		for ob in container:
			if hasattr(ob, "name") and ob.name==id:
				return assertType(id, ob, forceType)
	except TypeError:
		if ob is None:
			raise utils.logOldExc(common.NotFoundError(id, "Element with name",
				"container %s"%repr(container),
				hint="The container, %s, is not iterable"%repr(container)))
		else:
			raise utils.logOldExc(common.NotFoundError(id, "Element with name",
				"container %s"%repr(container),
				hint="Element %s is of type %s and thus unsuitable"
					" for name path"%(ob.name, type(ob))))
	raise common.NotFoundError(id, "Element with name",
		"container %s"%container.id)


def resolveComplexId(ctx, id, forceType=None):
	"""resolves a dotted id.

	See resolveId.
	"""
	try:
		pId, name = id.split(".")
	except ValueError:
		raise utils.logOldExc(common.LiteralParseError("id", id, 
			hint="A complex reference (parent.name) is expected here"))
	container = ctx.getById(pId)
	return resolveNameBased(container, name, forceType)


def _resolveOnNamepath(ctx, id, instance):
	if hasattr(instance, "resolveName"):
		return instance.resolveName(ctx, id)
	if (instance and instance.parent and 
			hasattr(instance.parent, "resolveName")):
		return instance.parent.resolveName(ctx, id)
	raise common.NotFoundError(id, "Element with id or name", "name path")


def resolveId(ctx, id, instance=None, forceType=None):
	"""tries to resolve id in context.

	ctx is some object having a getById method; this could be an RD
	or a parse context.

	The rules for id are as follows:

	(#) if id has a # in it, split it and take the first part to be
	an RD id, the second and id built according to the rest of this spec.

	(#) if id has a dot in it, split at the first dot to get a pair of
	id and name.  Iterate over the element with id, and look for something
	with a "name" attribute valued name.  If this fails, raise a 
	NotFoundError.

	(#) if instance is not None and has a resolveName method or has a parent, and
	that parent has a resolveName method, pass id to it.  If it does not raise a
	NotFoundError, return the result.  This is for parents with a
	rscdef.NamePathAttribute.

	(#) ask the ParseContext ctx's getById method to resolve id, not
	catching the NotFoundError this will raise if the id is not known.
	"""
	if "#" in id:
		return resolveCrossId(id, forceType)
	if ctx is None:
		raise common.StructureError("Cannot intra-reference when parsing without"
			" a context")
	if "." in id:
		return resolveComplexId(ctx, id, forceType)

	srcOb = None
	if instance:
		try:
			srcOb = _resolveOnNamepath(ctx, id, instance)
		except common.NotFoundError:  
			# no such named element, try element with id
			pass
	if srcOb is None and ctx is not None:
		srcOb = ctx.getById(id, forceType)
	return assertType(id, srcOb, forceType)


class IdAttribute(attrdef.UnicodeAttribute):
	"""is an attribute that registers its parent in the context's id map
	in addition to setting its id attribute.
	"""
	def feed(self, ctx, parent, literal):
		attrdef.UnicodeAttribute.feed(self, ctx, parent, literal)
		if ctx is not None:
			ctx.registerId(parent.id, parent)
			parent.qualifiedId = ctx.getQualifiedId(literal)
	
	def getCopy(self, parent, newParent):
		return None  # ids may not be copied

	def makeUserDoc(self):
		return None  # don't mention it in docs -- all structures have it


class OriginalAttribute(attrdef.AtomicAttribute):
	"""is an attribute that resolves an item 	copies over the managed 
	attributes from the referenced item.
	
	The references may be anything resolveId can cope with.

	You can pass a forceType argument to make sure only references to
	specific types are allowable.  In general, this will be the class
	itself of a base class.  If you don't do this, you'll probably get
	weird AttributeErrors for certain inputs.

	To work reliably, these attributes have to be known to the XML
	parser so it makes sure they are processed first.  This currently
	works by name, and "original" is reserved for this purpose.  Other
	names will raise an AssertionError right now.

	As a safety mechanism, OriginalAttribute checks if it is replacing
	a "pristine" object, i.e. one that has not had events fed to it.
	"""
	computed_ = True
	typeDesc_ = "id reference"

	def __init__(self, name="original", description="An id of an element"
			" to base the current one on.  This provides a simple inheritance"
			" method.  The general rules for advanced referencing in RDs apply.", 
			forceType=None, **kwargs):
		assert name=='original'
		attrdef.AtomicAttribute.__init__(self, name, None, description,
			**kwargs)
		self.forceType = forceType

	def feedObject(self, instance, original, ctx=None):
		if not instance._pristine:
			raise common.StructureError("Original must be applied before modifying"
				" the destination structure.", hint="You should normally use"
				" original only as attribute.  If you insist on having it as"
				" an element, it must be the first one and all other structure"
				" members must be set through elements, too")
		instance._originalObject = original 
		instance.feedFrom(original, ctx)

	def feed(self, ctx, instance, literal):
		self.feedObject(instance,
			resolveId(ctx, literal, instance, self.forceType), ctx)


class _ReferenceParser(common.Parser):
	"""A helper class for the ReferenceAttribute.
	"""
	def __init__(self, refAttr, parent, baseName):
		self.refAttr, self.parent = refAttr, parent
		self.child = common.NotGiven
		self.baseName = baseName

	def _setNewChild(self):
		"""creates an instance of the new, immediate child to be filled and
		leaves it in self.child.
		"""
		self.child = self.refAttr._makeChild(self.baseName, self.parent)

	def start_(self, ctx, name, value):
		# start event: we have an immediate child.  Create it and feed this
		# event to the newly created child.
		self._setNewChild() 
		return self.child.feedEvent(ctx, "start", name, value)
	
	def end_(self, ctx, name, value):
		if self.child is common.NotGiven:  # empty element; make a child
			self._setNewChild()
		if self.child is not None: # immediate child was given:
			self.child.finishElement(ctx)
			self.parent.feedObject(name, self.child)
		return self.parent
	
	def value_(self, ctx, name, value):
		# value event: If it's a content_, it's a reference, else it's an
		# attribute on a child of ours.
		if name=="content_":
			self.refAttr.feed(ctx, self.parent, value)
			self.child = None
			return self
		else:
			self._setNewChild()
			return self.child.feedEvent(ctx, "value", name, value)


class ReferenceAttribute(attrdef.AtomicAttribute):
	"""An attribute keeping a reference to some other structure

	This is a bit messy since the value referred to keeps its original
	parent, so self.attr.parent!=self for these attributes.  This is
	ok for many applications, but it will certainly not work for, e.g.
	tables (roughly, it's always trouble when an attribute value's 
	implementation refers to self.parent; this is particularly true
	for structures having an RDAttribute).

	So, before adding a reference attribute, think first whether
	it wouldn't be wiser to have the real thing and use original to copy
	things over.
	"""
	typeDesc_ = "id reference"

	def __init__(self, name="ref", default=attrdef.Undefined,
			description="Uncodumented", forceType=None, **kwargs):
		attrdef.AtomicAttribute.__init__(self, name, default,
			description, **kwargs)
		self.forceType = forceType

	def _getForceType(self, instance):
		"""returns self.forceType unless it is Recursive, in which case instance's
		type is returned.
		"""
		if self.forceType is attrdef.Recursive:
			return instance.__class__
		else:
			return self.forceType

	def unparse(self, value):
		if value is None:  # ref attribute was empty
			return None
		if hasattr(value, "qualifiedId"):
			return value.qualifiedId
		elif isinstance(value, basestring):
			return value
		else: # See HACK notice in feed
			setattr(value, "unparse-approved-anonymous", True)
			return value

# Since ReferenceAttributes can now contain immediate elements,
# just returning an id (as happens by default) may not be enough
# for serialization -- the immediate object is nowhere else.
#  We could fix that using something like this, at the expense
# of unrolling all the elements.  We don't do much DC structure
# serialization, and thus I believe it's just not worth it.
#	def iterEvents(self, instance):
#		# This needs a special iterEvents to actually return embedded
#		# structures if necessary
#		val = getattr(instance, self.name_)
#		if val==self.default_:
#			return
#	
#		if hasattr(val, "_RefAttrImmediate"):
#			yield ("start", self.name_, None)
#			for ev in val.iterEvents():
#				yield ev
#			yield ("end", self.name_, None)
#		else:
#			yield ("value", self.name_, self.unparse(val))

	def feed(self, ctx, instance, literal):
		if literal is None: # ref attribute empty during a copy
			return            # do nothing, since nothing was ref'd in original

		# HACK: when copying around structures, it's possible that anonymous
		# structures can be fed in here.  We *really* don't want to make
		# up ids for them.  Thus, we allow them out in unparse and in here
		# again.
		if hasattr(literal, "unparse-approved-anonymous"):
			self.feedObject(instance, literal)
		else:
			self.feedObject(instance,
				resolveId(ctx, literal, instance, self._getForceType(instance)))

	def _makeChild(self, name, parent):
		"""returns a new element of the appropriate type.

		This method raises a StructureError if that type is not known.
		Within ReferenceAttribute, the type is given by forceType.
		"""
		if self.forceType is None:
			raise common.StructureError("Only references allowed for %s, but"
				" an immediate object was found"%self.name_, 
				hint="This means that"
				" you tried to replace a reference to an element with"
				" the element itself.  This is only allowed if the reference"
				" forces a type, which is not the case here.")
		child = self._getForceType(parent)(parent)
		# leave a sentinel in the child that will later let us
		# iterEvents not the id but the struct itself.
		child._RefAttrImmediate = True
		return child

	def create(self, structure, ctx, name):
		# we don't know at this point whether or not the next event will be
		# an open (-> create a new instance of self.forceType) or a
		# value (-> resolve).  Thus, create an intermediate parser that
		# does the right thing.
		return _ReferenceParser(self, structure, name)


class ReferenceListAttribute(ReferenceAttribute):
	"""A list of references.

	These can come as distinct elements -- <ref>a</ref><ref>b</ref> -- or
	as a comma-joined string with ignored whitespace --
	ref="a, //services#b, x.y", or in a mixture between the two.
	"""
	typeDesc_ = "list of id references (comma separated or in distinct elements)"

	def __init__(self, name, **kwargs):
		if kwargs.get("default") is not None:
			raise common.StructureError("ReferenceListAttributes cannot have"
				" defaults")
		kwargs["default"] = attrdef.Computed
		ReferenceAttribute.__init__(self, name, **kwargs)

	@property
	def default_(self):
		return []

	def feedObject(self, instance, value):
		if isinstance(value, list):
			for item in value:
				self.feedObject(instance, item)
		else:
			getattr(instance, self.name_).append(value)
			self.doCallbacks(instance, value)

	def feed(self, ctx, instance, literal):
		# split literal up if there's commas
		if literal is None: # see ReferenceAttribute.feed
			return
		if "," in literal:
			for s in literal.split(","):
				ReferenceAttribute.feed(self, ctx, instance, s.strip())
		else:
				ReferenceAttribute.feed(self, ctx, instance, literal)

	def unparse(self, value):
		# Hack to avoid to have to figure out globally ok ids; see 
		# comments in ReferenceAttribute
		class BlessedList(list):
			pass
		setattr(BlessedList, "unparse-approved-anonymous", True)
		return BlessedList(value)


class ParseContext(object):
	"""is a scratchpad for any kind of data parsers want to pass to feed
	methods.

	These objects are available to the feed methods as their
	first objects.

	If restricted is True, embedded code must raise an error.

	You should set an eventSource using the setter provided.  This is
	the iterparse instance the events are coming from (or something else
	that has a pos attribute returning the current position).

	You can register exit functions to do some "global" cleanup.  Parsers 
	should call runExitFuncs right before they return the results; this arranges
	for these functions to be called.  The signature of an exit function is
	exitfunc(rootStruct, parseContext) -> whatever.
	"""
	def __init__(self, restricted=False, forRD=None):
		self.idmap = {}
		self.restricted = restricted
		self.forRD = forRD
		self.eventSource = None
		self.exitFuncs = []

	def setEventSource(self, evSource):
		self.eventSource = evSource

	def addExitFunc(self, callable):
		self.exitFuncs.append(callable)

	@property
	def pos(self):
		"""returns a token stringifying into a position guess.
		"""
		if self.eventSource is None:
			return "(while parsing sourceless)"
		else:
			return self.eventSource.pos

	def getQualifiedId(self, id):
		"""returns an id including the current RD's id, if known, otherwise id
		itself.
		"""
		if self.forRD:
			return "%s#%s"%(self.forRD, id)
		return id

	def registerId(self, elId, value):
		"""enters a value in the id map.

		We allow overriding in id.  That should not happen while parsing
		and XML document because of their uniqueness requirement, but
		might come in handy for programmatic manipulations.
		"""
		self.idmap[elId] = value
	
	def getById(self, id, forceType=None):
		"""returns the object last registred for id.

		You probably want to use resolveId; getById does no namePath or
		resource descriptor resolution.
		"""
		if id not in self.idmap:
			raise common.NotFoundError(id, "Element with id", "parse context",
				hint="Elements referenced must occur lexically (i.e., within the"
					" input file) before the reference.  If this actually gives"
					" you trouble, contact the authors.  Usually, though, this"
					" error just means you mistyped a name.")
		res = self.idmap[id]
		return assertType(id, res, forceType)

	def resolveId(self, id, instance=None, forceType=None):
		"""returns the object referred to by the complex id.

		See the resolveId function.
		"""
		return resolveId(self, id, instance, forceType)
	
	def runExitFuncs(self, root):
		for func in self.exitFuncs:
			func(root, self)
