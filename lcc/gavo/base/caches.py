"""
Accessor functions for the various immutables we have.

The main purpose of this module is to keep caches of resource descriptors,
and other items the parsing of which may take some time.

All you need to do is provide a function taking a "key" (a string, most
likely) and returning the object.  Then call

base.caches.makeCache(<accessorName>, <function>)

After that, clients can call

base.caches.<accessorName>(key)

You can additionally provide an isDirty(res) function when calling makeCache.
This can return True if the resource is out of date and should be reloaded.

An alternative interface to registering caches is the registerCache function
(see there).
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


class CacheRegistry:
	"""is a registry for caches kept to be able to clear them.

	A cache is assumed to be a dicitonary here.
	"""
	def __init__(self):
		self.knownCaches = []
	
	def clearall(self):
		for cache in self.knownCaches:
			for key in cache.keys():
				del cache[key]

	def clearForName(self, key):
		for cache in self.knownCaches:
			if key in cache:
				del cache[key]

	def register(self, cache):
		self.knownCaches.append(cache)


_cacheRegistry = CacheRegistry()
clearCaches = _cacheRegistry.clearall
clearForName = _cacheRegistry.clearForName


def _makeCache(creator, isDirty):
	"""returns a callable that memoizes the results of creator.

	The creator has to be a function taking an id and returning the 
	designated object.

	The whole thing is thread-safe only when the creators are.  It is
	possible that arbitrarily many creators for the same id run.  Only one
	will win in the end.

	Race conditions are possible when exceptions occur, but then creators
	behaviour should only depend on id, and so it shouldn't matter.

	isDirty can be a function returning true when the cache should be
	cleared.  The function is passed the current resource.  If isDirty
	is None, no such check is performed.
	"""
	cache = {}
	_cacheRegistry.register(cache)

	def func(id):
		if isDirty is not None and id in cache and isDirty(cache[id]):
			clearForName(id)

		if not id in cache:
			try:
				cache[id] = creator(id)
			except Exception, exc:
				cache[id] = exc
				raise
		if isinstance(cache[id], Exception):
			raise cache[id]
		else:
			return cache[id]

	return func


def registerCache(name, cacheDict, creationFunction):
	"""registers a custom cache.

	This function makes creationFunction available as base.caches.name,
	and it registers cacheDict with the cache manager such that cacheDict
	is cleared as necessary.

	creationFunction must manage cacheDict itself, and of course it
	must always use the instance passed to registerCache.

	This is for "magic" things like getRD that has to deal with aliases
	and such.  For normal use, use makeCache.
	"""
	globals()[name] = creationFunction
	_cacheRegistry.register(cacheDict)
	

def makeCache(name, callable, isDirty=None):
	"""creates a new function name to cache results to calls to callable.

	isDirty can be a function returning true when the cache should be
	cleared.  The function is passed the current resource.
	"""
	globals()[name] = _makeCache(callable, isDirty)
