"""
Active tags are used in prepare and insert computed material into RD trees.

And, ok, we are dealing with elements here rather than tags, but I liked
the name "active tags" much better, and there's too much talk of elements
in this source as it is.

The main tricky part with active tags is when they're nested.  In
short, active tags are expanded even when within active tags.  So,
if you write::

	<STREAM id="foo">
		<LOOP>
		</LOOP>
	</STREAM>

foo contains not a loop element but whatever that spit out.  In particular,
macros within the loop are expanded not within some FEED element but
within the RD.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import csv
import re
from cStringIO import StringIO

from gavo import utils
from gavo.base import attrdef
from gavo.base import common
from gavo.base import complexattrs
from gavo.base import macros
from gavo.base import parsecontext
from gavo.base import structure


# the following is a sentinel for values that have been expanded
# by an active tag already.  When active tags are nested, only the
# innermost must expand macros so one can be sure that double-escaped
# macros actually end up at the top level.  _EXPANDED_VALUE must
# compare true to value since it is used as such in event triples.
class _ExValueType(object):
	def __str__(self):
		return "value"

	def __repr__(self):
		return "'value/expanded'"

	def __eq__(self, other):
		return other=="value"

	def __ne__(self, other):
		return not other=="value"

_EXPANDED_VALUE =_ExValueType()


class ActiveTag(object):
	"""A mixin for active tags.

	This is usually mixed into structure.Structures or derivatives.  It
	is also used as a sentinel to find all active tags below.
	"""
	name_ = None

	def _hasActiveParent(self):
		el = self.parent
		while el:
			if isinstance(el, ActiveTag):
				return True
			el = el.parent
		return False


class GhostMixin(object):
	"""A mixin to make a Structure ghostly.
	
	Most active tags are "ghostly", i.e., the do not (directly)
	show up in their parents.  Therefore, as a part of the wrap-up
	of the new element, we raise an Ignore exception, which tells
	the Structure's end_ method to not feed us to the parent.
	"""
	def onElementComplete(self):
		self._onElementCompleteNext(GhostMixin)
		raise common.Ignore(self)


class _PreparedEventSource(object):
	"""An event source for xmlstruct.

	It is constructed with a list of events as recorded by classes
	inheriting from RecordingBase.
	"""
	def __init__(self, events):
		self.events_ = events
		self.curEvent = -1
		self.pos = None
	
	def __iter__(self):
		return _PreparedEventSource(self.events_)
	
	def next(self):
		self.curEvent += 1
		try:
			nextItem = self.events_[self.curEvent]
		except IndexError:
			raise StopIteration()
		res, self.pos = nextItem[:3], nextItem[-1]
		return res


class RecordingBase(structure.Structure):
	"""An "abstract base" for active tags doing event recording.

	The recorded events are available in the events attribute.
	"""
	name_ = None

	_doc = attrdef.UnicodeAttribute("doc", description="A description of"
		" this stream (should be restructured text).", strip=False)

	def __init__(self, *args, **kwargs):
		self.events_ = []
		self.tagStack_ = []
		structure.Structure.__init__(self, *args, **kwargs)

	def feedEvent(self, ctx, type, name, value):
		# keep _EXPANDED_VALUE rather than "value", see comment above
		if type is _EXPANDED_VALUE:
			self.events_.append((_EXPANDED_VALUE, name, value, ctx.pos))
			return self
		else:
			return structure.Structure.feedEvent(self, ctx, type, name, value)

	def start_(self, ctx, name, value):
		if name in self.managedAttrs and not self.tagStack_:
			res = structure.Structure.start_(self, ctx, name, value)
		else:
			self.events_.append(("start", name, value, ctx.pos))
			res = self
			self.tagStack_.append(name)
		return res

	def end_(self, ctx, name, value):
		if name in self.managedAttrs and not self.tagStack_:
			structure.Structure.end_(self, ctx, name, value)
		else:
			self.events_.append(("end", name, value, ctx.pos))
		self.tagStack_.pop()
		return self
	
	def value_(self, ctx, name, value):
		if name in self.managedAttrs and not self.tagStack_:
			# our attribute
			structure.Structure.value_(self, ctx, name, value)
		else:
			self.events_.append(("value", name, value, ctx.pos))
		return self
	
	def getEventSource(self):
		"""returns an object suitable as event source in xmlstruct.
		"""
		return _PreparedEventSource(self.events_)

	def unexpandMacros(self):
		"""undoes the marking of expanded values as expanded.

		This is when, as with mixins, duplicate expansion of macros during
		replay is desired.
		"""
		for ind, ev in enumerate(self.events_):
			if ev[0]==_EXPANDED_VALUE:
				self.events_[ind] = ("value",)+ev[1:]

	# This lets us feedFrom these
	iterEvents = getEventSource


class EventStream(RecordingBase, GhostMixin, ActiveTag):
	"""An active tag that records events as they come in.

	Their only direct effect is to leave a trace in the parser's id map.
	The resulting event stream can be played back later.
	"""
	name_ = "STREAM"

	def end_(self, ctx, name, value):
		# keep self out of the parse tree
		if not self.tagStack_: # end of STREAM element
			res = self.parent
			self.parent = None
			return res
		return RecordingBase.end_(self, ctx, name, value)


class RawEventStream(EventStream):
	"""An event stream that records events, not expanding active tags.

	Normal event streams expand embedded active tags in place.  This is
	frequently what you want, but it means that you cannot, e.g., fill
	in loop variables through stream macros.

	With non-expanded streams, you can do that::

		<NXSTREAM id="cols">
			<LOOP listItems="\stuff">
				<events>
					<column name="\\item"/>
				</events>
			</LOOP>
		</NXSTREAM>
		<table id="foo">
			<FEED source="cols" stuff="x y"/>
		</table>
	
	Note that the normal innermost-only rule for macro expansions
	within active tags does not apply for NXSTREAMS.  Macros expanded
	by a replayed NXSTREAM will be re-expanded by the next active
	tag that sees them (this is allow embedded active tags to use
	macros; you need to double-escape macros for them, of course).
	"""

	name_ = "NXSTREAM"

	# Hack to signal xmlstruct.EventProcessor not to expand active tags here
	ACTIVE_NOEXPAND = None


class EmbeddedStream(RecordingBase, structure.Structure):
	"""An event stream as a child of another element.
	"""
	name_ = "events"  # Lower case since it's really a "normal" element that's
	                  # added into the parse tree.
	def end_(self, ctx, name, value):
		if not self.tagStack_: # end of my element, do standard structure thing.
			return structure.Structure.end_(self, ctx, name, value)
		return RecordingBase.end_(self, ctx, name, value)


class Prune(ActiveTag, structure.Structure):
	"""An active tag that lets you selectively delete children of the
	current object.

	You give it regular expression-valued attributes; on the replay of
	the stream, matching items and their children will not be replayed.

	If you give more than one attribute, the result will be a conjunction
	of the specified conditions.
	
	This only works if the items to be matched are true XML attributes
	(i.e., not written as children).
	"""
	name_ = "PRUNE"
	
	def __init__(self, parent, **kwargs):
		self.conds = {}
		structure.Structure.__init__(self, parent)

	def value_(self, ctx, name, value):
		self.conds[name] = value
		return self
	
	def end_(self, ctx, name, value):
		assert name==self.name_
		self.matches = self._getMatcher()
		self.parent.feedObject(self.name_, self)
		return self.parent

	def _getMatcher(self):
		"""returns a callabe that takes a dictionary and matches the
		entries against the conditions given.
		"""
		conditions = []
		for attName, regEx in self.conds.iteritems():
			conditions.append((attName, re.compile(regEx)))

		def match(aDict):
			for attName, expr in conditions:
				val = aDict.get(attName)
				if val is None:  # not given or null empty attrs never match
					return False
				if not expr.search(val):
					return False
			return True

		return match


class Edit(EmbeddedStream):
	"""an event stream targeted at editing other structures.
	"""
	name_ = "EDIT"

	_ref = attrdef.UnicodeAttribute("ref", description="Destination of"
		" the edits, in the form elementName[<name or id>]", 
		default=utils.Undefined)

	refPat = re.compile(
		r"([A-Za-z_][A-Za-z0-9_]*)\[([A-Za-z_][A-Za-z0-9_]*)\]")

	def onElementComplete(self):
		mat = self.refPat.match(self.ref)
		if not mat:
			raise common.LiteralParseError("ref", self.ref, 
				hint="edit references have the form <element name>[<value of"
					" name or id attribute>]")
		self.triggerEl, self.triggerId = mat.groups()
	

class ReplayBase(ActiveTag, structure.Structure, macros.StandardMacroMixin):
	"""An "abstract base" for active tags replaying streams.
	"""
	name_ = None  # not a usable active tag
	_expandMacros = True

	_source = parsecontext.ReferenceAttribute("source",
		description="id of a stream to replay", default=None)
	_events = complexattrs.StructAttribute("events",
		childFactory=EmbeddedStream, default=None,
		description="Alternatively to source, an XML fragment to be replayed")
	_edits = complexattrs.StructListAttribute("edits",
		childFactory=Edit, description="Changes to be performed on the"
		" events played back.")
	_prunes = complexattrs.StructListAttribute("prunes",
		childFactory=Prune, description="Conditions for removing"
			" items from the playback stream.")

	def _ensureEditsDict(self):
		if not hasattr(self, "editsDict"):
			self.editsDict = {}
			for edit in self.edits:
				self.editsDict[edit.triggerEl, edit.triggerId] = edit

	def _isPruneable(self, val):
		for p in self.prunes:
			if p.matches(val):
				return True
		return False

	def _replayTo(self, events, evTarget, ctx):
		"""pushes stored events into an event processor.

		The public interface is replay (that receives a structure rather
		than an event processor).
		"""
		idStack = []
		pruneStack = []

		# see RawEventStream's docstring for why we do not want to suppress
		# further expansion with NXSTREAMs
		typeOfExpandedValues = _EXPANDED_VALUE
		if isinstance(self.source, RawEventStream):
			typeOfExpandedValues = "value"

		for type, name, val, pos in events:
			if (self._expandMacros
					and type=="value" 
					and type is not _EXPANDED_VALUE 
					and "\\" in val):
				try:
					val = self.expand(val)
				except macros.MacroError, ex:
					ex.hint = ("This probably means that you should have set a %s"
						" attribute in the FEED tag.  For details see the"
						" documentation of the STREAM with id %s."%(
							ex.macroName,
							getattr(self.source, "id", "<embedded>")))
					raise
				type = typeOfExpandedValues

			# the following mess implements the logic for EDIT.
			if type=="start":
				idStack.append(set())
			elif type=="value":
				if name=="id" or name=="name":
					idStack[-1].add(val)
			elif type=="end":
				ids = idStack.pop()
				for foundId in ids:
					if (name, foundId) in self.editsDict:
						self._replayTo(self.editsDict[name, foundId].events_,
							evTarget,
							ctx)

			# The following mess implements the logic for PRUNE
			if type=="start":
				if pruneStack:
					pruneStack.append(None)
				else:
					if self.prunes and self._isPruneable(val):
						pruneStack.append(None)

			try:
				if not pruneStack:
					evTarget.feed(type, name, val)
			except Exception, msg:
				msg.pos = "%s (replaying, real error position %s)"%(
					ctx.pos, pos)
				raise

			if pruneStack and type=="end":
				pruneStack.pop()
	
		# ReferenceAttribute and similar may change the element fed into;
		# make sure the right object is returned up-tree
		self.parent = evTarget.curParser

	def replay(self, events, destination, ctx):
		"""pushes the stored events into the destination structure.

		While doing this, local macros are expanded unless we already
		receive the events from an active tag (e.g., nested streams
		and such).
		"""
		# XXX TODO: Circular import here.  Think again and resolve.
		from gavo.base.xmlstruct import EventProcessor
		evTarget = EventProcessor(None, ctx)
		evTarget.setRoot(destination)

		self._ensureEditsDict()
		self._replayTo(events, evTarget, ctx)


class DelayedReplayBase(ReplayBase, GhostMixin):
	"""An base class for active tags wanting to replay streams from
	where the context is invisible.

	These define a _replayer attribute that, when called, replays
	the stored events *within the context at its end* and to the
	parent.

	This is what you want for the FEED and LOOP since they always work
	on the embedding element and, by virtue of being ghosts, cannot
	be copied.  If the element embedding an event stream can be
	copied, this will almost certainly not do what you want.
	"""
	def _setupReplay(self, ctx):
		sources = [s for s in [self.source, self.events] if s]
		if len(sources)!=1:
			raise common.StructureError("Need exactly one of source and events"
				" on %s elements"%self.name_)
		stream = sources[0].events_
		def replayer():
			self.replay(stream, self.parent, ctx)
		self._replayer = replayer

	def end_(self, ctx, name, value):
		self._setupReplay(ctx)
		return structure.Structure.end_(self, ctx, name, value)


class ReplayedEventsWithFreeAttributesBase(DelayedReplayBase):
	"""An active tag that takes arbitrary attributes as macro definitions.
	"""
	def __init__(self, *args, **kwargs):
		DelayedReplayBase.__init__(self, *args, **kwargs)
		# managedAttrs in general is a class attribute.  Here, we want
		# to add values for the macros, and these are instance-local.
		self.managedAttrs = self.managedAttrs.copy()

	def getAttribute(self, name):
		try:
			return DelayedReplayBase.getAttribute(self, name)
		except common.StructureError: # no "real" attribute, it's a macro def
			def m():
				return getattr(self, name)
			setattr(self, "macro_"+name.strip(), m)
			self.managedAttrs[name] = attrdef.UnicodeAttribute(name)
			return self.managedAttrs[name]


class ReplayedEvents(ReplayedEventsWithFreeAttributesBase):
	"""An active tag that takes an event stream and replays the events,
	possibly filling variables.

	This element supports arbitrary attributes with unicode values.  These
	values are available as macros for replayed values.
	"""
	name_ = "FEED"

	def completeElement(self, ctx):
		self._completeElementNext(ReplayedEvents, ctx)
		self._replayer()


class NonExpandedReplayedEvents(ReplayedEvents):
	"""A ReplayedEventStream that does not expand active tag macros.

	You only want this when embedding a stream into another stream
	that could want to expand the embedded macros.
	"""
	name_ = "LFEED"
	_expandMacros = False


class GeneratorAttribute(attrdef.UnicodeAttribute):
	"""An attribute containing a generator working on the parse context.
	"""
	def feed(self, ctx, instance, literal):
		if ctx.restricted:
			raise common.RestrictedElement("codeItems")
		attrdef.UnicodeAttribute.feed(self, ctx, instance, literal)
		src = utils.fixIndentation(
			getattr(instance, self.name_), 
			"  ", governingLine=1)
		src = "def makeRows():\n"+src+"\n"
		instance.iterRowsFromCode = utils.compileFunction(
			src, "makeRows", useGlobals={"context": ctx})


class Loop(ReplayedEventsWithFreeAttributesBase):
	"""An active tag that replays a feed several times, each time with
	different values.
	"""
	name_ = "LOOP"

	_csvItems = attrdef.UnicodeAttribute("csvItems", default=None,
		description="The items to loop over, in CSV-with-labels format.",
		strip=True)
	_listItems = attrdef.UnicodeAttribute("listItems", default=None,
		description="The items to loop over, as space-separated single"
		" items.  Each item will show up once, as 'item' macro.",
		strip=True)
	_codeItems = GeneratorAttribute("codeItems", default=None,
		description="A python generator body that yields dictionaries"
		" that are then used as loop items.  You can access the parse context"
		" as the context variable in these code snippets.", strip=False)

	def maybeExpand(self, val):
		if "\\" in val:
			el = self.parent
			while el:
				if hasattr(el, "expand"):
					return el.expand(val)
				el = el.parent
		return val

	def _makeRowIteratorFromListItems(self):
		if self.listItems is None:
			return None
		def rowIterator():
			for item in self.maybeExpand(self.listItems).split():
				yield {"item": item}
		return rowIterator()
	
	def _makeRowIteratorFromCSV(self):
		if self.csvItems is None:
			return None
		# I'd rather not do the encode below, but 2.7 csv can't handle
		# unicode.  We'll need to decode stuff again.
		src = self.maybeExpand(self.csvItems).strip().encode("utf-8")

		def encodeValues(row):
			return dict((key, str(val).decode("utf-8"))
				for key, val in row.iteritems())

		return (encodeValues(row) 
			for row in csv.DictReader(StringIO(src), skipinitialspace=True))

	def _makeRowIteratorFromCode(self):
		if self.codeItems is None:
			return None
		return self.iterRowsFromCode()

	def _getRowIterator(self):
		rowIterators = [ri for ri in [
			self._makeRowIteratorFromListItems(),
			self._makeRowIteratorFromCSV(),
			self._makeRowIteratorFromCode()] if ri]
		if len(rowIterators)!=1:
				raise common.StructureError("Must give exactly one data source in"
					" LOOP")
		return rowIterators[0]
			
	def completeElement(self, ctx):
		self._completeElementNext(Loop, ctx)
		for row in self._getRowIterator():
			for name, value in row.iteritems():
				if value:
					value = value.strip()
				setattr(self, "macro_"+name.strip(), lambda v=value: v)
			self._replayer()


getActiveTag = utils.buildClassResolver(ActiveTag, globals().values(),
	key=lambda obj: getattr(obj, "name_", None))


def registerActiveTag(activeTag):
	getActiveTag.registry[activeTag.name_] = activeTag


def isActive(name):
	return name in getActiveTag.registry
