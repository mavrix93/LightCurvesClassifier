"""
Definitions and shared code for STC processing.
"""

#c Copyright 2008-2016, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import itertools
import math
import operator

from gavo import utils
from gavo.utils import ElementTree #noflake:clients expect this name
from gavo.utils.stanxml import Stub, registerPrefix, schemaURL


class STCError(utils.Error):
	pass

class STCSParseError(STCError):
	"""is raised if an STC-S expression could not be parsed.

	Low-level routines raise a pyparsing ParseException.  Only higher
	level functions raise this error.  The offending expression is in
	the expr attribute, the start position of the offending phrase in pos.
	"""
	def __init__(self, msg, expr=None, pos=None):
		STCError.__init__(self, msg)
		self.args = [msg, expr, pos]
		self.pos, self.expr = pos, expr
	

class STCLiteralError(STCError):
	"""is raised when a literal is not well-formed.

	There is an attribute literal giving the malformed literal.
	"""
	def __init__(self, msg, literal=None):
		STCError.__init__(self, msg)
		self.args = [msg, literal]
		self.literal = literal

class STCInternalError(STCError):
	"""is raised when assumptions about the library behaviour are violated.
	"""

class STCValueError(STCError):
	"""is raised when some STC specification is inconsistent.
	"""

class STCUnitError(STCError):
	"""is raised when some impossible operation on units is requested.
	"""

class STCXBadError(STCError):
	"""is raised when something is wrong with STC-X.
	"""

class STCNotImplementedError(STCError):
	"""is raised when the current implementation limits are reached.
	"""

#### Constants

TWO_PI = 2*math.pi
tropicalYear = 365.242198781  # in days
secsPerJCy = 36525*86400.

STCNamespace = "http://www.ivoa.net/xml/STC/stc-v1.30.xsd"
XlinkNamespace = "http://www.w3.org/1999/xlink"

registerPrefix("stc", STCNamespace,
	schemaURL("stc-v1.30.xsd"))
registerPrefix("xlink", XlinkNamespace,
	schemaURL("xlink.xsd"))


# The following lists have to be updated when the STC standard is
# updated.  They are used for building the STC-X namespace.

# known space reference frames
stcSpaceRefFrames = set(["ICRS", "FK4", "FK5", "ECLIPTIC", "GALACTIC_I",
		"GALACTIC_II", "SUPER_GALACTIC", "AZ_EL", "BODY", "GEO_C", "GEO_D", "MAG",
		"GSE", "GSM", "SM", "HGC", "HGS", "HPC", "HPR", "HEE", "HEEQ", "HGI",
		"HRTN", "MERCURY_C", "VENUS_C", "LUNA_C", "MARS_C", "JUPITER_C_III",
		"SATURN_C_III", "UNKNOWNFrame"])

# known space reference positions
stcRefPositions = set(["TOPOCENTER", "BARYCENTER", "HELIOCENTER", "GEOCENTER",
		"LSR", "LSRK", "LSRD", "GALACTIC_CENTER", "LOCAL_GROUP_CENTER", "MOON",
		"EMBARYCENTER", "MERCURY", "VENUS", "MARS", "JUPITER", "SATURN", "URANUS",
		"NEPTUNE", "PLUTO", "RELOCATABLE", "UNKNOWNRefPos", "CoordRefPos"])

# known flavors for coordinates
stcCoordFlavors = set(["SPHERICAL", "CARTESIAN", "UNITSPHERE", "POLAR", 
	"CYLINDRICAL", "STRING", "HEALPIX"])

# known time scales
stcTimeScales = set(["TT", "TDT", "ET", "TAI", "IAT", "UTC", "TEB", "TDB",
	"TCG", "TCB", "LST", "nil"])


# Nodes for ASTs

def _compareFloat(val1, val2):
	"""returns true if val1==val2 up to a fudge factor.

	This only works for floats.

	>>> _compareFloat(30.0, 29.999999999999996)
	True
	"""
	try:
		return abs(val1-val2)/val1<1e-12
	except ZeroDivisionError:  # val1 is zero
		return val2==0


def _aboutEqual(val1, val2):
	"""compares val1 and val2 inexactly.

	This is for comparing floats or sequences of floats.  If you pass in
	other sequences, bad things will happen.

	It will return true if val1 and val2 are deemed equal.

	>>> _aboutEqual(2.3, 2.2999999999999997)
	True
	>>> _aboutEqual(2.3, 2.299999997)
	False
	>>> _aboutEqual(None, 2.3)
	False
	>>> _aboutEqual((1e-10,1e10), (1.00000000000001e-10,1.00000000000001e10))
	True
	>>> _aboutEqual((1e-10,1e10), (1.0000000001e-10,1.000000001e10))
	False
	"""
	if val1==val2:
		return True
	if isinstance(val1, float) and isinstance(val2, float):
		return _compareFloat(val1, val2)
	try:
		return reduce(operator.and_, (_compareFloat(*p)
			for p in itertools.izip(val1, val2)))
	except TypeError: # At least one value is not iterable
		return False


class ASTNode(utils.AutoNode):
	"""The base class for all nodes in STC ASTs.
	"""
	_a_ucd = None
	_a_id = None

	inexactAttrs = set()

	# we want fast comparison for identitical objects.
	def __eq__(self, other):
		if not isinstance(other, self.__class__):
			return False
		if self is other:
			return True
		for name, _ in self._nodeAttrs:
			if name=="id":
				continue
			if name in self.inexactAttrs:
				if not _aboutEqual(getattr(self, name), getattr(other, name)):
					return False
			elif getattr(self, name)!=getattr(other, name):
				return False
		return True
	
	def __ne__(self, other):
		return not self==other

	def __hash__(self):
		return hash(id(self))

	def ensureId(self):
		"""sets id to some value if still None.
		"""
		if self.id is None:
			self.id = utils.intToFunnyWord(id(self))


class ColRef(Stub):
	"""A column reference instead of a true value, occurring in an STC-S tree.
	"""
	name_ = "_colRef"

	# A ghastly hack: if someone sets this true at some point this
	# reference will be rendered to a PARAMref rather than a FIELDref
	# in VOTables.  Well, this whole code needs overdoing.
	toParam = False

	def __str__(self):
		return self.dest 
		# only for debugging: '"%s"'%self.dest
	
	def __mul__(self, other):
		raise STCValueError("ColRefs (here, %s) cannot be used in arithmetic"
			" expressions."%repr(self))

	def encode(self, encoding): # for ElementTree.dump
		return self.dest.encode(encoding)

	def isoformat(self):
		return self

	def apply(self, func):
		return func(self, self.dest, {}, [])


class GeometryColRef(ColRef):
	"""A ColRef that refers to an in-DB geometry.

	These comprise the entire arguments of a geometry (or all coordinates
	of a vector).  They implement __len__ as soon as they are validated
	(in stcsast; we don't do col. refs in stc-x); their len is the
	expected number of elements.
	"""
	expectedLength = None

	def __len__(self):
		if self.expectedLength is None:
			raise STCValueError("No length on unvalidated geometry column"
				" reference")
		return self.expectedLength

	def __nonzero__(self):
		return True


def clampLong(val):
	"""returns val standardized as a latitude.

	Our latitudes are always in [0, 2*pi].
	"""
	val = math.fmod(val, TWO_PI)
	if val<0:
		val += TWO_PI
	return val


def clampLat(val):
	"""returns val standardized as a latitude.

	Our latitudes are always in [-pi, pi].
	"""
	val = math.fmod(val, TWO_PI)
	if val<-math.pi:
		val += TWO_PI
	if val>math.pi:
		val -= TWO_PI
	return val


def _test():
	import doctest, gavo.stc.common
	doctest.testmod(gavo.stc.common)

if __name__=="__main__":
	_test()
