"""
Some fundamental algorithms not found in the standard library.
"""

#c Copyright 2008-2016, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import itertools


class IndexedGraph(object):
	"""is a graph that is indexed by both incoming and outgoing edges.

	The constructor argument edges is an iterable of (from, to)-tuples,
	where both from and to must be hashable.

	The class keeps a set rootNodes of "root nodes" (i.e. those with
	no incoming edges).

	To find leaf nodes, you'd have to compute allNodes-set(outgoingIndex).

	You may access allNodes, rootNodes, incomingIndex, and outgoingIndex
	reading, but any external change to them will wreak havoc.
	"""
	def __init__(self, edges):
		self.allNodes = set()
		self.rootNodes = self.allNodes.copy()
		self.incomingIndex, self.outgoingIndex = {}, {}
		for comeFrom, goTo in edges:
			self.addEdge(comeFrom, goTo)

	def __nonzero__(self):
		return not not self.incomingIndex

	def addEdge(self, comeFrom, goTo):
		self.incomingIndex.setdefault(goTo, set()).add(comeFrom)
		self.outgoingIndex.setdefault(comeFrom, set()).add(goTo)
		self.allNodes.add(goTo)
		self.allNodes.add(comeFrom)
		if comeFrom not in self.incomingIndex:
			self.rootNodes.add(comeFrom)
		self.rootNodes.discard(goTo)

	def removeEdge(self, comeFrom, goTo):
		if (comeFrom not in self.outgoingIndex or 
				goTo not in self.outgoingIndex[comeFrom]):
			raise KeyError("No edge %s->%s"%(comeFrom, goTo))
		self.outgoingIndex[comeFrom].remove(goTo)
		self.incomingIndex[goTo].remove(comeFrom)
		if not self.outgoingIndex[comeFrom]:
			del self.outgoingIndex[comeFrom]
			if comeFrom not in self.incomingIndex:
				self.allNodes.remove(comeFrom)
				self.rootNodes.discard(comeFrom)
		if not self.incomingIndex[goTo]:
			del self.incomingIndex[goTo]
			self.rootNodes.add(goTo)
			if goTo not in self.outgoingIndex:
				self.allNodes.remove(goTo)
				self.rootNodes.discard(goTo)

	def getEdge(self):
		"""returns a random edge.

		It raises an IndexError if the graph is empty.
		"""
		comeFrom = self.incomingIndex.iterkeys().next()
		goTo = self.incomingIndex[comeFrom].pop()
		self.incomingIndex[comeFrom].add(goTo)
		return comeFrom, goTo

	def getSomeRootNode(self):
		"""returns an arbitrary element of rootNodes.

		This will raise a KeyError if no root nodes are left.
		"""
		el = self.rootNodes.pop()
		self.rootNodes.add(el)
		return el


def topoSort(edges):
	"""returns a list with the nodes in the graph edges sorted topologically.

	edges is a sequence of (from, to)-tuples, where both from and to must
	be hashable.

	A ValueError is raised if the graph is not acyclic.
	"""
	res, emptySet = [], frozenset()
	graph = IndexedGraph(edges)
	while graph.rootNodes:
		comeFrom = graph.getSomeRootNode()
		res.append(comeFrom)
		outgoingFromCur = graph.outgoingIndex.get(comeFrom, emptySet).copy()
		for goTo in outgoingFromCur:
			graph.removeEdge(comeFrom, goTo)
			if goTo not in graph.allNodes:
				res.append(goTo)
	if graph:
		raise ValueError("Graph not acyclic, cycle: %s->%s"%graph.getEdge())
	return res


class _Deferred(object):
	"""is a helper class for DeferringDict.
	"""
	def __init__(self, callable, args=(), kwargs={}):
		self.callable, self.args, self.kwargs = callable, args, kwargs
	
	def actualize(self):
		return self.callable(*self.args, **self.kwargs)


class DeferringDict(dict):
	"""is a dictionary that stores tuples of a callable and its
	arguments and will, on the first access, do the calls.

	This is used below to defer the construction of instances in the class
	resolver to when they are actually used.  This is important with interfaces,
	since they usually need the entire system up before they can sensibly
	be built.
	"""
	def __setitem__(self, key, value):
		if isinstance(value, tuple):
			dict.__setitem__(self, key, _Deferred(*value))
		else:
			dict.__setitem__(self, key, _Deferred(value))

	def __getitem__(self, key):
		val = dict.__getitem__(self, key)
		if isinstance(val, _Deferred):
			val = val.actualize()
			dict.__setitem__(self, key, val)
		return val

	def iteritems(self):
		for key in self:
			yield key, self[key]


def commonPrefixLength(t1, t2):
	"""returns the length of the common prefix of the sequences t1, t2.
	"""
	try:
		for prefixLength in itertools.count():
			if t1[prefixLength]!=t2[prefixLength]:
				return prefixLength
	except IndexError: # seqs are identical up to the shorter one's length
		return prefixLength


def chunk(items, getChunkKey, getKeyKey=lambda a: a[0]):
	"""returns items in a chunked form.

	getChunkKey(item)->chunk key is a function returning the chunk title,
	getKeyKey(chunk)->sort key a function returning a sort key for the
	chunks (default is just the chunk key, i.e., chunk[0]

	The chunked form is a sequence of pairs of a chunk key and a sequence
	of items belonging to that chunk.

	The internal order within each chunk is not disturbed, so you should sort
	items as desired before passing things in.
	
	This is supposed to work like this:

	>>> chunk(["abakus", "Analysis", "knopf", "Kasper", "kohl"],
	...   lambda item: item[0].lower())
	[('a', ['abakus', 'Analysis']), ('k', ['knopf', 'Kasper', 'kohl'])]
	"""
	chunks = {}
	for item in items:
		chunkKey = getChunkKey(item)
		chunks.setdefault(chunkKey, []).append(item)
	return sorted(chunks.items(), key=getKeyKey)


def identity(val):
	return val


def _test():
	import doctest, algotricks
	doctest.testmod(algotricks)

if __name__=="__main__":
	_test()
