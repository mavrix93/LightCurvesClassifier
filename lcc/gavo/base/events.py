"""
General event handling.

Basically, everything roughly classified as user interaction should go
through this module.  gavo.base, on import, creates an instance of 
EventDispatcher and installs it as base.ui.  The rest of the library
can then call methods of base.ui.

Clients can then register observers (probably derived from
base.observer.Observer) that subscribe to events and can display or 
log them in some form appropriate to the client.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import contextlib
import sys


class DispatcherType(type):
	"""is a metaclass for dispatching of messages.

	Basically, you define methods called notify<whatever> in your class.
	For each of them, a subscribe<whatever> method is added.

	Then, when notify<whatever> is called, your defined method is called,
	and its result is then passed to all callbacks passed in through
	subscribe<whatever>.
	"""
	def __init__(cls, name, bases, dict):
		type.__init__(cls, name, bases, dict)
		cls.eventTypes = []
		cls._makeNotifiers(dict)

	def _makeNotifier(cls, name, callable):
		cls.eventTypes.append(name)
		def notify(self, *args, **kwargs):
			res = callable(self, *args, **kwargs)
			for callback in self.callbacks[name]:
				callback(res)
			return res
		def subscribe(self, callback):
			self.subscribe(name, callback)
		def unsubscribe(self, callback):
			self.unsubscribe(name, callback)
		setattr(cls, "notify"+name, notify)
		setattr(cls, "subscribe"+name, subscribe)
		setattr(cls, "unsubscribe"+name, unsubscribe)

	def _makeNotifiers(cls, dict):
		for name, val in dict.iteritems():
			if name.startswith("notify"):
				cls._makeNotifier(name[6:], val)


class EventDispatcher(object):
	"""is the central event dispatcher.

	Events are posted by using notify* methods.  Various handlers can
	then attach to them.
	"""
	__metaclass__ = DispatcherType

	def __init__(self):
		self.callbacks = dict((name, []) for name in self.eventTypes)
		self.sourceStack = [None]
		self.curSource = None
		self.totalShippedOut = 0
		self.totalRead = 0
		self.lastRow = None

	@contextlib.contextmanager
	def suspended(self, evName):
		"""a context manager suspending notification for a specific event.

		This is mainly for use by test code that wants to avoid spilling
		too much junk into the log.

		One weak point here is that any subscriptions entered while notification
		is suspended are lost.  So: Don't suspend notifications for normal code.
		"""
		origCallbacks = self.callbacks[evName]
		self.callbacks[evName] = []
		try:
			yield
		finally:
			self.callbacks[evName] = origCallbacks

	def subscribe(self, evName, callback):
		self.callbacks[evName].append(callback)

	def unsubscribe(self, evName, callback):
		"""removes a callback from evName's callback list.

		It is not an error to unsubscribe a callback that's not subscribed.
		"""
		try:
			self.callbacks[evName].remove(callback)
		except ValueError:
			pass

	def notifyExceptionMutation(self, newExc):
		"""is called when an exception is being handled by raising newExc.

		The callbacks are passed a pair of sys.exc_info() and newExc.
		"""
		return sys.exc_info(), newExc

	def logOldExc(self, newExc):
		"""notifies of and ExceptionMutation and returns newExc.
	
		This is just a convenience when mutating exceptions.
		"""
		self.notifyExceptionMutation(newExc)
		return newExc

	def notifyNewSource(self, sourceToken):
		"""is called when a new source is being operated on.

		The callbacks are passed some, hopefully useful, token string.  For
		file source, this is the file name, otherwise we try to make up
		something.

		As side effects, the curSource attribute is set to this value.
		"""
		if isinstance(sourceToken, basestring):
			sourceName = sourceToken
		else:
			sourceName = repr(sourceToken)[:40]
		self.curSource = sourceName
		self.sourceStack.append(sourceToken)
		return sourceName

	def notifySourceError(self):
		"""is called when a parse error occurred in a source.

		The callbacks are passed the name of the failing source.
		"""
		if self.sourceStack:  # user-defined grammars may fail to push one
			lastSource = self.sourceStack.pop()
		else:
			lastSource = "Undefined"
		try:
			self.curSource = self.sourceStack[-1]
		except IndexError: # this would be an internal error...
			self.curSource = None
		return lastSource

	def notifySourceFinished(self):
		"""is called when a source file has been processed.

		The curSource attribute is updated, and its old value is propagated
		to the callbacks.
		"""
		try:
			lastSource = self.sourceStack.pop()
			self.curSource = self.sourceStack[-1]
		except IndexError:
			# someone didn't notified us of a finish without telling us first
			# they started.  Don't fail because of this.
			lastSource = None
		return lastSource
	
	def notifyShipout(self, numItems):
		"""is called when certain table implementations store items.

		The number of items is passed on to the callbacks.  As a side effect,
		the instance variable totalShippedOut is adjusted.

		InMemoryTables don't call this right now and probably never will.
		"""
		self.totalShippedOut += numItems
		return numItems
	
	def notifyIncomingRow(self, row):
		"""is called when certain grammars yield a row to the DC's belly.

		The callbacks receive a reference to the row.  As a side effect,
		the instance variable totalRead is bumped up, and lastRow becomes
		the row passed in.

		To support this, RowIterators have to call this method in their
		_iterRows.  Most will do, DictlistGrammars, e.g., don't.
		"""
		self.totalRead += 1
		self.lastRow = row
		return row

	def notifyIndexCreation(self, indexName):
		"""is called when an index on a DB table is created.

		The callbacks receive the index name.
		"""
		return indexName

	def notifyScriptRunning(self, script):
		"""is called when a script is being started.

		The callback receives a scripting.ScriptRunner instance.  You probably
		want to use the name attribute and not much else.
		"""
		return script

	def notifyError(self, errmsg):
		"""is called when something wants to put out an error message.

		The handlers receive the error message as-is.

		In general, you will be in an exception context when you receive
		this error, but your handlers should not bomb out when you are not.
		"""
		return errmsg

	def notifyFailure(self, failure):
		"""is called when an unexpected twisted failure is being processed.

		You should not listen on this, since the handler just receives None.
		Rather, these events are converted to ErrorOccurreds including the
		failure's traceback.
		"""
		self.notifyError(failure.getErrorMessage()+" (see info for traceback)")
		self.notifyInfo("Traceback of failure just logged:\n%s"%
			failure.getTraceback())

	def notifyWarning(self, message):
		"""is called when something tries to emit communicate non-fatal trouble.

		The handlers receive the message as-is
		"""
		return message

	def notifyInfo(self, message):
		"""is called when something tries to emit auxiliary information.

		The handlers receive the message as-is
		"""
		return message

	def notifyDebug(self, message):
		"""is called when something wants to communicate information only
		useful when trying to figure out a malfunction.

		The handlers receive the message as-is.
		"""
		return message

	def notifyWebServerUp(self):
		"""is called when the webserver is up and running.

		No arguments are transmitted.
		"""
		return ()
