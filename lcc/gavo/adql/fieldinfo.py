"""
Field Infos -- annotations to ADQL parse nodes carrying values.

To do this, we have a set of naive heuristics how types, ucds, and units 
behave when such "fields" are combined.  Since right now, we don't parse
out enough and, at least for ucds and units we don't have enough data
to begin with, much of this is conjecture.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import re


class _CoercNode(object):
	"""An entry in the coercion tree.
	"""
	def __init__(self, name, children=(), aliases=()):
		self.name, self.aliases = name, aliases
		self.parent, self.children = None, children
		for child in self.children:
			child.parent = self

	def getAncestorNames(self):
		if self.parent is None:
			return [self.name]
		res = self.parent.getAncestorNames()
		res.append(self.name)
		return res


class Coercions(object):
	"""A tree of types that can be used to infer common types.

	The tree is passed in as nested sequences.

	>>> c = Coercions(_CoercNode('bar', (_CoercNode('foo'), _CoercNode('baz',
	...   (_CoercNode('quux'),)))))
	>>> c.getSubsuming([])
	'bar'
	>>> c.getSubsuming(['foo'])
	'foo'
	>>> c.getSubsuming(['foo', 'foo'])
	'foo'
	>>> c.getSubsuming(['foo', 'quux'])
	'bar'
	>>> c.getSubsuming(['foo', 'weird'])
	'bar'
	"""
	def __init__(self, typeTree):
		self.typesIndex = {}
		self.root = typeTree
		def index(node):
			self.typesIndex[node.name] = node
			for a in node.aliases:
				self.typesIndex[a] = node
			for c in node.children:
				index(c)
		index(self.root)

	def _unify(self, n1, n2):
		"""returns the first node that is an ancestor to both n1 and n2.
		"""
		ancestors = set(n1.getAncestorNames())
		while n2:
			if n2.name in ancestors:
				return n2
			n2 = n2.parent
		return self.root

	def getSubsuming(self, typeSeq):
		"""returns the least general type being able to represent all types
		within typeSeq.

		The method returns the root type for both an empty typeSeq or
		a typeSeq containing an unknown type.  We don't want to fail here,
		and the "all-encompassing" type should handle any crap.
		"""
		try:
			startNodes = [self.typesIndex[t] for t in typeSeq]
		except KeyError: # don't know at least one type
			return self.root.name
		try:
			return reduce(self._unify, startNodes).name
		except TypeError: # startNodes is empty
			return self.root.name


N = _CoercNode
_coercions = Coercions(
	N('raw', (
		N('unicode', (
			N('text', (
				N("double precision", aliases=("double",), children=(
					N("real", aliases=("float",), children=(
						N("bigint", (
							N("integer", aliases=("int",), children=(
								N("smallint", (
									N('bytea'),
									N('boolean'),)),)),)),)),)),
				N('timestamp', (
					N('date'),
					N('time'),)),
				N('file'),
				N('box'),
				N('spoint'),
				N('scircle'),
				N('spoly', (
					N('sbox'),)),
				),),),),)))
del N


_stringRE = re.compile(r"(?:character varying|varchar|char)\(\d*\)")
_arrayRE = re.compile(r"([^[]*)(?:\[\d*\])+")


def getSubsumingType(sqlTypes):
	"""returns an approximate sql type for a value composed of the types
	mentioned in the sequence sqlTypes.

	Basically, we have the coercion sequence int -> float -> text,
	where earlier types get clobbered by later ones.  And then there's
	messy stuff like dates.  We don't want to fail here, so if all else
	fails, we just make it a text.

	Since we don't know what operation is being performed, this can never
	be accurate; the idea is to come up with something usable to generate
	VOTables from ADQL results.

	We do arrays (and subsume them by subsuming all types and gluing a []
	to the result; the char(x) and friends are all subsumed to text.

	All intput is supposed to be lower case.

	>>> getSubsumingType(["smallint", "integer"])
	'integer'
	"""
	cleanedTypes, wasArray = [], False
	for type in sqlTypes:
		if _stringRE.match(type):
			return "text"
		mat = _arrayRE.match(type)
		if mat:
			type = mat.group(1)
			wasArray = True
		cleanedTypes.append(type)
	
	subsType = _coercions.getSubsuming(cleanedTypes)

	if wasArray:
		return subsType+"[]"
	else:
		return subsType


class FieldInfo(object):
	"""is a container for meta information on columns.

	It is constructed with a unit, a ucd and userData.  UserData is
	a sequence of opaque objects.  A FieldInfo combined from more than 
	one FieldInfo will have all userDatas of the combined FieldInfos in
	its userData attribute.

	There's also a properties dictionary you can use to set arbitrary
	keys in.  These should not be inherited.  This is used for:

		- xtype -- where applicable, write an ADQL xtype.
	"""
	def __init__(self, type, unit, ucd, userData=(), tainted=False, stc=None):
		self.type = type
		self.ucd = ucd
		self.unit = unit
		self.stc = stc
		self.userData = userData
		self.tainted = tainted
		self.properties = {}

	def __eq__(self, other):
		try:
			return (self.type==other.type
				and self.ucd==other.ucd 
				and self.unit==other.unit 
				and self.stc==other.stc
				and self.tainted==other.tainted)
		except AttributeError:
			return False
	
	def __ne__(self, other):
		return not self==other

	def __repr__(self):
		return "FieldInfo(%s, %s, %s, %s)"%(
			repr(self.type),
			repr(self.unit), 
			repr(self.ucd),
			repr(self.userData))

	@staticmethod
	def combineUserData(fi1, fi2):
		return fi1.userData+fi2.userData

	@staticmethod
	def combineSTC(fi1, fi2):
		"""tries to find a common STC system for fi1 and fi2.

		Two STC systems are compatible if at least one is None or if they
		are equal.

		If this method discovers incompatible systems, it will set the
		stc attribute to "BROKEN".
		"""
		if fi1.stc is None and fi2.stc is None:
			return None
		elif fi2.stc is None or fi1.stc==fi2.stc:
			return fi1.stc
		elif fi1.stc is None:
			return fi2.stc
		else: # Trouble: stcs not equal but given, warn and blindly return
		      # fi1's stc
			res = fi1.stc.change()
			res.broken = ("This STC info is bogus.  It is the STC from an"
				" expression combining two different systems.")
			return res

	@classmethod
	def fromMulExpression(cls, opr, fi1, fi2):
		"""returns a new FieldInfo built from the multiplication-like operator opr
		and the two field infos.

		The unit is unit1 opr unit2 unless we have a dimless (empty unit), in
		which case we keep the unit but turn the tainted flag on, unless both
		are empty.

		The ucd is always empty unless it's a simple dimless multiplication,
		in which case the ucd of the non-dimless is kept (but the info is
		tainted).
		"""
		unit1, unit2 = fi1.unit, fi2.unit
		newUserData = cls.combineUserData(fi1, fi2)
		stc = cls.combineSTC(fi1, fi2)
		newType = getSubsumingType([fi1.type, fi2.type])

		if unit1=="" and unit2=="":
			return cls(newType, "", "", newUserData, stc=stc, tainted=True)
		elif unit1=="":
			return cls(newType, unit2, fi2.ucd, newUserData, tainted=True, stc=stc)
		elif unit2=="":
			return cls(newType, unit1, fi1.ucd, newUserData, tainted=True, stc=stc)
		else:
			if opr=="/":
				unit2 = "(%s)"%unit2
			return cls(newType, unit1+opr+unit2, "", newUserData,
				tainted=True, stc=stc)
	
	@classmethod
	def fromAddExpression(cls, opr, fi1, fi2, forceType=None):
		"""returns a new FieldInfo built from the addition-like operator
		opr and the two field infos.
			
		If both UCDs and units are the same, they are kept.  Otherwise,
		they are cleared and the fieldInfo is tainted.
		"""
		unit, ucd, taint = "", "", True
		stc = cls.combineSTC(fi1, fi2)
		if fi1.unit==fi2.unit:
			unit = fi1.unit
		else:
			taint = True
		if fi1.ucd==fi2.ucd:
			ucd = fi1.ucd
		else:
			taint = True
		if forceType is not None:
			newType = forceType
		else:
			newType = getSubsumingType([fi1.type, fi2.type])
		return cls(newType, unit, ucd, cls.combineUserData(fi1, fi2), taint, stc)

	def copyModified(self, **kwargs):
		consArgs = {"type": self.type, "unit": self.unit, "ucd": self.ucd,
			"userData": self.userData, "tainted": self.tainted, "stc": self.stc}
		consArgs.update(kwargs)
		return FieldInfo(**kwargs)


def _test():
	import doctest, fieldinfo
	doctest.testmod(fieldinfo)


if __name__=="__main__":
	_test()


