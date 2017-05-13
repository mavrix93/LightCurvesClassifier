"""
Bindings for the pgsphere libarary and psycopg2.

Basically, once per program run, you need to call preparePgSphere(connection),
and you're done.

All native representation is in rad.
"""

#c Copyright 2008-2016, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import math
import re

from gavo.utils import codetricks
from gavo.utils import excs
from gavo.utils import mathtricks
from gavo.utils import misctricks
from gavo.utils.mathtricks import DEG

_TRAILING_ZEROES = re.compile("0+(\s|$)")
def removeTrailingZeroes(s):
	"""remove zeroes in front of whitespace or the string end.

	This is used for cosmetics in STC-S strings.

	>>> removeTrailingZeroes("23.3420   21.2 12.00000")
	'23.342   21.2 12.'
	"""
	return _TRAILING_ZEROES.sub(r"\1", s)


class TwoSBoxes(excs.ExecutiveAction):
	"""is raised when an SBox is constructed from center and size such that
	it overlaps the pole.
	"""
	def __init__(self, box1, box2):
		self.box1, self.box2 = box1, box2


def _query(conn, query, pars=None):
	c = conn.cursor()
	c.execute(query, pars)
	res = list(c)
	return res


class PgSAdapter(object):
	"""A base class for objects adapting pgSphere objects.

	The all need a pgType attribute and two static methods
	_adaptToPgSphere(obj) and _castFromPgSphere(value, cursor).

	You must also define a sequence checkedAttributes; all attributes
	metioned there must be equal for two adapted values to be equal (equality
	testing here really is mainly for unit tests with hand-crafted values).

	Also, all subclasses you should provide an asPoly returning a spherical
	polygon.  This is used when uploading VOTables with REGION columns.
	"""
	pgType = None

	def __eq__(self, other):
		if self.__class__!=other.__class__:
			return False
		for attName in self.checkedAttributes:
			if getattr(self, attName)!=getattr(other, attName):
				return False
		return True

	def __ne__(self, other):
		return not self==other

	def __repr__(self):
		return "<pgsphere %s>"%self.asSTCS("Unknown")

	def asPoly(self):
		raise ValueError("%s objects cannot be turned into polygons."%
			self.__class__)


class SPoint(PgSAdapter):
	"""A point on a sphere from pgSphere.

	>>> SPoint(1, 1).asSTCS("ICRS")
	'Position ICRS 57.2957795131 57.2957795131'
	>>> SPoint.fromDegrees(1, -1).asSTCS("ICRS")
	'Position ICRS 1. -1.'
	"""
	pgType = "spoint"
	checkedAttributes = ["x", "y"]
	pattern = re.compile(r"\s*\(\s*([0-9.e-]+)\s*,\s*([0-9.e-]+)\s*\)")

	def __init__(self, x, y):
		self.x, self.y = float(x), float(y)

	def __repr__(self):
		return "SPoint(%r, %r)"%(self.x, self.y)

	@staticmethod
	def _adaptToPgSphere(spoint):
		return AsIs("spoint '(%.10f,%.10f)'"%(spoint.x, spoint.y))
	
	@classmethod
	def _castFromPgSphere(cls, value, cursor):
		if value is not None:
			return cls(*map(float, cls.pattern.match(value).groups()))
	
	@classmethod
	def fromDegrees(cls, x, y):
		return cls(x*DEG, y*DEG)

	def asCooPair(self):
		"""returns this point as (long, lat) in degrees.
		"""
		return (self.x/DEG, self.y/DEG)

	def asSTCS(self, systemString):
		return removeTrailingZeroes(
			"Position %s %.10f %.10f"%(systemString, self.x/DEG, self.y/DEG))

	def asPgSphere(self):
		return "spoint '(%.10f,%.10f)'"%(self.x, self.y)

	def p(self):   # helps below
		return "(%r, %r)"%(self.x, self.y)


class SCircle(PgSAdapter):
	"""A spherical circle from pgSphere.

	The constructor accepts an SPoint center and a radius in rad.
	"""
	pgType = "scircle"
	checkedAttributes = ["center", "radius"]
	pattern = re.compile("<(\([^)]*\))\s*,\s*([0-9.e-]+)>")

	def __init__(self, center, radius):
		self.center, self.radius = center, float(radius)

	@staticmethod
	def _adaptToPgSphere(sc):
		return AsIs("scircle '< %s, %r >'"%(sc.center.p(), sc.radius))
	
	@classmethod
	def _castFromPgSphere(cls, value, cursor):
		if value is not None:
			pt, radius = cls.pattern.match(value).groups()
			return cls(SPoint._castFromPgSphere(pt, cursor), radius)

	def asSODA(self):
		"""returns the "SODA-form" for this circle.

		This is a string containing blank-separated float literals of the
		center coordinates and the radius in degrees.  Warning: if the coordinates
		aren't ICRS to begin with, these values will be wrong.
		"""
		return "%.10f %.10f %.10f"%(self.center.x/DEG, self.center.y/DEG,
			self.radius/DEG)

	@classmethod
	def fromSODA(cls, sodaSeq):
		"""returns a circle from its SODA-like float sequence.
		"""
		ra, dec, radius = [float(s) for s in sodaSeq]
		return cls(SPoint.fromDegrees(ra, dec), radius*DEG)

	def asSTCS(self, systemString):
		return removeTrailingZeroes("Circle %s %s"%(
			systemString, self.asSODA()))

	def asPgSphere(self):
		return "scircle '< (%.10f, %.10f), %.10f >'"%(
			self.center.x, self.center.y, self.radius)

	def asPoly(self):
		# approximate the circle with 32 line segments and don't worry about
		# circles with radii larger than 90 degrees.
		# We compute the circle around the north pole and then rotate
		# the resulting points such that the center ends up at the
		# circle's center.
		r = math.sin(self.radius)
		innerOffset = math.cos(self.radius)
		rotationMatrix = mathtricks.getRotZ(math.pi/2-self.center.x).matMul(
			mathtricks.getRotX(math.pi/2-self.center.y))

		points = []
		for i in range(32):
			angle = i/16.*math.pi
			dx, dy = r*math.sin(angle), r*math.cos(angle)
			points.append(SPoint(
				*mathtricks.cartToSpher(rotationMatrix.vecMul((dx, dy, innerOffset)))))
		return SPoly(points)


class SPoly(PgSAdapter):
	"""A spherical polygon from pgSphere.

	The constructor accepts a list points of SPoints.
	"""
	pgType = "spoly"
	checkedAttributes = ["points"]
	pattern = re.compile("\([^)]+\)")

	def __init__(self, points):
		self.points = tuple(points)

	@staticmethod
	def _adaptToPgSphere(spoly):
		return AsIs("spoly '{%s}'"%(", ".join(p.p() for p in spoly.points)))
	
	@classmethod
	def _castFromPgSphere(cls, value, cursor):
		if value is not None:
			return cls([SPoint._castFromPgSphere(ptLit, cursor)
				for ptLit in cls.pattern.findall(value)])

	def asSODA(self):
		"""returns the "SODA-form" for this polygon.

		This is a string containing blank-separated float literals of the vertex
		coordinates in degrees.  Warning: if the coordinates aren't ICRS to begin
		with, these values will be wrong.
		"""
		return removeTrailingZeroes(
			" ".join("%.10f %.10f"%(p.x/DEG, p.y/DEG) for p in self.points))

	@classmethod
	def fromSODA(cls, sodaSeq):
		"""returns a polygon from a SODA-like float-sequence

		This is a string containing blank-separated float literals of the vertex
		coordinates in degrees, ICRS.
		"""
		return cls([SPoint.fromDegrees(*tuple(p)) 
			for p in misctricks.grouped(2, sodaSeq)])

	def asCooPairs(self):
		"""returns the vertices as a sequence of (long, lat) pairs in
		degrees.

		This form is required by some functions from base.coords.
		"""
		return [p.asCooPair() for p in self.points]

	def asSTCS(self, systemString):
		return removeTrailingZeroes("Polygon %s %s"%(systemString, 
			self.asSODA()))

	def asPgSphere(self):
		return "spoly '{%s}'"%(",".join("(%.10f,%.10f)"%(p.x, p.y)
			for p in self.points))

	def asPoly(self):
		return self


class SBox(PgSAdapter):
	"""A spherical box from pgSphere.

	The constructor accepts the two corner points.
	"""
	pgType = "sbox"
	checkedAttributes = ["corner1", "corner2"]
	pattern = re.compile("\([^()]+\)")

	def __init__(self, corner1, corner2):
		self.corner1, self.corner2 = corner1, corner2

	@staticmethod
	def _adaptToPgSphere(sbox):
		return AsIs("sbox '(%s, %s)'"%(sbox.corner1.p(), sbox.corner2.p()))

	@classmethod
	def _castFromPgSphere(cls, value, cursor):
		if value is not None:
			return cls(*[SPoint._castFromPgSphere(ptLit, cursor)
				for ptLit in cls.pattern.findall(value)])

	@classmethod
	def fromSIAPPars(cls, ra, dec, raSize, decSize):
		"""returns an SBox corresponding to what SIAP passes in.

		In particular, all values are in degrees, and a cartesian projection
		is assumed.

		This is for use with SIAP and tries to partially implement that silly
		prescription of "folding" over at the poles.  If that happens,
		a TwoSBoxes exception is raised.  It contains two SBoxes that
		should be ORed.  I agree that sucks.  Let's fix SIAP.
		"""
		if 90-abs(dec)<0.1:  # Special handling at the pole
			raSize = 360
		else:
			raSize = raSize/math.cos(dec*DEG)
		decSize = abs(decSize) # inhibit auto swapping of points
		minRA, maxRA = ra-raSize/2., ra+raSize/2.
		bottom, top = dec-decSize/2., dec+decSize/2.
		# folding over at the poles: raise an exception with two boxes,
		# and let upstream handle it.  Foldover on both poles is not supported.
		# All this isn't really thought out and probably doesn't work in
		# many interesting cases.
		# I hate that folding over.
		if bottom<-90 and top>90:
			raise ValueError("Cannot fold over at both poles")
		elif bottom<-90:
			raise TwoSBoxes(
				cls(
					SPoint.fromDegrees(minRA, -90), 
					SPoint.fromDegrees(maxRA, top)),
				cls(
					SPoint.fromDegrees(180+minRA, -90),
					SPoint.fromDegrees(180+maxRA, top)))
		elif top>90:
			raise TwoSBoxes(
				cls(
					SPoint.fromDegrees(minRA, bottom), 
					SPoint.fromDegrees(maxRA, 90)),
				cls(
					SPoint.fromDegrees(180+minRA, bottom),
					SPoint.fromDegrees(180+maxRA, 90)))
		return cls(SPoint.fromDegrees(minRA, bottom), 
			SPoint.fromDegrees(maxRA, top))

	def asSTCS(self, systemString):
		return removeTrailingZeroes("PositionInterval %s %s %s"%(systemString, 
			"%.10f %.10f"%(self.corner1.x/DEG, self.corner1.y/DEG),
			"%.10f %.10f"%(self.corner2.x/DEG, self.corner2.y/DEG)))

	def asPoly(self):
		x1, y1 = self.corner1.x, self.corner1.y
		x2, y2 = self.corner2.x, self.corner2.y
		minX, maxX = min(x1, x2), max(x1, x2)
		minY, maxY = min(y1, y2), max(y1, y2)
		return SPoly((
			SPoint(minX, minY), 
			SPoint(minX, maxY),
			SPoint(maxX, maxY),
			SPoint(maxX, minY)))

try:
	import psycopg2
	from psycopg2.extensions import (register_adapter, AsIs, register_type,
		new_type)

	_getPgSClass = codetricks.buildClassResolver(PgSAdapter, globals().values(),
		key=lambda obj: obj.pgType, default=PgSAdapter)


	def preparePgSphere(conn):
		if hasattr(psycopg2, "_pgsphereLoaded"):
			return
		try:
			oidmap = _query(conn, 
				"SELECT typname, oid"
				" FROM pg_type"
				" WHERE typname ~ '^s(point|trans|circle|line|ellipse|poly|path|box)'")
			for typeName, oid in oidmap:
				cls = _getPgSClass(typeName)
				if cls is not PgSAdapter:  # base class is null value
					register_adapter(cls, cls._adaptToPgSphere)
					register_type(
						new_type((oid,), "spoint", cls._castFromPgSphere))
				psycopg2._pgsphereLoaded = True
			conn.commit()
		except:
			psycopg2._pgsphereLoaded = False
			raise

except ImportError:
	# psycopg2 not installed.  Since preparsePgSphere can only be
	# called from code depending on psycopg2, there's not harm if
	# we don't define it.
	pass


def _test():
	import doctest, pgsphere
	doctest.testmod(pgsphere)


if __name__=="__main__":
	_test()
