"""
Observers are objects listening to EventDispatchers.

They are mostly used as bases for UIs in the context of the DC.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


def listensTo(*args):
	"""is a decorator to make a method listen to a set of events.

	It receives one or more event names.
	"""
	def deco(meth):
		meth.listensTo = args
		return meth
	return deco


class ObserverBase(object):
	"""is a base class for observers.

	Observers have methods listening to certain events.  Use the listen
	decorator above to make the connections.  The actual event subscriptions
	are done in the constructor.

	The signature of the listeners always is::
	
	  listener(dispatcher, arg) -> ignored
	
	dispatcher is the EventDispatcher instance propagating the event.  It
	has lots of useful attributes explained in base.event's notifyXXX docstrings.

	You can listen to anything that has a notify method in the EventDispatcher.
	"""
	def __init__(self, dispatcher):
		self.dispatcher = dispatcher
		for name in dir(self):
			att = getattr(self, name)
			if hasattr(att, "listensTo"):
				for ev in att.listensTo:
					dispatcher.subscribe(ev, att)
