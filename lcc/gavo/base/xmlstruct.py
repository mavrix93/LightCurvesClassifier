"""
Code to parse structures from XML sources.

The purpose of much of the mess here is to symmetrized XML attributes
and values.  Basically, we want start, value, end events whether
or not a piece of data comes in an element with a certain tag name or
via a named attribute.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import re
from cStringIO import StringIO

from gavo import utils
from gavo.base import activetags
from gavo.base import common
from gavo.base import parsecontext


ALL_WHITESPACE = re.compile("\s*$")


class EventProcessor(object):
	"""A dispatcher for parse events to structures.

	It is constructed with the root structure of the result tree, either
	as a type or as an instance.

	After that, events can be fed to the feed method that makes sure
	they are routed to the proper object.
	"""

# The event processor distinguishes between parsing atoms (just one
# value) and structured data using the next attribute.  If it is not
# None, the next value coming in will be turned to a "value" event
# on the current parser.  If it is None, we hand through the event
# to the current structure.

	def __init__(self, rootStruct, ctx):
		self.rootStruct = rootStruct
		self.curParser, self.next = self, None
		self.result, self.ctx = None, ctx
		# a queue of events to replay after the current structured
		# element has been processed
		self.eventQueue = []

	def _processEventQueue(self):
		while self.eventQueue:
			self.feed(*self.eventQueue.pop(0))

	def _feedToAtom(self, type, name, value):
		if type=='start':
			raise common.StructureError("%s elements cannot have %s children"%(
				self.next, name))
		elif type=='value' or type=="parsedvalue":
			self.curParser.feedEvent(self.ctx, 'value', self.next, value)
		elif type=='end':
			self.next = None

	def _feedToStructured(self, type, name, value):
		next = self.curParser.feedEvent(self.ctx, type, name, value)
		if isinstance(next, basestring):
			self.next = next
		else:
			self.curParser = next
		if type=="end":
			self._processEventQueue()

	def feed(self, type, name, value=None):
		"""feeds an event.

		This is the main entry point for user calls.
		"""
		# Special handling for active tags: They may occur everywhere and
		# thus are not not parsed by the element parsers but by us.
		# Active tags may define ACTIVE_NOEXPAND to undo that behaviour
		# (i.e., see active tag events themselves).
		if (type=="start" 
				and activetags.isActive(name)
				and not hasattr(self.curParser, "ACTIVE_NOEXPAND")):
			self.curParser = activetags.getActiveTag(name)(self.curParser)
			return

		if self.next is None:
			self._feedToStructured(type, name, value)
		else:
			self._feedToAtom(type, name, value)
	
	def feedEvent(self, ctx, evType, name, value):
		"""dispatches an event to the root structure.

		Do not call this yourself unless you know what you're doing.  The
		method to feed "real" events to is feed.
		"""
		if name!=self.rootStruct.name_:
			raise common.StructureError("Expected root element %s, found %s"%(
				self.rootStruct.name_, name))
		if evType=="start":
			if isinstance(self.rootStruct, type):
				self.result = self.rootStruct(None)
			else:
				self.result = self.rootStruct
			self.result.idmap = ctx.idmap
			return self.result
		else:
			raise common.StructureError("Bad document structure")
	
	def setRoot(self, root):
		"""artifically inserts an instanciated root element.

		In particular, this bypasses any checks that the event stream coming
		is is actually destined for root.  Use this for replay-type things
		(feedFrom, active tags) exclusively.
		"""
		self.result = root
		self.curParser = root
		self.result.idmap = self.ctx.idmap

	def clone(self):
		return EventProcessor(self.rootStruct, self.ctx)


def _synthesizeAttributeEvents(evProc, context, attrs):
	"""generates value events for the attributes in attrs.
	"""
	# original attributes must be fed first since they will ususally
	# yield a different target object
	original = attrs.pop("original", None)
	if original:
		evProc.feed("value", "original", original)
	
	# mixins must be fed last as they might depend on stuff set
	# in other attributes
	mixin = attrs.pop("mixin", None)

	for key, val in attrs.iteritems():
		evProc.feed("value", key, val)

	if mixin:
		evProc.feed("value", "mixin", mixin)

def feedTo(rootStruct, eventSource, context, feedInto=False):
	"""feeds events from eventSource to rootStruct.

	A new event processor is used for feeding.  No context
	exit functions are run.

	The processed root structure is returned.

	if feedInto is true, the event creating the root structure is not
	expected (TODO: this is crap; fix it so that this is always the
	case when rootStruct is an instance).
	"""
	evProc = EventProcessor(rootStruct, context)
	if feedInto:
		evProc.setRoot(rootStruct)
	buf = []

	try:
		for type, name, payload in eventSource:
			
			# buffer data
			if type=="data":
				buf.append(payload)
				continue
			else:
				if buf:
					res = "".join(buf)
					if not ALL_WHITESPACE.match(res):
						evProc.feed("value", "content_", res)
				buf = []

			# "normal" event feed
			evProc.feed(type, name, payload)

			# start event: Synthesize value events for attributes.
			if type=="start" and payload:  
				_synthesizeAttributeEvents(evProc, context, payload)
				payload = None

	except Exception, ex:
		if (not getattr(ex, "posInMsg", False) 
				and getattr(ex, "pos", None) is None):
			# only add pos when the message string does not already have it.
			ex.pos = eventSource.pos
		raise
	return evProc.result


def parseFromStream(rootStruct, inputStream, context=None):
	"""parses a tree rooted in rootStruct from some file-like object inputStream.

	It returns the root element of the resulting tree.  If rootStruct is
	a type subclass, it will be instanciated to create a root
	element, if it is an instance, this instance will be the root.
	"""
	eventSource = utils.iterparse(inputStream)
	if context is None:
		context = parsecontext.ParseContext()
	context.setEventSource(eventSource)
	res = feedTo(rootStruct, eventSource, context)
	context.runExitFuncs(res)
	return res


def parseFromString(rootStruct, inputString, context=None):
	"""parses a tree rooted in rootStruct from a string.

	It returns the root element of the resulting tree.
	"""
	return parseFromStream(rootStruct, StringIO(inputString), context)
