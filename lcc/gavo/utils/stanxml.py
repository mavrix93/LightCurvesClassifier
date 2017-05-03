"""
A stan-like model for building namespaced XML trees.

The main reason for this module is that much of the VO's XML mess is based
on XML schema and thus has namespaced attributes.  This single design
decision ruins the entire XML design.  To retain some rests of
sanity, I treat the prefixes themselves as namespaces and maintain
a single central registry from prefixes to namespaces in this module.

Then, the elements only use these prefixes, and this module makes sure
that during serialization the instance document's root element contains
the namespace mapping (and the schema locations) required.
"""

#c Copyright 2008-2016, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from cStringIO import StringIO

try:
	from xml.etree import cElementTree as ElementTree
except ImportError:
	from elementtree import ElementTree #noflake: conditional import

from gavo.utils import autonode
from gavo.utils import excs
from gavo.utils import misctricks
from gavo.utils import texttricks

class Error(Exception):
	pass


class ChildNotAllowed(Error):
	pass


encoding = "utf-8"
XML_HEADER = '<?xml version="1.0" encoding="%s"?>'%encoding


class _Autoconstructor(autonode.AutoNodeType):
	"""A metaclass used for Elements.

	On the one hand, it does autonode's constructor magic with _a_<attrname>
	attributes, on the other, it will instanciate itself when indexed
	-- that we want for convenient stan-like notation.
	"""
	def __init__(cls, name, bases, dict):
		autonode.AutoNodeType.__init__(cls, name, bases, dict)
		if hasattr(cls, "_childSequence") and cls._childSequence is not None:
			cls._allowedChildren = set(cls._childSequence)
		else:
			cls._childSequence = None

	def __getitem__(cls, items):
		return cls()[items]


class Stub(object):
	"""A sentinel class for embedding objects not yet existing into
	stanxml trees.

	These have a single opaque object and need to be dealt with by the
	user.  One example of how these can be used is the ColRefs in stc to
	utype conversion.

	Stubs are equal to each othter if their handles are identical.
	"""
	name_ = "stub"
	text_ = None

	def __init__(self, dest):
		self.dest = dest

	def __repr__(self):
		return "%s(%s)"%(self.__class__.__name__, repr(self.dest))

	def __eq__(self, other):
		return self.dest==getattr(other, "dest", Stub)
	
	def __ne__(self, other):
		return not self==other

	def __hash__(self):
		return hash(self.dest)

	def isEmpty(self):
		return False

	def shouldBeSkipped(self):
		return False

	def getChildDict(self):
		return {}

	def iterAttNames(self):
		if False:
			yield

	def apply(self, func):
		"""does nothing.

		Stubs don't have what Element.apply needs, so we don't even pretend.
		"""
		return


class Element(object):
	"""An element for serialization into XML.

	This is loosely modelled after nevow stan.

	Don't add to the children attribute directly, use addChild or (more
	usually) __getitem__.

	Elements have attributes and children.  The attributes are defined,
	complete with defaults, in _a_<name> attributes as in AutoNodes.
	Attributes are checked.

	Children are not usually checked, but you can set a _childSequence
	attribute containing a list of (unqualified) element names.  These
	children will be emitted in the sequence given.
	
	When deriving from Elements, you may need attribute names that are not
	python identifiers (e.g., with dashes in them).  In that case, define
	an attribute _name_a_<att> and point it to any string you want as the
	attribute.

	When serializing these, empty elements (i.e. those having an empty text and
	having no non-empty children) are usually discarded.  If you need such an
	element (e.g., for attributes), set mayBeEmpty to True.

	Since insane XSD mandates that local elements must not be qualified when
	elementFormDefault is unqualified, you need to set _local=True on
	such local elements to suppress the namespace prefix.  Attribute names
	are never qualified here.  If you need qualified attributes, you'll
	have to use attribute name translation.

	The content of the DOM may be anything recognized by addChild.
	In particular, you can give objects a serializeToXMLStan method returning
	strings or an Element to make them good DOM citizens.

	Elements cannot harbor mixed content (or rather, there is only
	one piece of text).
	"""
	__metaclass__ = _Autoconstructor

	name_ = None
	_a_id = None
	_prefix = ""
	_additionalPrefixes = frozenset()
	_mayBeEmpty = False
	_local = False
	_stringifyContent = False

	# should probably do this in the elements needing it (quite a lot of them
	# do, however...)
	_name_a_xsi_type = "xsi:type"

	# for type dispatching in addChild.
	_generator_t = type((x for x in ()))

	# see _setupNode below for __init__

	def __getitem__(self, children):
		self.addChild(children)
		return self

	def __call__(self, **kw):
		if not kw:
			return self
	
		# XXX TODO: namespaced attributes?
		for k, v in kw.iteritems():
			# Only allow setting attributes already present
			getattr(self, k)
			setattr(self, k, v)
		return self

	def __iter__(self):
		raise NotImplementedError("Element instances are not iterable.")

	def __nonzero__(self):
		return self.isEmpty()

	def _setupNodeNext(self, cls):
		try:
			pc = super(cls, self)._setupNode
		except AttributeError:
			pass
		else:
			pc()

	def _setupNode(self):
		self._isEmptyCache = None
		self._children = []
		self.text_ = ""
		if self.name_ is None:
			self.name_ = self.__class__.__name__.split(".")[-1]
		self._setupNodeNext(Element)

	def _makeAttrDict(self):
		res = {}
		for name, attName in self.iterAttNames():
			if getattr(self, name, None) is not None:
				res[attName] = unicode(getattr(self, name))
		return res

	def _iterChildrenInSequence(self):
		cDict = self.getChildDict()
		for cName in self._childSequence:
			if cName in cDict:
				for c in cDict[cName]:
					yield c

	def bailIfBadChild(self, child):
		if (self._childSequence is not None 
				and getattr(child, "name_", None) not in self._allowedChildren 
				and type(child) not in self._allowedChildren):
			raise ChildNotAllowed("No %s children in %s"%(
				getattr(child, "name_", "text"), self.name_))

	def deepcopy(self):
		"""returns a deep copy of self.
		"""
		copy = self.__class__(**self._makeAttrDict())
		for child in self.iterChildren():
			if isinstance(child, Element):
				copy.addChild(child.deepcopy())
			else:
				copy.addChild(child)
		return copy

	def addChild(self, child):
		"""adds child to the list of children.

		Child may be an Element, a string, or a list or tuple of Elements and
		strings.  Finally, child may be None, in which case nothing will be
		added.
		"""
		self._isEmptyCache = None
		if child is None:
			pass
		elif hasattr(child, "serializeToXMLStan"):
			self.addChild(child.serializeToXMLStan())
		elif isinstance(child, basestring):
			self.bailIfBadChild(child)
			self.text_ = child
		elif isinstance(child, (Element, Stub)):
			self.bailIfBadChild(child)
			self._children.append(child)
		elif isinstance(child, (list, tuple, self._generator_t)):
			for c in child:
				self.addChild(c)
		elif isinstance(child, _Autoconstructor):
			self.addChild(child())
		elif self._stringifyContent:
			self.addChild(unicode(child))
		else:
			raise Error("%s element %s cannot be added to %s node"%(
				type(child), repr(child), self.name_))

	def isEmpty(self):
		"""returns true if the current node has no non-empty children and no
		non-whitespace text content.
		"""
		if self._isEmptyCache is None:
			self._isEmptyCache = True

			if self.text_.strip():
				self._isEmptyCache = False
			if self._isEmptyCache:
				for c in self._children:
					if not c.shouldBeSkipped():
						self._isEmptyCache = False
						break

		return self._isEmptyCache

	def shouldBeSkipped(self):
		"""returns true if the current node should be part of an output.

		That is true if it is either non-empty or _mayBeEmpty is true.
		An empty element is one that has only empty children and no
		non-whitespace text content.
		"""
		if self._mayBeEmpty:
			return False
		return self.isEmpty()

	def iterAttNames(self):
		"""iterates over the defined attribute names of this node.
		
		Each element returned is a pair of the node attribute name and the 
		xml name (which may be translated via _a_name_<att>
		"""
		for name, default in self._nodeAttrs:
			xmlName = getattr(self, "_name_a_"+name, name)
			yield name, xmlName

	def addAttribute(self, attName, attValue):
		"""adds attName, attValue to this Element's attributes when instanciated.

		You cannot add _a_<attname> attributes to instances.  Thus, when
		in a pinch, use this.
		"""
		attName = str(attName)
		if not hasattr(self, attName):
			self._nodeAttrs.append((attName, attValue))
		setattr(self, attName, attValue)

	def iterChildrenOfType(self, type):
		"""iterates over all children having type.
		"""
		for c in self._children:
			if isinstance(c, type):
				yield c

	def iterChildren(self):
		return iter(self._children)

	def getChildDict(self):
		cDict = {}
		for c in self._children:
			cDict.setdefault(c.name_, []).append(c)
		return cDict
	
	def iterChildrenWithName(self, elName):
		"""iterates over children whose element name is elName.

		This always does a linear search through the children and hence
		may be slow.
		"""
		for c in self._children:
			if c.name_==elName:
				yield c
		
	def _getChildIter(self):
		if self._childSequence is None:
			return iter(self._children)
		else:
			return self._iterChildrenInSequence()

	def apply(self, func):
		"""calls func(node, text, attrs, childIter).

		This is a building block for tree traversals; the expectation is that 
		func does something like func(node, text, attrDict, childSequence).
		"""
		try:
			if self.shouldBeSkipped():
				return
			attrs = self._makeAttrDict()
			return func(self, self.text_,
				attrs, self._getChildIter())
		except Error:
			raise
		except Exception:
			misctricks.sendUIEvent("Info",
				"Internal failure while building XML; context is"
				" %s node with children %s"%(
					self.name_, 
					texttricks.makeEllipsis(repr(self._children), 60)))
			raise

	def asETree(self, prefixForEmpty=None):
		"""returns an ElementTree instance for the tree below this node.

		Deprecated.  Use Serializer rather than ElementTree.
		"""
		return DOMMorpher(prefixForEmpty, NSRegistry).getMorphed(self)

	def render(self, prefixForEmpty=None, includeSchemaLocation=True):
		"""returns this and its children as a string.
		"""
		f = StringIO()
		write(self, f, prefixForEmpty=prefixForEmpty, xmlDecl=False,
			includeSchemaLocation=includeSchemaLocation)
		return f.getvalue()


class NSRegistry(object):
	"""A container for a registry of namespace prefixes to namespaces.

	This is used to have fixed namespace prefixes (IMHO the only way
	to have namespaced attribute values and retain sanity).  The
	class is never instanciated.  It is used through the module-level
	method registerPrefix and by DOMMorpher.
	"""
	_registry = {}
	_reverseRegistry = {}
	_schemaLocations = {}

	@classmethod
	def registerPrefix(cls, prefix, ns, schemaLocation):
		if prefix in cls._registry:
			if ns!=cls._registry[prefix]:
				raise ValueError("Prefix %s is already allocated for namespace %s"%
					(prefix, ns))
		cls._registry[prefix] = ns
		cls._reverseRegistry[ns] = prefix
		cls._schemaLocations[prefix] = schemaLocation

	@classmethod
	def getPrefixForNS(cls, ns):
		try:
			return cls._reverseRegistry[ns]
		except KeyError:
			raise excs.NotFoundError(ns, "XML namespace",
				"registry of XML namespaces.", hint="The registry is filled"
				" by modules as they are imported -- maybe you need to import"
				" the right module?")

	@classmethod
	def getNSForPrefix(cls, prefix):
		try:
			return cls._registry[prefix]
		except KeyError:
			raise excs.NotFoundError(prefix, "XML namespace prefix",
				"registry of prefixes.", hint="The registry is filled"
				" by modules as they are imported -- maybe you need to import"
				" the right module?")
	
	@classmethod
	def _iterNSAttrs(cls, prefixes, prefixForEmpty, includeSchemaLocation):
		"""iterates over pairs of (attrName, attrVal) for declaring
		prefixes.
		"""
		# null prefixes are ignored here; prefixForEmpty, if non-null, gives
		# the prefix the namespace would normally be bound to.
		prefixes.discard("")

		schemaLocations = []
		for pref in sorted(prefixes):
			yield "xmlns:%s"%pref, cls._registry[pref]
			if includeSchemaLocation and cls._schemaLocations[pref]:
				schemaLocations.append("%s %s"%(
					cls._registry[pref],
					cls._schemaLocations[pref]))

		if prefixForEmpty:
			yield "xmlns", cls._registry[prefixForEmpty]

		if schemaLocations:
			if not "xsi" in prefixes:
				yield "xmlns:xsi", cls._registry["xsi"]
			yield "xsi:schemaLocation", " ".join(schemaLocations)

	@classmethod
	def addNamespaceDeclarationsETree(cls, root, prefixes, prefixForEmpty=None,
			includeSchemaLocation=True):
		"""adds xmlns declarations for prefixes to the etree node root.

		With stanxml and the global-prefix scheme, xmlns declarations
		only come at the root element; thus, root should indeed be root
		rather than some random element.

		Deprecated, don't use ElementTree with stanxml any more.
		"""
		for attName, attVal in cls._iterNSAttrs(prefixes, prefixForEmpty,
				includeSchemaLocation):
			root.attrib[attName] = attVal

	@classmethod
	def addNamespaceDeclarations(cls, root, prefixes, prefixForEmpty=None,
			includeSchemaLocation=True):
		"""adds xmlns declarations for prefixes to the stanxml node root.

		With stanxml and the global-prefix scheme, xmlns declarations
		only come at the root element; thus, root should indeed be root
		rather than some random element.
		"""
		for attName, attVal in cls._iterNSAttrs(prefixes, prefixForEmpty,
				includeSchemaLocation):
			root.addAttribute(attName, attVal)

	@classmethod
	def getPrefixInfo(cls, prefix):
		return (cls._registry[prefix], cls._schemaLocations[prefix])


registerPrefix = NSRegistry.registerPrefix
getPrefixInfo = NSRegistry.getPrefixInfo

def schemaURL(xsdName):
	"""returns the URL to the local mirror of the schema xsdName.

	This is used by the various xmlstan clients to make schemaLocations.
	"""
	return "http://vo.ari.uni-heidelberg.de/docs/schemata/"+xsdName


registerPrefix("xsi","http://www.w3.org/2001/XMLSchema-instance",  None)
# convenience for _additionalPrefixes of elements needing the xsi prefix
# (and no others) in their attributes.
xsiPrefix = frozenset(["xsi"])


class DOMMorpher(object):
	"""An object encapsulating the process of turning a stanxml.Element
	tree into an ElementTree.

	Discard instances after single use.

	Deprecated, since the whole ElementTree-based serialization is deprecated.
	"""
	def __init__(self, prefixForEmpty=None, nsRegistry=NSRegistry):
		self.prefixForEmpty, self.nsRegistry = prefixForEmpty, nsRegistry
		self.prefixesUsed = set()
	
	def _morphNode(self, stanEl, content, attrDict, childIter):
		name = stanEl.name_
		if stanEl._prefix:
			self.prefixesUsed.add(stanEl._prefix)
			if not (stanEl._local or stanEl._prefix==self.prefixForEmpty):
				name = "%s:%s"%(stanEl._prefix, stanEl.name_)
		if stanEl._additionalPrefixes:
			self.prefixesUsed.update(stanEl._additionalPrefixes)

		node = ElementTree.Element(name, **attrDict)
		if content:
			node.text = content
		for child in childIter:
			childNode = child.apply(self._morphNode)
			if childNode is not None:
				node.append(childNode)
		return node

	def getMorphed(self, stan):
		root = stan.apply(self._morphNode)
		self.nsRegistry.addNamespaceDeclarationsETree(root, self.prefixesUsed)
		if self.prefixForEmpty:
			root.attrib["xmlns"] = self.nsRegistry.getNSForPrefix(
				self.prefixForEmpty)
		return root


class NillableMixin(object):
	"""An Element mixin making the element XSD nillable.

	This element will automatically have an xsi:nil="true" attribute
	on empty elements (rather than leave them out entirely).

	This overrides apply, so the mixin must be before the base class in
	the inheritance list.
	"""
	_mayBeEmpty = True

	def apply(self, func):
		attrs = self._makeAttrDict()
		if self.text_:
			return Element.apply(self, func)
		else:
			attrs = self._makeAttrDict()
			attrs["xsi:nil"] = "true"
			self._additionalPrefixes = self._additionalPrefixes|set(["xsi"])
			return func(self, "", attrs, ())

	def isEmpty(self):
		return False


def escapePCDATA(val):
	return (val
		).replace("&", "&amp;"
		).replace('<', '&lt;'
		).replace('>', '&gt;'
		).replace("\0", "&x00;")


def escapeAttrVal(val):
	return '"%s"'%(escapePCDATA(val).replace('"', '&quot;').encode("utf-8"))


def _makeVisitor(outputFile, prefixForEmpty):
	"""returns a function writing nodes to outputFile.
	"""
	
	def visit(node, text, attrs, childIter):
		attrRepr = " ".join(sorted("%s=%s"%(k, escapeAttrVal(attrs[k]))
			for k in attrs))
		if attrRepr:
			attrRepr = " "+attrRepr

		if getattr(node, "_fixedTagMaterial", None):
			attrRepr = attrRepr+" "+node._fixedTagMaterial

		if not node._prefix or node._local or node._prefix==prefixForEmpty:
			name = node.name_
		else:
			name = "%s:%s"%(node._prefix, node.name_)

		if node.isEmpty():
			if node._mayBeEmpty:
				outputFile.write("<%s%s/>"%(name, attrRepr))
		else:
			outputFile.write("<%s%s>"%(name, attrRepr))
			try:
				try:
					if text:
						outputFile.write(escapePCDATA(text).encode("utf-8"))

					for c in childIter:
						if hasattr(c, "write"):
							c.write(outputFile)
						else:
							c.apply(visit)
				except Exception, ex:
					if hasattr(node, "writeErrorElement"):
						node.writeErrorElement(outputFile, ex)
					raise
			finally:
				outputFile.write("</%s>"%name)

	return visit


def write(root, outputFile, prefixForEmpty=None, nsRegistry=NSRegistry,
		xmlDecl=True, includeSchemaLocation=True):
	"""writes an xmlstan tree starting at root to destFile.

	prefixForEmpty is a namespace URI that should have no prefix at all.
	"""
	# since namespaces only enter here through prefixes, I just need to
	# figure out which ones are used.
	prefixesUsed = set()

	def collectPrefixes(node, text, attrs, childIter, 
			prefixesUsed=prefixesUsed):
		prefixesUsed |= node._additionalPrefixes
		prefixesUsed.add(node._prefix)
		for child in childIter:
			child.apply(collectPrefixes)

	root.apply(collectPrefixes)
	# An incredibly nasty hack for VOTable generation; we need a better
	# way to handle with the 1.1/1.2 namespaces: Root may declare it
	# handles all NS declarations itself.  Die, die, die.
	if getattr(root, "_fixedTagMaterial", None) is None:
		nsRegistry.addNamespaceDeclarations(root, prefixesUsed, prefixForEmpty,
			includeSchemaLocation)

	if xmlDecl:
		outputFile.write("<?xml version='1.0' encoding='utf-8'?>\n")

	root.apply(_makeVisitor(outputFile, prefixForEmpty))


def xmlrender(tree, prolog=None, prefixForEmpty=None):
	"""returns a unicode object containing tree in serialized forms.

	tree can be any object with a render method or some sort of string.
	If it's a byte string, it must not contain any non-ASCII. 

	If prolog is given, it must be a string that will be prepended to the
	serialization of tree.  The way ElementTree currently is implemented,
	you can use this for xml declarations or stylesheet processing 
	instructions.
	"""
	if hasattr(tree, "render"):
		res = tree.render(prefixForEmpty=prefixForEmpty)
	elif hasattr(tree, "getchildren"):  # hopefully an xml.etree Element
		res = ElementTree.tostring(tree)
	elif isinstance(tree, str):
		res = unicode(tree)
	elif isinstance(tree, unicode):
		res = tree
	else:
		raise ValueError("Cannot render %s"%repr(tree))
	if prolog:
		res = prolog+res
	return res
