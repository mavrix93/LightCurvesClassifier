"""
Useless observers.

Well, maybe they aren't useless, but at least they are not intended for
"normal" use.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from gavo.base import ObserverBase

class DelugeUI(ObserverBase):
	"""is an observer that just dumps all events.
	"""
	def __init__(self, dispatcher):
		ObserverBase.__init__(self, dispatcher)
		for eventType in dispatcher.eventTypes:
			dispatcher.subscribe(eventType, 
				lambda arg, eventType=eventType: self.dumpStuff(arg, eventType))
	
	def dumpStuff(self, stuff, eventType):
		print eventType, stuff


class NullUI(ObserverBase):
	"""is an observer that reports no events at all.
	"""
	def __init__(self, dispatcher):
		pass
