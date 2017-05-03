"""
Code dealing with meta information.

The meta information we deal with here is *not* column information (which
is handled in datadef.py) but information on tables, services and
resources as a whole.

We deal with VO-style RMI metadata but also allow custom metadata.  Custom
metadata keys should usually start with _.

See develNotes for some discussion of why this is so messy and an explanation
of why in particular addMeta and helpers are a minefield of selections.

The rough plan to do this looks like this:

Metadata is kept in containers that mix in MetaMixin.  Meta information is 
accessed through keys of the form <atom>{.<atom>}  The first atom is the 
primary key.  An atom consists exclusively of ascii letters and the 
underscore.

There's a meta mixin having the methods addMeta and getMeta that care
about finding metadata including handover.  For compound metadata, they
will split the key and hand over to the parent if the don't have a meta 
item for the main key.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import re
import textwrap
import urllib

from gavo import utils
from gavo.base import attrdef
from gavo.base import common
from gavo.utils import stanxml


class MetaError(utils.Error):
	"""A base class for metadata-related errors.

	MetaErrors have a carrier attribute that should point to the MetaMixin
	item queried.  Metadata propagation makes this a bit tricky, but we
	should at least try; for setMeta and addMeta, the top-level entry
	functions manipulate the carrier attributes for this purpose.

	To yield useful error messages, leave carrier at its default None
	only when you really have no idea what the meta will end up on.
	"""
	def __init__(self, msg, carrier=None, hint=None, key=None):
		self.carrier = carrier
		self.key = key
		utils.Error.__init__(self, msg, hint)


class MetaSyntaxError(MetaError):
	"""is raised when a meta key is invalid.
	"""


class NoMetaKey(MetaError):
	"""is raised when a meta key does not exist (and raiseOnFail is True).
	"""


class MetaCardError(MetaError):
	"""is raised when a meta value somehow has the wrong cardinality (e.g.,
	on attempting to stringify a sequence meta).
	"""


class MetaValueError(MetaError):
	"""is raised when a meta value is inapproriate for the key given.
	"""


def metaRstToHtml(inputString):
	return utils.rstxToHTML(inputString)


_metaPat = re.compile(r"([a-zA-Z_-]+)(?:\.([a-zA-Z_-]+))*$")
_primaryPat = re.compile(r"([a-zA-Z_-]+)(\.|$)")


def getPrimary(metaKey):
	key = _primaryPat.match(metaKey)
	if not key or not key.group(1):
		raise MetaSyntaxError("Invalid meta key: %s"%metaKey, None)
	return key.group(1)


def parseKey(metaKey):
	if not _metaPat.match(metaKey):
		raise MetaSyntaxError("Invalid meta key: %s"%metaKey, None)
	return metaKey.split(".")


def parseMetaStream(metaContainer, metaStream, clearItems=False):
	"""parser meta key/value pairs from metaStream and adds them to
	metaContainer.

	If clearItems is true, for each key found in the metaStream there's
	first a delMeta for that key executed.  This is for re-parsing 
	meta streams.

	The stream format is: 
	
	 - continuation lines with backslashes, where any sequence of 
	   backslash, (cr?) lf (blank or tab)* is replaced by nothing.
	 - comments are lines like (ws*)# anything
	 - empty lines are no-ops
	 - all other lines are (ws*)<key>(ws*):(ws*)value(ws*)
	 - if a key starts with !, any meta info for the key is cleared before 
	   setting
	"""
	if metaStream is None:
		return

	# handle continuation lines
	metaStream = re.sub("\\\\\r?\n[\t ]*", "", metaStream)

	keysSeen = set()

	for line in metaStream.split("\n"):
		line = line.strip()
		if line.startswith("#") or not line:
			continue
		try:
			key, value = line.split(":", 1)
		except ValueError:
			raise MetaSyntaxError("%s is no valid line for a meta stream"%
				repr(line), None,
				hint="In general, meta streams contain lines like 'meta.key:"
				" meta value; see also the documentation.")

		key = key.strip()
		if key.startswith("!"):
			key = key[1:]
			metaContainer.delMeta(key)

		if key not in keysSeen and clearItems:
			metaContainer.delMeta(key)
		keysSeen.add(key)
		metaContainer.addMeta(key, value.strip())
				

class MetaParser(common.Parser):
	"""A structure parser that kicks in when meta information is 
	parsed from XML.

	This parser can also handle the notation with an attribute-less
	meta tag and lf-separated colon-pairs as content.
	"""
# These are constructed a lot, so let's keep __init__ as clean as possible, 
# shall we?
	def __init__(self, container, nextParser):
		self.container, self.nextParser = container, nextParser
		self.attrs = {}
		self.children = []  # containing key, metaValue pairs
		self.next = None

	def addMeta(self, *value):
		self.children.append(value)

	def start_(self, ctx, name, value):
		if name=="meta":
			return MetaParser(self, self)
		else:
			self.next = name
			return self

	def value_(self, ctx, name, value):
		if self.next is None:
			self.attrs[str(name)] = value
		else:
			self.attrs[str(self.next)] = value
		return self

	def _getMetaValue(self):
		content = self.attrs.pop("content_", "")
		if not self.attrs: # content only, parse this as a meta stream
			parseMetaStream(self.container, content)
			return None, None
		else:
			try:
				content = utils.fixIndentation(content, "", 1).rstrip()
			except common.Error, ex:
				raise utils.logOldExc(common.StructureError("Bad text in meta value"
					" (%s)"%ex))
			mv = makeMetaValue(content, **self.attrs)
			if not "name" in self.attrs:
				raise common.StructureError("meta elements must have a"
					" name attribute")
			return self.attrs.pop("name"), mv

	def end_(self, ctx, name, value):
		if name=="meta":
			key, mv = self._getMetaValue()
			for child in self.children:
				mv.addMeta(*child)
			if key is not None:
				self.container.addMeta(key, mv)
			return self.nextParser
		else:
			self.next = None
			return self


class MetaAttribute(attrdef.AttributeDef):
	"""An attribute magically inserting meta values to Structures mixing
	in MetaMixin.

	We don't want to keep metadata itself in structures for performance
	reasons, so we define a parser of our own in here.
	"""
	typedesc = "Metadata"

	def __init__(self, description="Metadata"):
		attrdef.AttributeDef.__init__(self, "meta_", 
			attrdef.Computed, description)
		self.xmlName_ = "meta"

	@property
	def default_(self):
		return {}

	def feedObject(self, instance, value):
		self.meta_ = value

	def getCopy(self, parent, newParent):
		"""creates a deep copy of the current meta dictionary and sets it
		as the new meta dictionary.

		You need to call this when you do a copy (using something like copy.copy()
		of an object mixing in this class.

		Note that the copying semantics is a bit funky: Copied values
		remain, but on write, sequences are replaced rather than added to.
		"""
		oldDict = self.meta_
		newMeta = {}
		for key, mi in oldDict.iteritems():
			newMeta[key] = mi.copy()
		return oldDict
	
	def create(self, parent, ctx, name):
		return MetaParser(parent, parent)

	def makeUserDoc(self):
		return ("**meta** -- a piece of meta information, giving at least a name"
			" and some content.  See Metadata_ on what is permitted here.")

	def iterEvents(self, instance):
		def doIter(metaDict):
			for key, item in metaDict.iteritems():
				for value in item:
					yield ("start", "meta", None)
					yield ("value", "name", key)
					if value.getContent():
						yield ("value", "content_", value.getContent())

					if value.meta_:
						for ev in doIter(value.meta_):
							yield ev
					yield ("end", "meta", None)

		for ev in doIter(instance.meta_):
			yield ev


class MetaMixin(object):
	"""is a mixin for entities carrying meta information.

	The meta mixin provides the followng methods:

		- setMetaParent(m) -- sets the name of the meta container enclosing the
			current one.  m has to have the Meta mixin as well.
		- getMeta(key, propagate=True, raiseOnFail=False, default=None) -- returns 
			meta information for key or default.
		- addMeta(key, metaItem) -- adds a piece of meta information here.  Key
			may be a compound.
		- setMeta(key, metaItem) -- like addMeta, only previous value(s) are
			overwritten
		- delMeta(key) -- removes a meta value(s) for key.

	When querying meta information, by default all parents are queried as
	well (propagate=True).
	"""
	_metaAttr = MetaAttribute()

	def __init__(self):
		"""is a constructor for standalone use.  You do *not* want to
		call this when mixing into a Structure.
		"""
		self.meta_ = {}

	def __hasMetaParent(self):
		try:
			self.__metaParent # assert existence
			return True
		except AttributeError:
			return False

	def isEmpty(self):
		return len(self.meta_)==0 and getattr(self, "content", "")==""

	def setMetaParent(self, parent):
		if parent is not None:
			self.__metaParent = parent
	
	def getMetaParent(self):
		if self.__hasMetaParent():
			return self.__metaParent
		else:
			return None

	def _getMeta(self, atoms, propagate):
		try:
			return self._getFromAtom(atoms[0])._getMeta(atoms[1:])
		except NoMetaKey:
			pass   # See if parent has the key
		if propagate:
			if self.__hasMetaParent():
				return self.__metaParent._getMeta(atoms, propagate)
			else:
				return configMeta._getMeta(atoms, propagate=False)
		raise NoMetaKey("No meta item %s"%".".join(atoms), carrier=self)

	def getMeta(self, key, propagate=True, raiseOnFail=False, default=None):
		try:
			try:
				return self._getMeta(parseKey(key), propagate)
			except NoMetaKey, ex:
				if raiseOnFail:
					ex.key = key
					raise
		except MetaError, ex:
			ex.carrier = self
			raise
		return default

	def _iterMeta(self, atoms):
		mine, others = atoms[0], atoms[1:]
		for mv in self.meta_.get(mine, []):
			if others:
				for child in mv._iterMeta(others):
					yield child
			else:
				yield mv
			
	def iterMeta(self, key, propagate=False):
		"""yields all MetaValues for key.

		This will traverse down all branches necessary to yield, in sequence,
		all MetaValues reachable by key.

		If propagation is enabled, the first meta carrier that has at least
		one item exhausts the iteration.

		(this currently doesn't return an iterator but a sequence; that's an
		implementation detail though, you should only assume whatever comes
		back is iterable)
		"""
		val = list(self._iterMeta(parseKey(key)))
		if not val and propagate:
			if self.__hasMetaParent():
				val = self.__metaParent.iterMeta(key, propagate=True)
			else:
				val = configMeta.iterMeta(key, propagate=False)
		return val

	def buildRepr(self, key, builder, propagate=True, raiseOnFail=True):
		value = self.getMeta(key, raiseOnFail=raiseOnFail, propagate=propagate)
		if value:
			builder.startKey(key)
			value.traverse(builder)
			builder.endKey(key)
		return builder.getResult()

	def _hasAtom(self, atom):
		return atom in self.meta_

	def _getFromAtom(self, atom):
		if atom in self.meta_:
			return self.meta_[atom]
		raise NoMetaKey("No meta child %s"%atom, carrier=self)

	def getMetaKeys(self):
		return self.meta_.keys()

# XXX TRANS remove; this is too common a name
	keys = getMetaKeys

	def _setForAtom(self, atom, metaItem):
		self.meta_[atom] = metaItem

	def _addMeta(self, atoms, metaValue):
		primary = atoms[0]
		if primary in self.meta_:
			self.meta_[primary]._addMeta(atoms[1:], metaValue)
		else:
			self.meta_[primary] = MetaItem.fromAtoms(
				atoms[1:], metaValue, primary)

	def addMeta(self, key, metaValue):
		"""adds metaItem to self under key.
		"""
		try:
			if isinstance(metaValue, basestring):
				metaValue = makeMetaValue(metaValue, name=key)
			self._addMeta(parseKey(key), metaValue)
		except MetaError, ex:
			ex.carrier = self
			raise

	def _delMeta(self, atoms):
		if atoms[0] not in self.meta_:
			return
		if len(atoms)==1:
			del self.meta_[atoms[0]]
		else:
			child = self.meta_[atoms[0]]
			child._delMeta(atoms[1:])
			if child.isEmpty():
				del self.meta_[atoms[0]]

	def delMeta(self, key):
		"""removes a meta item from this meta container.

		This will not propagate, i.e., getMeta(key) might still
		return something unless you give propagate=False.

		It is not an error do delete an non-existing meta key.
		"""
		self._delMeta(parseKey(key))

	def setMeta(self, key, value):
		"""replaces any previous meta content of key (on this container)
		with value.
		"""
		self.delMeta(key)
		self.addMeta(key, value)

	def traverse(self, builder):
		for key, item in self.meta_.iteritems():
			builder.startKey(key)
			item.traverse(builder)
			builder.endKey(key)

	def deepCopyMeta(self):
		"""creates a deep copy of the current meta dictionary and sets it
		as the new meta dictionary.

		This is used during a recursive copy of a meta tree.  If this
		is mixed into a structure, its attribute magic will automatically
		make sure this ist applied.

		Note that the copying semantics is a bit funky: Copied values
		remain, but on write, sequences are replaced rather than added to.
		"""
		oldDict = self.meta_
		self.meta_ = {}
		for key, mi in oldDict.iteritems():
			self.meta_[key] = mi.copy()
	
	def copyMetaFrom(self, other):
		"""sets a copy of other's meta items on self.
		"""
		self.meta_ = other.meta_
		self.deepCopyMeta()


# Global meta, items get added from config
configMeta = MetaMixin()


class ComputedMetaMixin(MetaMixin):
	"""is a MetaMixin for classes that want to implement defaults for
	unresolvable meta items.

	If getMeta would return a NoMetaKey, this mixin's getMeta will check
	the presence of a _meta_<key> method (replacing dots with two underscores)
	and, if it exists, returns whatever it returns.  Otherwise, the
	exception will be propagated.

	The _meta_<key> methods can return MetaItems; if something else
	is returned, it is automatically packed into one.
	"""
	def _getFromAtom(self, atom):
		try:
			return MetaMixin._getFromAtom(self, atom)
		except NoMetaKey:
			methName = "_meta_"+atom
			if hasattr(self, methName):
				res = getattr(self, methName)()
				if res is None:
					raise
				if not isinstance(res, MetaItem):
					res = makeMetaItem(res, name=atom)
				return res
			raise


class MetaItem(object):
	"""is a collection of homogenous MetaValues.

	All MetaValues within a MetaItem have the same key.

	A MetaItem contains a list of children MetaValues.

	The last added MetaValue is the "active" one that will be changed
	on _addMeta calls.
	"""
	def __init__(self, val):
		self.children = [val]

	@classmethod
	def fromAtoms(cls, atoms, metaValue, key):
		if len(atoms)==0:  # This will become my child.
			return cls(metaValue)
		elif len(atoms)==1:  # Create a MetaValue with the target as child
			mv = makeMetaValue(name=key)
			mv._setForAtom(atoms[0], cls(metaValue))
			return cls(mv)
		else:   # Create a MetaValue with an ancestor of the target as child
			mv = makeMetaValue(name=key)
			mv._setForAtom(atoms[0], cls.fromAtoms(atoms[1:], metaValue, atoms[0]))
			return cls(mv)

	def __str__(self):
		try:
			res = self.getContent(targetFormat="text")
			return res
		except MetaError:
			return ", ".join(m.getContent(targetFormat="text") 
				for m in self.children)

	__unicode__ = __str__

	def __iter__(self):
		return iter(self.children)

	def __len__(self):
		return len(self.children)

	def isEmpty(self):
		return len(self)==0

	def addContent(self, item):
		self.children[-1].addContent(item)

	def addChild(self, metaValue=None, key=None):
# XXX should we force metaValue to be "compatible" with what's 
# already in children?
		if hasattr(self, "copied"):
			self.children = []
			delattr(self, "copied")
		if metaValue is None:
			metaValue = makeMetaValue(name=key)
		assert isinstance(metaValue, MetaValue)
		self.children.append(metaValue)

	def _getMeta(self, atoms):
		if atoms:
			if len(self.children)!=1:
				raise MetaCardError("getMeta cannot be used on"
					" sequence meta items", carrier=self, key=".".join(atoms))
			else:
				return self.children[0]._getMeta(atoms)
		return self
	
	def _addMeta(self, atoms, metaValue):
# See above for this mess -- I'm afraid it has to be that complex
# if we want to be able to build compound sequences using text labels.

		# Case 1: Direct child of MetaMixin, sequence addition
		if not atoms:  
			self.addChild(metaValue)
		else:
			self.children[-1]._addMeta(atoms, metaValue)

	def getMeta(self, key):
		if len(self.children)==1:
			return self.children[0].getMeta(key)
		else:
			return MetaCardError("No getMeta for meta value sequences",
				carrier=self)

	def getContent(self, targetFormat="text", macroPackage=None):
		if len(self.children)==1:
			return self.children[0].getContent(targetFormat, macroPackage)
		raise MetaCardError("getContent not allowed for sequence meta items",
			carrier=self)

	def _delMeta(self, atoms):
		newChildren = []
		for c in self.children:
			c._delMeta(atoms)
			if not c.isEmpty():
				newChildren.append(c)
		self.children = newChildren

	def traverse(self, builder):
		for mv in self.children:
			if mv.content:
				builder.enterValue(mv)
			mv.traverse(builder)

	def copy(self):
		"""returns a deep copy of self.
		"""
		newOb = self.__class__("")
		newOb.children = [mv.copy() for mv in self.children]
		newOb.copied = True
		return newOb

	def serializeToXMLStan(self):
		return unicode(self)


class _NoHyphenWrapper(textwrap.TextWrapper):
# we don't want whitespace after hyphens in plain meta strings (looks
# funny in HTML), so fix wordsep_re
	wordsep_re = re.compile(
        r'(\s+|'                                  # any whitespace
        r'(?<=[\w\!\"\'\&\.\,\?])-{2,}(?=\w))')   # em-dash


class MetaValue(MetaMixin):
	"""is a piece of meta information about a resource.

	The content is always a string.

	The text content may be in different formats, notably

		- literal

		- rst (restructured text)

		- plain (the default)

		- raw (for embedded HTML, mainly -- only use this if you know
			the item will only be embedded into HTML templates).
	"""
	knownFormats = set(["literal", "rst", "plain", "raw"])
	paragraphPat = re.compile("\n\\s*\n")
	consecutiveWSPat = re.compile("\s\s+")
	plainWrapper = _NoHyphenWrapper(break_long_words=False,
		replace_whitespace=True)

	def __init__(self, content="", format="plain"):
		self.initArgs = content, format
		MetaMixin.__init__(self)
		if format not in self.knownFormats:
			raise common.StructureError(
				"Unknown meta format '%s'; allowed are %s."%(
					format, ", ".join(self.knownFormats)))
		self.content = content
		self.format = format
		self._preprocessContent()

	def __str__(self):
		return self.getContent().encode("utf-8")
	
	def __unicode__(self):
		return self.getContent()

	def _preprocessContent(self):
		if self.format=="plain":
			self.content = "\n\n".join(self.plainWrapper.fill(
					self.consecutiveWSPat.sub(" ", para))
				for para in self.paragraphPat.split(self.content))

	def _getContentAsText(self, content):
		return content

	def _getContentAsHTML(self, content, block=False):
		if block:
			encTag = "p"
		else:
			encTag = "span"
		if self.format=="literal":
			return '<%s class="literalmeta">%s</%s>'%(encTag, content, encTag)
		elif self.format=="plain":
			return "\n".join('<%s class="plainmeta">%s</%s>'%(encTag, p, encTag)
				for p in content.split("\n\n"))
		elif self.format=="rst":
# XXX TODO: figure out a way to have them block=False
			return metaRstToHtml(content)
		elif self.format=="raw":
			return content

	def getContent(self, targetFormat="text", macroPackage=None):
		content = self.content
		if hasattr(macroPackage, "expand") and "\\" in self.content:
			content = macroPackage.expand(content)
		if targetFormat=="text":
			return self._getContentAsText(content)
		elif targetFormat=="html":
			return self._getContentAsHTML(content)
		elif targetFormat=="blockhtml":
			return self._getContentAsHTML(content, block=True)
		else:
			raise MetaError("Invalid meta target format: %s"%targetFormat)

	def encode(self, enc):
		return unicode(self).encode(enc)

	def _getMeta(self, atoms, propagate=False):
		return self._getFromAtom(atoms[0])._getMeta(atoms[1:])

	def _addMeta(self, atoms, metaValue):
# Cases continued from MetaItem._addMeta
		# Case 2: Part of a compound, metaValue is to become direct child
		if len(atoms)==1: 
			primary = atoms[0]

			# Case 2.1: Requested child exists
			if self._hasAtom(primary):
				self._getFromAtom(primary).addChild(metaValue, primary)

			# Case 2.2: Requested child does not exist
			else:
				self._setForAtom(primary, MetaItem(metaValue))

		# Case 3: metaItem will become an indirect child
		else:
			primary = atoms[0]

			# Case 3.1: metaValue will become a child of an existing child of ours
			if self._hasAtom(primary):
				self._getFromAtom(primary)._addMeta(atoms[1:], metaValue)

			# Case 3.2: metaItem is on a branch that needs yet to be created.
			else:
				self._setForAtom(primary, MetaItem.fromAtoms(atoms[1:], 
					metaValue, primary))

	def copy(self):
		"""returns a deep copy of self.
		"""
		newOb = self.__class__(*self.initArgs)
		newOb.format, newOb.content = self.format, self.content
		newOb.deepCopyMeta()
		return newOb


################## individual meta types (factor out to a new module)

class MetaURL(MetaValue):
	"""A meta value containing a link and optionally a title

	In plain text, this would look like
	this::
	
		_related:http://foo.bar
		_related.title: The foo page

	In XML, you can write::

			<meta name="_related" title="The foo page"
				ivoId="ivo://bar.org/foo">http://foo.bar</meta>

	or, if you prefer::

		<meta name="_related">http://foo.bar
			 <meta name="title">The foo page</meta></meta>
	
	These values are used for _related (meaning "visible" links to other
	services).

	For links within you data center, use the internallink macro, the argument
	of which the the "path" to a resource, i.e. RD path/service/renderer;
	we recommend to use the info renderer in such links as a rule.  This would
	look like this::
		
		<meta name="_related" title="Aspec SSAP"
			>\internallink{aspec/q/ssa/info}</meta>

	"""
	def __init__(self, url, format="plain", title=None):
		MetaValue.__init__(self, url, format)
		self.title = title

	def _getContentAsHTML(self, content):
		title = self.title or content
		return '<a href="%s">%s</a>'%(content.strip(), title)

	def _addMeta(self, atoms, metaValue):
		if atoms[0]=="title":
			self.title = metaValue.content
		else:
			MetaValue._addMeta(self, atoms, metaValue)


class RelatedResourceMeta(MetaValue):
	"""A meta value containing an ivo-id and a name of a related resource.

	These are intended for serviceFor, servedBy, derivedFrom,
	mirrorOf, and relatedTo metas.  Plus, new and non-standard for
	DocRegExt, uses.

	It should look like this::

		servedBy: GAVO TAP service
		servedBy.ivoId: ivo://org.gavo.dc
	
	However, service attribute of data publications automatically sets
	these metas, so typically you won't have to bother with those.
	"""
	def __init__(self, title, format="plain", ivoId=None):
		MetaValue.__init__(self, title, format)
		if ivoId is not None:
			self._addMeta(["ivoId"], MetaValue(ivoId))
	

class NewsMeta(MetaValue):
	"""A meta value representing a "news" items.

	The content is the body of the news.  In addition, they have
	date and author children.  In plain text, you would write::

	  _news: Frobnicated the quux.
	  _news.author: MD
	  _news.date: 2009-03-06
	
	In XML, you would usually write::

	  <meta name="_news" author="MD" date="2009-03-06">
	    Frobnicated the quux.
	  </meta>
	"""
	def __init__(self, url, format="plain", author=None, 
			date="Unspecified time"):
		MetaValue.__init__(self, url, format)
		self.initArgs = url, format, author, date
		self.author = author
		self.date = date

	def _getContentAsHTML(self, content):
		authorpart = ""
		if self.author:
			authorpart = " (%s)"%self.author
		return '<span class="newsitem">%s%s: %s</span>'%(self.date, authorpart,
			content)
	
	def _addMeta(self, atoms, metaValue):
		if atoms[0]=="author":
			self.author = metaValue.content
		elif atoms[0]=="date":
			self.date = metaValue.content
		else:
			MetaValue._addMeta(self, atoms, metaValue)


class NoteMeta(MetaValue):
	"""A meta value representing a "note" item.

	This is like a footnote, typically on tables, and is rendered in table
	infos.

	The content is the note body.  In addition, you want a tag child that
	gives whatever the note is references as.  We recommend numbers.

	Contrary to other meta items, note content defaults to rstx format.

	Typically, this works with a column's note attribute.

	In XML, you would usually write::

	  <meta name="note" tag="1">
	    Better ignore this.
	  </meta>
	"""
	def __init__(self, content, format="rst", tag=None):
		MetaValue.__init__(self, content, format)
		self.initArgs = content, format, tag
		self.tag = tag

	def _getContentAsHTML(self, content):
		return ('<dt class="notehead">'
				'<a name="note-%s">Note %s</a></dt><dd>%s</dd>')%(
			self.tag,
			self.tag,
			MetaValue._getContentAsHTML(self, content))
	
	def _addMeta(self, atoms, metaValue):
		if atoms[0]=="tag":
			self.tag = metaValue.content
		else:
			MetaValue._addMeta(self, atoms, metaValue)


class InfoItem(MetaValue):
	"""A meta value for info items in VOTables.

	In addition to the content (which should be rendered as the info element's
	text content), it contains an infoName and an infoValue.
	
	They are only used internally in VOTable generation and might go away
	without notice.
	"""
	def __init__(self, content, format="plain", infoName=None, 
			infoValue=None, infoId=None):
		MetaValue.__init__(self, content, format)
		self.initArgs = content, format, infoName, infoValue, infoId
		self.infoName, self.infoValue = infoName, infoValue
		self.infoId = infoId


class LogoMeta(MetaValue):
	"""A MetaItem corresponding to a small image.

	These are rendered as little images in HTML.  In XML meta, you can
	say::

	  <meta name="_somelogo" type="logo">http://foo.bar/quux.png</meta>
	"""
	def _getContentAsHTML(self, content):
		return u'<img class="metalogo" src="%s" alt="[Logo]"/>'%(
				unicode(content).strip())


class BibcodeMeta(MetaValue):
	"""A MetaItem that may contain bibcodes, which are rendered as links
	into ADS.
	"""
	bibcodePat = re.compile("\d\d\d\d\w[^ ]{14}$")

	def _makeADSLink(self, matOb):
		# local import of config to avoid circular import.
		# (move special metas to separate module?)
		from gavo.base import config
		adsMirror = config.get("web", "adsMirror")
		return '<a href="%s">%s</a>'%(
			adsMirror+"cgi-bin/nph-data_query?bibcode=%s&"
				"link_type=ABSTRACT"%urllib.quote(matOb.group(0)),
			matOb.group(0))  

	def _getContentAsHTML(self, content):
		return self.bibcodePat.sub(self._makeADSLink, unicode(content)
			).replace("&", "&amp;")
			# Yikes.  We should really quote such raw HTML properly...


class VotLinkMeta(MetaValue):
	"""A MetaItem serialized into VOTable links (or, ideally,
	analoguous constructs).

	This exposes the various attributes of VOTable LINKs as href
	linkname, contentType, and role.  You cannot set ID here; if this ever
	needs referencing, we'll need to think about it again.	
	The href attribute is simply the content of our meta (since
	there's no link without href), and there's never any content
	in VOTable LINKs).

	You could thus say::

		votlink: http://docs.g-vo.org/DaCHS
		votlink.role: doc
		votlink.contentType: text/html
		votlink.linkname: GAVO DaCHS documentation
	"""
	def __init__(self, href, format="plain", linkname=None, contentType=None,
			role=None):
		MetaValue.__init__(self, href, format)
		for key in ["linkname", "contentType", "role"]:
			val = locals()[key]
			if val is not None:
				self._addMeta([key], MetaValue(val))


class ExampleMeta(MetaValue):
	"""A MetaItem to keep VOSI examples in.

	All of these must have a title, which is also used to generate
	references.

	These also are in reStructuredText by default, and changing
	that probably makes no sense at all, as these will always need
	interpreted text roles for proper markup.

	Thus, the usual pattern here is::

		<meta name="_example" title="An example for _example">
			See docs_

			.. _docs: http://docs.g-vo.org
		</meta>
	"""
	def __init__(self, content, format="rst", title=None):
		if title is None:
			raise MetaError("_example meta must always have a title")
		MetaValue.__init__(self, content, format)
		self._addMeta(["title"], MetaValue(title))


_metaTypeRegistry = {
	"link": MetaURL,
	"relResource": RelatedResourceMeta,
	"info": InfoItem,
	"logo": LogoMeta,
	"bibcodes": BibcodeMeta,
	"news": NewsMeta,
	"note": NoteMeta,
	"votlink": VotLinkMeta,
	"example": ExampleMeta,
}

_typesForKeys = {
	"_related": "link",
	"_example": "example",
	"servedBy": "relResource",
	"serviceFor": "relResource",
	"relatedTo": "relResource",
	"mirrorOf": "relResource",
	"derivedFrom": "relResource",
	"uses": "relResource",
	"_news": "news",
	"referenceURL": "link",
	"info": "info",
	"logo": "logo",
	"source": "bibcodes",
	"note": "note",
	"votlink": "votlink",
}


def printMetaTree(metaContainer, curKey=""):
	#for debugging
	md = metaContainer.meta_
	for childName in md:
		childKey = curKey+"."+childName
		print childKey
		for item in md[childName]:
			printMetaTree(item, childKey)


def makeMetaValue(value="", **kwargs):
	"""returns a MetaValue instance depending on kwargs.

	Basically, with kwargs["type"] you can select various "special"
	MetaValue-derived types, for example InfoItems, MetaLinks, etc.

	These should always work as "normal" meta items but may provide
	special functionality or attributes, e.g. in HTML serializing (Links
	include a title, InfoItems provide additional attributes for VOTables.

	In general, it's preferable to use plain MetaValues and, e.g., add
	a title meta to a URL.  However, for the most common "structured" values
	it's more convenient to use specialized classes.

	In addition, you can pass the name the MetaValue will eventually have.
	If you do that, a type may automatically be added (but not overridden)
	from the _typesForKeys dictionary.

	If what you pass in already is a MetaValue, it is returned unchanged
	(this is mainly a convenience for makeMetaItem).
	"""
# nB: it was foolish that type, format, and name are passed in just like
# special constructor arguments -- this blocks these atoms for specially
# constructed meta items.  Changing this is a bit nasty because
# this is sort-of-exposed in RD XML (see MetaAttribute above).
# Maybe the change should be done anyway?
	if isinstance(value, MetaValue):
		return value
	cls = MetaValue
	if "name" in kwargs:
		lastKey = parseKey(kwargs["name"])[-1]
		if lastKey in _typesForKeys and not "type" in kwargs and not (
				kwargs.get("format")=="rst"):
			kwargs["type"] = _typesForKeys[lastKey]
		del kwargs["name"]
	if "type" in kwargs:
		if kwargs["type"] is not None:
			try:
				cls = _metaTypeRegistry[kwargs["type"]]
			except KeyError:
				raise utils.logOldExc(
					MetaError("No such meta value type: %s"%kwargs["type"]))
		del kwargs["type"]
	try:
		return cls(value, **kwargs)
	except TypeError:
		raise utils.logOldExc(MetaError(
			"Invalid arguments for %s meta items :%s"%(cls.__name__, str(kwargs)),
			None))


def makeMetaItem(value="", **kwargs):
	"""returns a meta item.

	The kwargs are as for makeMetaValue, except it can be a list, in
	which case a series of MetaValues will be generated within the MetaItem.
	"""
	if isinstance(value, list):
		res = MetaItem(makeMetaValue(value[0], **kwargs))
		for atom in value[1:]:
			res.addChild(makeMetaValue(atom, **kwargs))
		return res
	return MetaItem(makeMetaValue(value, **kwargs))


def getMetaText(ob, key, default=None, **kwargs):
	"""returns the meta item key form ob in text form if present, default 
	otherwise.

	You can pass getMeta keyword arguments (except default).

	ob will be used as a macro package if it has an expand method; to
	use something else as the macro package, pass a macroPackage keyword
	argument.
	"""
	if "macroPackage" in kwargs:
		macroPackage = kwargs.pop("macroPackage")
	else:
		macroPackage = ob

	m = ob.getMeta(key, default=None, **kwargs)
	if m is None:
		return default
	try:
		return m.getContent(macroPackage=macroPackage)
	except MetaCardError:
		raise


class MetaBuilder(object):
	"""A base class for meta builders.

	Builders are passed to a MetaItem's traverse method or to MetaMixin's
	buildRepr method to build representations of the meta information.

	You can either override startKey, endKey, and enterValue.  If you are
	not doing anything fancy, you can get by by just overriding enterValue
	and inspecting curAtoms[-1] (which contains the last meta key).

	You will want to override getResult.
	"""
	def __init__(self):
		self.curAtoms = []

	def startKey(self, key):
		self.curAtoms.append(key)
	
	def endKey(self, key):
		self.curAtoms.pop()
		
	def enterValue(self, value):
		pass
	
	def getResult(self):
		pass


class TextBuilder(MetaBuilder):
	"""is a MetaBuilder that recovers a tuple sequence of the meta items
	in text representation.
	"""
	def __init__(self):
		self.metaItems = []
		super(TextBuilder, self).__init__()
	
	def enterValue(self, value):
		self.metaItems.append((".".join(self.curAtoms), value.getContent()))
	
	def getResult(self):
		return self.metaItems


def stanFactory(tag, **kwargs):
	"""returns a factory for ModelBasedBuilder built from a stan-like "tag".

	Do *not* pass in instanciated tags -- they will just keep accumulating
	children on every model run.
	"""
	if isinstance(tag, stanxml.Element):
		raise utils.ReportableError("Do not use instanciated stanxml element"
			" in stanFactories.  Instead, return them from a zero-argument"
			" function.")

	def factory(args, localattrs=None):
		if localattrs:
			localattrs.update(kwargs)
			attrs = localattrs
		else:
			attrs = kwargs
		if isinstance(tag, type):
			el = tag
		else:  # assume it's a function if it's not an element type.
			el = tag()
		return el(**attrs)[args]
	return factory


# Within this abomination of code, the following is particularly nasty.
# It *must* go.

class ModelBasedBuilder(object):
	"""is a meta builder that can create stan-like structures from meta
	information

	It is constructed with with a tuple-tree of keys and DOM constructors;
	these must work like stan elements, which is, e.g., also true for our
	registrymodel elements.

	Each node in the tree can be one of:
	
		- a meta key and a callable,
		- this, and a sequence of child nodes
		- this, and a dictionary mapping argument names for the callable
			to meta keys of the node.
	
	The callable can also be None, which causes the corresponding items
	to be inlined into the parent (this is for flattening nested meta
	structures).

	The meta key can also be None, which causes the factory to be called
	exactly once (this is for nesting flat meta structures).
	"""
	def __init__(self, constructors, format="text"):
		self.constructors, self.format = constructors, format

	def _buildNode(self, processContent, metaItem, children=(),
			macroPackage=None):
		if not metaItem:
			return []
		result = []
		for child in metaItem.children:
			content = []
			c = child.getContent(self.format, macroPackage=macroPackage)
			if c:
				content.append(c)
			childContent = self._build(children, child, macroPackage)
			if childContent:
				content.append(childContent)
			if content:
				result.append(processContent(content, child))
		return result

	def _getItemsForConstructor(self, metaContainer, macroPackage,
			key, factory, children=(), attrs={}):
		if factory:
			def processContent(childContent, metaItem):
				moreAttrs = {}
				for argName, metaKey in attrs.iteritems():
					val = metaItem.getMeta(metaKey)
					if val:
						moreAttrs[argName] = val.getContent("text", 
							macroPackage=macroPackage)
				return [factory(childContent, localattrs=moreAttrs)]
		else:
			def processContent(childContent, metaItem): #noflake: conditional def
				return childContent

		if key is None:
			return [factory(self._build(children, metaContainer, macroPackage))]
		else:
			return self._buildNode(processContent, 
				metaContainer.getMeta(key, raiseOnFail=False), children,
				macroPackage=macroPackage)

	def _build(self, constructors, metaContainer, macroPackage):
		result = []
		for item in constructors:
			if isinstance(item, basestring):
				result.append(item)
			else:
				try:
					result.extend(self._getItemsForConstructor(metaContainer, 
						macroPackage, *item))
				except utils.Error:
					raise
				except:
					raise utils.logOldExc(utils.ReportableError(
						"Invalid constructor func in %s, meta container active %s"%(
							repr(item), repr(metaContainer))))
		return result

	def build(self, metaContainer, macroPackage=None):
		if macroPackage is None:
			macroPackage = metaContainer
		return self._build(self.constructors, metaContainer, macroPackage)
