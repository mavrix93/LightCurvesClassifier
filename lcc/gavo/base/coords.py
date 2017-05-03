"""
(Mostly deprecated) code to handle coordinate systems and transform 
between them.  

Basically all of this should be taken over by stc and astropysics.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import math
import new
from math import sin, cos, pi #noflake: exported names
import re
import warnings


from gavo import utils
from gavo.utils import DEG
from gavo.utils import pgsphere
from gavo.utils import pyfits


class PyWCSLoader(object):
	"""A quick hack to save time on startup: delay (slow) loading of pywcs
	until it is used (which it may not be at all in many GAVO programs).
	"""
	def __getattr__(self, *args):
		import pywcs
		globals()["pywcs"] = pywcs
		return getattr(pywcs, *args)

pywcs = PyWCSLoader()


fitsKwPat = re.compile("[A-Z0-9_-]{1,8}$")

def makePyfitsFromDict(d):
	"""returns a pyfits header with the cards of d.items().

	Only keys "looking like" FITS header keywords are used, i.e. all-uppercase
	and shorter than 9 characters.
	"""
	res = pyfits.Header()
	for key, val in d.iteritems():
		if fitsKwPat.match(key) and val is not None:
			res.update(str(key), val)
	return res



_wcsTestDict = {
	"CRVAL1": 0,   "CRVAL2": 0, "CRPIX1": 50,  "CRPIX2": 50,
	"CD1_1": 0.01, "CD1_2": 0, "CD2_1": 0,    "CD2_2": 0.01,
	"NAXIS1": 100, "NAXIS2": 100, "CUNIT1": "deg", "CUNIT2": "deg",
	"CTYPE1": 'RA---TAN-SIP', "CTYPE2": 'DEC--TAN-SIP', "LONPOLE": 180.,
}


def getBbox(points):
	"""returns a bounding box for the sequence of 2-sequences points.

	The thing returned is a coords.Box.

	>>> getBbox([(0.25, 1), (-3.75, 1), (-2, 4)])
	Box((0.25,4), (-3.75,1))
	"""
	xCoos, yCoos = [[p[i] for p in points] for i in range(2)]
	return Box(min(xCoos), max(xCoos), min(yCoos), max(yCoos))


def clampAlpha(alpha):
	while alpha>360:
		alpha -= 360
	while alpha<0:
		alpha += 360
	return alpha


def clampDelta(delta):
	return max(-90, min(90, delta))


def _calcFootprintMonkeypatch(self, hdr=None, undistort=True):
	"""returns the coordinates of the four corners of an image.

	This is for monkeypatching pywcs, which at least up to 1.11 does
	really badly when non-spatial coordinates are present.  This method
	relies on the _monkey_naxis_lengths attribute left by getWCS to
	figure out the axis lengths.

	pywcs' hdr argument is always ignored here.
	"""
	naxis1, naxis2 = self._monkey_naxis_lengths
	corners = [[1,1],[1,naxis2], [naxis1,naxis2], [naxis1, 1]]
	if undistort:
		return self.all_pix2sky(corners, 1)
	else:
		return self.wcs_pix2sky(corners,1)


def _monkeypatchWCS(wcsObj, naxis, wcsFields):
	"""monkeypatches pywcs instances for DaCHS' purposes.
	"""
	wcsObj._dachs_header = wcsFields
	wcsObj.longAxis = naxis[0]
	if len(naxis)>1:
		wcsObj.latAxis = naxis[1]
	wcsObj._monkey_naxis_lengths = [wcsFields.get("NAXIS%d"%i)
		for i in naxis]
	wcsObj.origCalcFootprint = wcsObj.calcFootprint
	wcsObj.calcFootprint = new.instancemethod(_calcFootprintMonkeypatch, 
		wcsObj, wcsObj.__class__)


def getWCS(wcsFields, naxis=(1,2), relax=True):
	"""returns a WCS instance from wcsFields
	
	wcsFields can be either a dictionary or a pyfits header giving
	some kind of WCS information, or an pywcs.WCS instance that is
	returned verbatim.

	This will return None if no (usable) WCS information is found in the header.

	We monkeypatch the resulting pywcs structure quite a bit.  Among
	others:

	* calcFootprint takes into account the naxis kw parameter
	* there's longAxis and latAxis attributes taken from naxis
	* there's _dachs_header, containing the incoming k-v pairs
	* there's _monkey_naxis_length, the lengths along the WCS axes.
	"""
	if isinstance(wcsFields, pywcs.WCS):
		return wcsFields
	if isinstance(wcsFields, dict):
		wcsFields = makePyfitsFromDict(wcsFields)

	# pywcs will invent identity transforms if no WCS keys are present.
	# Hence. we do some sanity checking up front to weed those out.
	if (not wcsFields.has_key("CD1_1") 
			and not wcsFields.has_key("CDELT1")
			and not wcsFields.has_key("PC1_1")):
		return None
	
	# workaround for a bug in pywcs 1.11: .*_ORDER=0 must not happen
	for key in ["AP_ORDER", "BP_ORDER", "A_ORDER", "B_ORDER"]:
		if wcsFields.get(key)==0:
			del wcsFields[key]
	
	wcsObj = pywcs.WCS(wcsFields, relax=relax, naxis=naxis)
	_monkeypatchWCS(wcsObj, naxis, wcsFields)
	return wcsObj


def pix2sky(wcsFields, pixels):
	"""returns the sky coordindates for the 2-sequence pixels.

	(this is a thin wrapper intended to abstract for pix2sky's funky
	calling convention; also, we fix on the silly "0 pixel is 1 convention")
	"""
	wcsObj = getWCS(wcsFields)
	val = wcsObj.all_pix2sky((pixels[0],), (pixels[1],), 1)
	return val[0][0], val[1][0]


def sky2pix(wcsFields, longLat):
	"""returns the pixel coordindates for the 2-sequence longLad.

	(this is a thin wrapper intended to abstract for sky2pix's funky
	calling convention; also, we fix on the silly "0 pixel is 1 convention")
	"""
	val = getWCS(wcsFields).wcs_sky2pix((longLat[0],), (longLat[1],), 1)
	return val[0][0], val[1][0]


def getPixelSizeDeg(wcsFields):
	"""returns the sizes of a pixel at roughly the center of the image for
	wcsFields.

	Near the pole, this gets a bit weird; we do some limitation of the width
	of RA pixels there.
	"""
	wcs = getWCS(wcsFields)
	width, height = wcs._dachs_header["NAXIS1"], wcs._dachs_header["NAXIS2"]
	cosDelta = max(0.01, math.cos(pix2sky(wcs, (width/2, height/2))[1]*DEG))

	p0 = pix2sky(wcs, (width/2, height/2))
	p1 = pix2sky(wcs, (width/2+1, height/2))
	p2 = pix2sky(wcs, (width/2, height/2+1))
	return abs(p1[0]-p0[0])*cosDelta, abs(p2[1]-p0[1])


def getWCSTrafo(wcsFields):
	"""returns a callable transforming pixel to physical coordinates.

	wcsFields is passed to getWCS, see there for legal types.
	"""
	wcs = getWCS(wcsFields)
	return lambda x, y: pix2sky(wcs, (x, y))


def getInvWCSTrafo(wcsFields):
	"""returns a callable transforming physical to pixel coordinates.

	wcsFields is passed to getWCS, see there for legal types.
	"""
	wcs = getWCS(wcsFields)
	return lambda ra, dec: sky2pix(wcs, (ra,dec))


def getBboxFromWCSFields(wcsFields):
	"""returns a bbox and a field center for WCS FITS header fields.

	wcsFields is passed to getWCS, see there for legal types.

	Warning: this is different from wcs.calcFootprint in that
	we keep negative angles if the stitching line is crossed; also,
	no distortions or anything like that are taken into account.

	This code is only used for bboxSIAP, and you must not use it
	for anything else; it's going to disappear with it.
	"""
 	wcs = getWCS(wcsFields)
	width, height = float(wcs._dachs_header["NAXIS1"]
		), float(wcs._dachs_header["NAXIS2"])
	cA, cD = pix2sky(wcs, (width/2., height/2.))
	wA, wD = getPixelSizeDeg(wcs)
	wA *= width/2.
	wD *= height/2.
	# Compute all "corners" to ease handling of corner cases
	bounds = [(cA+wA, cD+wD), (cA-wA, cD-wD), (cA+wA, cD-wD),
		(cA-wA, cD+wD)]
	bbox = getBbox(bounds)
	if bbox[0][1]>89:
		bbox = Box((0, clampDelta(bbox[0][1])), (360, clampDelta(bbox[1][1])))
	if bbox[1][1]<-89:
		bbox = Box((0, clampDelta(bbox[0][1])), (360, clampDelta(bbox[1][1])))
	return bbox


def getSpolyFromWCSFields(wcsFields):
	"""returns a pgsphere spoly corresponding to wcsFields

	wcsFields is passed to getWCS, see there for legal types.

	The polygon returned is computed by using the four corner points
	assuming a rectangular image.
	"""
	wcs = getWCS(wcsFields)
	return pgsphere.SPoly([pgsphere.SPoint.fromDegrees(*p)
		for p in wcs.calcFootprint(wcs._dachs_header)])


def getCenterFromWCSFields(wcsFields):
	"""returns RA and Dec of the center of an image described by wcsFields.

	Well, this isn't very general; actually, we just use the first two axes.
	This should probably be fixed once we might get to see cubes here.
	"""
	wcs = getWCS(wcsFields)
	return pix2sky(wcs, (wcs._dachs_header["NAXIS1"]/2., 
		wcs._dachs_header["NAXIS2"]/2.))


# let's do a tiny vector type.  It's really not worth getting some dependency
# for this.
class Vector3(object):
	"""is a 3d vector that responds to both .x... and [0]...

	>>> x, y = Vector3(1,2,3), Vector3(2,3,4)
	>>> x+y
	Vector3(3.000000,5.000000,7.000000)
	>>> 4*x
	Vector3(4.000000,8.000000,12.000000)
	>>> x*4
	Vector3(4.000000,8.000000,12.000000)
	>>> x*y
	20
	>>> "%.6f"%abs(x)
	'3.741657'
	>>> print abs((x+y).normalized())
	1.0
	"""
	def __init__(self, x, y=None, z=None):
		if isinstance(x, tuple):
			self.coos = x
		else:
			self.coos = (x, y, z)

	def __repr__(self):
		return "Vector3(%f,%f,%f)"%tuple(self.coos)

	def __str__(self):
		def cutoff(c):
			if abs(c)<1e-10:
				return 0
			else:
				return c
		rounded = [cutoff(c) for c in self.coos]
		return "[%.2g,%.2g,%.2g]"%tuple(rounded)

	def __getitem__(self, index):
		return self.coos[index]

	def __mul__(self, other):
		"""does either scalar multiplication if other is not a Vector3, or
		a scalar product.
		"""
		if isinstance(other, Vector3):
			return self.x*other.x+self.y*other.y+self.z*other.z
		else:
			return Vector3(self.x*other, self.y*other, self.z*other)
	
	__rmul__ = __mul__

	def __div__(self, scalar):
		return Vector3(self.x/scalar, self.y/scalar, self.z/scalar)

	def __add__(self, other):
		return Vector3(self.x+other.x, self.y+other.y, self.z+other.z)

	def __sub__(self, other):
		return Vector3(self.x-other.x, self.y-other.y, self.z-other.z)

	def __abs__(self):
		return math.sqrt(self.x**2+self.y**2+self.z**2)

	def cross(self, other):
		return Vector3(self.y*other.z-self.z*other.y,
			self.z*other.x-self.x*other.z,
			self.x*other.y-self.y*other.x)

	def normalized(self):
		return self/abs(self)

	def getx(self): return self.coos[0]
	def setx(self, x): self.coos[0] = x
	x = property(getx, setx)
	def gety(self): return self.coos[1]
	def sety(self, y): self.coos[1] = y
	y = property(gety, sety)
	def getz(self): return self.coos[2]
	def setz(self, z): self.coos[2] = z
	z = property(getz, setz)


class Box(object):
	"""is a 2D box.

	The can be constructed either with two tuples, giving two points
	delimiting the box, or with four arguments x0, x1, y0, y1.

	To access the thing, you can either access the x[01], y[01] attributes
	or use getitem to retrieve the upper right and lower left corner.

	The slightly silly ordering of the bounding points (larger values
	first) is for consistency with Postgresql.

	Boxes can be serialized to/from Postgresql BOXes.

	>>> b1 = Box(0, 1, 0, 1)
	>>> b2 = Box((0.5, 0.5), (1.5, 1.5))
	>>> b1.overlaps(b2)
	True
	>>> b2.contains(b1)
	False
	>>> b2.contains(None)
	False
	>>> b2[0]
	(1.5, 1.5)
	"""
	def __init__(self, x0, x1, y0=None, y1=None):
		if y0 is None:
			x0, y0 = x0
			x1, y1 = x1
		lowerLeft = (min(x0, x1), min(y0, y1))
		upperRight = (max(x0, x1), max(y0, y1))
		self.x0, self.y0 = upperRight
		self.x1, self.y1 = lowerLeft
	
	def __getitem__(self, index):
		if index==0 or index==-2:
			return (self.x0, self.y0)
		elif index==1 or index==-1:
			return (self.x1, self.y1)
		else:
			raise IndexError("len(box) is always 2")

	def __str__(self):
		return "((%.4g,%.4g), (%.4g,%.4g))"%(self.x0, self.y0, self.x1, self.y1)

	def __repr__(self):
		return "Box((%g,%g), (%g,%g))"%(self.x0, self.y0, self.x1, self.y1)

	def overlaps(self, other):
		if other is None:
			return False
		return not (
			(self.x1>other.x0 or self.x0<other.x1) or
			(self.y1>other.y0 or self.y0<other.y1))

	def contains(self, other):
		if other is None:
			return False

		if isinstance(other, Box):
			return (self.x0+1e-10>=other.x0 and self.x1-1e-10<=other.x1 and
				self.y0+1e-10>=other.y0 and self.y1-1e-10<=other.y1)
		else: # other is assumed to be a 2-sequence interpreted as a point.
			x, y = other
			return self.x0>=x>=self.x1 and self.y0>=y>=self.y1
	
	def translate(self, vec):
		dx, dy = vec
		return Box((self.x0+dx, self.y0+dy), (self.x1+dx, self.y1+dy))


# tell sqlsupport about the box
try:
	from gavo.base import sqlsupport

	class BoxAdapter(object):
		"""is an adapter for coords.Box instances to SQL boxes.
		"""
		def __init__(self, box):
			self._box = box

		def prepare(self, conn):
			pass

		def getquoted(self):
			# "'(%s,%s)'"%self._box would work as well, but let's be conservative
			# here
			res = "'((%f, %f), (%f, %f))'"%(self._box.x0, self._box.y0,
				self._box.x1, self._box.y1)
			return res

	sqlsupport.registerAdapter(Box, BoxAdapter)

	# XXX TODO: I'm using a fixed oid here because I don't want to do
	# a db connection during import to find out OIDs.  This *should*
	# work fine, but really it should be delegated into a "connection set-up"
	# type thing.  Hm.
	_BOX_OID = 603

	def castBox(value, cursor):
		"""makes coords.Box instances from SQL boxes.
		"""
		if value:
			vals = map(float, re.match(r"\(([\d.+eE-]+),([\d.+eE-]+)\),"
				"\(([\d.+eE-]+),([\d.+eE-]+)\)", value).groups())
			return Box(vals[0], vals[2], vals[1], vals[3])
	
	sqlsupport.registerType((_BOX_OID,), "BOX", castBox)

except:
	import traceback
	traceback.print_exc()
	warnings.warn("Failed to register Box adapter with sqlsupport.  Expect"
		" trouble with siap")


def sgn(a):
	if a<0:
		return -1
	elif a>0:
		return 1
	else:
		return 0


def computeUnitSphereCoords(alpha, delta):
# TODO: replaced by mathtricks.spherToCart
	"""returns the 3d coordinates of the intersection of the direction
	vector given by the spherical coordinates alpha and delta with the
	unit sphere.

	alpha and delta are given in degrees.

	>>> print computeUnitSphereCoords(0,0)
	[1,0,0]
	>>> print computeUnitSphereCoords(0, 90)
	[0,0,1]
	>>> print computeUnitSphereCoords(90, 90)
	[0,0,1]
	>>> print computeUnitSphereCoords(90, 0)
	[0,1,0]
	>>> print computeUnitSphereCoords(180, -45)
	[-0.71,0,-0.71]
	"""
	return Vector3(*utils.spherToCart(alpha*DEG, delta*DEG))


def dirVecToCelCoos(dirVec):
	"""returns alpha, delta in degrees for the direction vector dirVec.

	>>> dirVecToCelCoos(computeUnitSphereCoords(25.25, 12.125))
	(25.25, 12.125)
	>>> dirVecToCelCoos(computeUnitSphereCoords(25.25, 12.125)*16)
	(25.25, 12.125)
	>>> "%g,%g"%dirVecToCelCoos(computeUnitSphereCoords(25.25, 12.125)+
	...   computeUnitSphereCoords(30.75, 20.0))
	'27.9455,16.0801'
	"""
	dirVec = dirVec.normalized()
	alpha = math.atan2(dirVec.y, dirVec.x)
	if alpha<0:
		alpha += 2*math.pi
	return alpha*180./math.pi, math.asin(dirVec.z)*180./math.pi


def getTangentialUnits(cPos):
	"""returns the unit vectors for RA and Dec at the unit circle position cPos.

	We compute them by solving u_1*p_1+u_2*p_2=0 (we already know that
	u_3=0) simultaneously with u_1^2+u_2^2=1 for RA, and by computing the
	cross product of the RA unit and the radius vector for dec.

	This becomes degenerate at the poles.  If we're exactly on a pole,
	we *define* the unit vectors as (1,0,0) and (0,1,0).

	Orientation is a pain -- the convention used here is that unit delta
	always points to the pole.

	>>> cPos = computeUnitSphereCoords(45, -45)
	>>> ua, ud = getTangentialUnits(cPos)
	>>> print abs(ua), abs(ud), cPos*ua, cPos*ud
	1.0 1.0 0.0 0.0
	>>> print ua, ud
	[-0.71,0.71,0] [-0.5,-0.5,-0.71]
	>>> ua, ud = getTangentialUnits(computeUnitSphereCoords(180, 60))
	>>> print ua, ud
	[0,-1,0] [0.87,0,0.5]
	>>> ua, ud = getTangentialUnits(computeUnitSphereCoords(0, 60))
	>>> print ua, ud
	[0,1,0] [-0.87,0,0.5]
	>>> ua, ud = getTangentialUnits(computeUnitSphereCoords(0, -60))
	>>> print ua, ud
	[0,1,0] [-0.87,0,-0.5]
	"""
	try:
		normalizer = 1/math.sqrt(cPos.x**2+cPos.y**2)
	except ZeroDivisionError:
		return Vector3(1,0,0), Vector3(0,1,0)
	alphaUnit = normalizer*Vector3(cPos.y, -cPos.x, 0)
	deltaUnit = normalizer*Vector3(cPos.x*cPos.z, cPos.y*cPos.z,
		-cPos.x**2-cPos.y**2)
	# now orient the vectors: in delta, we always look towards the pole
	if sgn(cPos.z)!=sgn(deltaUnit.z):
		deltaUnit = -1*deltaUnit  # XXX this breaks on the equator
	# The orientation of alphaUnit depends on the hemisphere
	if cPos.z<0:  # south
		if deltaUnit.cross(alphaUnit)*cPos<0:
			alphaUnit = -1*alphaUnit
	else:  # north
		if deltaUnit.cross(alphaUnit)*cPos>0:
			alphaUnit = -1*alphaUnit
	return alphaUnit, deltaUnit


def movePm(alphaDeg, deltaDeg, pmAlpha, pmDelta, timeDiff, foreshort=0):
	"""returns alpha and delta for an object with pm pmAlpha after timeDiff.

	pmAlpha has to have cos(delta) applied, everything is supposed to be
	in degrees, the time unit is yours to choose.
	"""
	alpha, delta = alphaDeg/180.*math.pi, deltaDeg/180.*math.pi
	pmAlpha, pmDelta = pmAlpha/180.*math.pi, pmDelta/180.*math.pi
	sd, cd = math.sin(delta), math.cos(delta)
	sa, ca = math.sin(alpha), math.cos(alpha)
	muAbs = math.sqrt(pmAlpha**2+pmDelta**2);
	muTot = muAbs+0.5*foreshort*timeDiff;

	if muAbs<1e-20:
		return alphaDeg, deltaDeg
	# this is according to Mueller, 115 (4.94)
	dirA = pmAlpha/muAbs;
	dirD = pmDelta/muAbs;
	sinMot = sin(muTot*timeDiff);
	cosMot = cos(muTot*timeDiff);

	dirVec = Vector3(-sd*ca*dirD*sinMot - sa*dirA*sinMot + cd*ca*cosMot,
		-sd*sa*dirD*sinMot + ca*dirA*sinMot + cd*sa*cosMot,
		+cd*dirD*sinMot + sd*cosMot)
	return dirVecToCelCoos(dirVec)


def getGCDist(pos1, pos2):
	"""returns the distance along a great circle between two points.

	The distance is in degrees, the input positions are in degrees.
	"""
	scalarprod = computeUnitSphereCoords(*pos1)*computeUnitSphereCoords(*pos2)
	# cope with numerical trouble
	if scalarprod>=1:
		return 0
	return math.acos(scalarprod)/DEG


def _test():
	import doctest, coords
	doctest.testmod(coords)


if __name__=="__main__":
	_test()
