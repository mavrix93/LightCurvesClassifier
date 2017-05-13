"""
Autonodes are stripped-down versions of the full DaCHS structures.

The idea is to have "managed attributes light" with automatic
constructors.  The Autonodes are used when building something like abstract
syntax trees in STC or ADQL.
"""

#c Copyright 2008-2016, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import itertools


class AutoNodeType(type):
	"""A metaclass for AutoNodes..

	The idea here is to define children in a class definition and make sure they
	are actually present.
	
	AutoNodes are supposed to be immutable; the are defined during construction.
	Currently, nothing keeps you from changing them afterwards, but that may
	change.
	
	The classes' constructor is defined to accept all attributes as arguments
	(you probably want to use keyword arguments here).  It is the constructor
	that sets up the attributes, so AutoNodes must not have an __init__ method.
	However, they may define a method _setupNode that is called just before the
	artificial constructor returns.
	
	To define the attributes of the class, add _a_<attname> attributes
	giving a default to the class.  The default should normally be either
	None for 1:1 or 1:0 relations or an empty tuple for 1:n relations.
	The defaults must return a repr that constructs them, since we create
	a source fragment.
	"""
	def __init__(cls, name, bases, dict):
		cls._collectAttributes()
		cls._buildConstructor()
	
	def _collectAttributes(cls):
		cls._nodeAttrs = []
		for name in dir(cls):
			if name.startswith("_a_"):
				cls._nodeAttrs.append((name[3:], getattr(cls, name)))
	
	def _buildConstructor(cls):
		argList, codeLines = ["self"], []
		for argName, argDefault in cls._nodeAttrs:
			argList.append("%s=%s"%(argName, repr(argDefault)))
			codeLines.append("  self.%s = %s"%(argName, argName))
		codeLines.append("  self._setupNode()\n")
		codeLines.insert(0, "def constructor(%s):"%(", ".join(argList)))
		ns = {}
		exec "\n".join(codeLines) in ns
		cls.__init__ = ns["constructor"]


class AutoNode(object):
	"""An AutoNode.

	AutoNodes are explained in AutoNode's metaclass, AutoNodeType.

	A noteworthy method is change -- pass in new attribute values 
	to create a new instance with the original attribute values except
	for those passed to change.  This will only work if all non-autoattribute
	attributes of the class are set in _setupNode.
	"""
	__metaclass__ = AutoNodeType

	def _setupNodeNext(self, cls):
		try:
			pc = super(cls, self)._setupNode
		except AttributeError:
			pass
		else:
			pc()

	def _setupNode(self):
		self._setupNodeNext(AutoNode)

	def __repr__(self):
		return "<%s %s>"%(self.__class__.__name__, " ".join(
			"%s=%s"%(name, repr(val))
			for name, val in self.iterAttributes(skipEmpty=True)))

	def change(self, **kwargs):
		"""returns a shallow copy of self with constructor arguments in kwargs
		changed.
		"""
		if not kwargs:
			return self
		consArgs = dict(self.iterAttributes())
		consArgs.update(kwargs)
		return self.__class__(**consArgs)

	@classmethod
	def cloneFrom(cls, other, **kwargs):
		"""returns a shallow clone of other.

		other should be of the same class or a superclass.
		"""
		consArgs = dict(other.iterAttributes())
		consArgs.update(kwargs)
		return cls(**consArgs)

	def iterAttributes(self, skipEmpty=False):
		"""yields pairs of attributeName, attributeValue for this node.
		"""
		for name, _ in self._nodeAttrs:
			val = getattr(self, name)
			if skipEmpty and not val:
				continue
			yield name, val
	
	def iterChildren(self, skipEmpty=False):
		for name, val in self.iterAttributes(skipEmpty):
			if isinstance(val, (list, tuple)):
				for c in val:
					yield name, c
			else:
				yield name, val

	def iterNodeChildren(self):
		"""yields pairs of attributeName, attributeValue for this node.

		This will look into sequences, so multiple occurrences of an
		attributeName are possible.  Only nodes are returned.
		"""
		for name, val in self.iterChildren(skipEmpty=True):
			if isinstance(val, AutoNode) and val is not self:
				yield val

	def iterNodes(self):
		"""iterates the tree preorder.

		Only AutoNodes are returned, not python values.
		"""
		childIterators = [c.iterNodes() for c in self.iterNodeChildren()]
		return itertools.chain((self,), *childIterators)
