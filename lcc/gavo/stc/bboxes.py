"""
Computing bboxes for STC geometries.

A bbox coming out of this module is a 4-tuple of (ra0, de0, ra1, de1) in
ICRS degrees.

(You're right, this should be part of the dm classes; but it's enough
messy custom code that I found it nicer to break it out).
"""

#c Copyright 2008-2016, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import math
from math import sin, cos, tan, atan, acos

from gavo import utils
from gavo.stc import common
from gavo.stc import conform
from gavo.stc import stcsast

from gavo.utils import DEG

############### Some spherical geometry calculations
# (most due to Chamberlain and Duquette, "Some Algorithms for Polygons on
# a sphere", http://hdl.handle.net/2014/40409)


def getHeading(long1, lat1, long2, lat2):
	"""returns the initial heading when going from one spherical position to
	another along a great circle.

	Everything is in rad, angle is counted north over east.
	"""
	if abs(long1-long2)<=1e-10:
		# along a meridian
		if lat1<lat2:
			return 0
		else:
			return math.pi

	if lat1<=-math.pi/2+1e-10:
		#	starting on south pole
		return 0
	elif lat1>=math.pi/2-1e-10: 
		#	starting on north pole
		return math.pi

	zeta = utils.spherDist(
		utils.spherToCart(long1, lat1),
		utils.spherToCart(long2, lat2))
	cosPhi = (sin(lat2)-sin(lat1)*cos(zeta))/(sin(zeta)*cos(lat1))
	if abs(cosPhi-1)<1e-10:
		return 0
	elif abs(cosPhi+1)<1e-10:
		return math.pi
	elif sin(long2-long1)>0:
		return acos(cosPhi)
	else:
		return common.TWO_PI-acos(cosPhi)


class GCSegment(object):
	"""A great circle segment on a sphere.  It is assumed that it's no larger
	than pi.

	Construction is long,lat, long, lat in rad (or use the fromDegrees
	class method.

	Very small (<1e-8 rad, say) segments are not supported.  You should
	probably work in the tangential plane on that kind of scale.
	"""
	def __init__(self, long1, lat1, long2, lat2):
		self.long1, self.lat1 = long1, lat1
		self.long2, self.lat2 = long2, lat2
		self._normalize()
		if self.long1>self.long2:
			self.long1, self.long2 = self.long2, self.long1
			self.lat1, self.lat2 = self.lat2, self.lat1
		
		vertical = abs(self.long1-self.long2)<1e-10
		if vertical and abs(self.lat1-self.lat2)<1e-10:
			raise ValueError("Null segment: start and end are identical")

		self.overPole = vertical or cos(lat1)*cos(lat2)<1e-10
		self.overStich = 2*math.pi<=self.long1+self.long2<3*math.pi

	@classmethod
	def fromDegrees(cls, long1, lat1, long2, lat2):
		return cls(long1*DEG, lat1*DEG, long2*DEG, lat2*DEG)

	def __str__(self):
		return "<Great Circle through (%f %f), (%f %f)"%(
			self.long1/DEG, self.lat1/DEG, self.long2/DEG, self.lat2/DEG)

	def _normalize(self):
		"""makes sure all longitudes are in [0, 2 pi[ and all latitudes between
		[-pi, pi].
		"""
		self.long1 = common.clampLong(self.long1)
		self.long2 = common.clampLong(self.long2)
		self.lat1 = common.clampLat(self.lat1)
		self.lat2 = common.clampLat(self.lat2)

	def _computeBBFor(self, long1, lat1, long2, lat2):
		"""returns a 4-tuple bounding box for a great circle segment.

		This is restricted to GCs not crossing the stitch line; furthermore, it
		still depends on self.
		"""
		if self.overPole:
			latMin, latMax  = min(lat1, lat2), max(lat1, lat2)
			if cos(lat1)*cos(lat2)<1e-10:
				# the pole is part of the segment
				long1, long2 = 0, common.TWO_PI

		else:
			# compute headings at both ends
			theta1 = getHeading(long1, lat1, long2, lat2)
			theta2 = getHeading(long2, lat2, long1, lat1)

			# if the headings are two quadrants apart, the limits are at
			# the corners
			quad1, quad2 = int(2*theta1/math.pi), int(2*theta2/math.pi)
			if abs(quad1-quad2)==2:
				latExt = lat1
			else:
				# the limit is somewhere in between.
				latExt = acos(abs(sin(theta1))*cos(lat1))
				# acos has two branches; inspecting lat1 for the sign is
				# enough since latExt won't be extreme when sgn(lat1)!=sgn(lat2).
				if lat1<0:
					latExt = -latExt

			latMin = min(latExt, lat1, lat2)
			latMax = max(latExt, lat1, lat2)
		return (long1, latMin, long2, latMax)

	def latForLong(self, long):
		"""returns the latitude the great circle is on for a given longitude.

		Input and output is in rad.

		If the pole is part of the great circle, a constant (but fairly
		meaningless) value is returned.
		"""
		if self.overPole:
			return self.long1
		return atan(
			tan(self.lat1)*(sin(long-self.long2)/sin(self.long1-self.long2))
			-tan(self.lat2)*(sin(long-self.long1)/sin(self.long1-self.long2)))

	def getBBs(self):
		"""returns a sequence of bounding boxes for this great circle segment.

		Actually, the sequence contains one box for a segment that does not
		cross the stitching line, two boxes for those that do.
		"""
		if not self.overPole and common.TWO_PI<=self.long1+self.long2<3*math.pi:
			# segment crosses stitch line, split it up
			latAtStich = self.latForLong(0)
			return [
				self._computeBBFor(0, latAtStich, self.long1, self.lat1),
				self._computeBBFor(self.long2, self.lat2, 2*math.pi, latAtStich)]
		else:
			return [
				self._computeBBFor(self.long1, self.lat1, self.long2, self.lat2)]


#############################################################
# Actual bbox hacks.  I'm pretty sure there's loads of bad
# corner cases in here.  In particular in the vicinity of the
# pole, *much* more thought and testing is required (I'm hoping
# astropy will come to the rescue at some point).

@utils.memoized
def getStandardFrame():
	return stcsast.parseSTCS("Position ICRS unit deg")


def _makeSphericalBbox(minRA, minDec, maxRA, maxDec):
	"""yields one or two bboxes from for spherical coordinates.

	This handles crossing the stich line as well as shooting over the pole.

	Everything here is in degrees.

	This function assumes that -360<minRA<maxRA<720 and that at least one
	of minRA, maxRA is between 0 and 360.
	"""
	if minDec<-90:
		# fold over the pole
		maxDec = max(maxDec, -minDec-180)
		minDec = -90
		minRA, maxRA = 0, 360

	if maxDec>90:
		# fold over the pole
		minDec = min(minDec, 180-maxDec)
		maxDec = 90
		minRA, maxRA = 0, 360

	if minRA<0:
		yield (0, minDec, maxRA, maxDec)
		yield (360+minRA, minDec, 360, maxDec)
	elif maxRA>360:
		yield (0, minDec, maxRA-360, maxDec)
		yield (minRA, minDec, 360, maxDec)
	else:
		yield (minRA, minDec, maxRA, maxDec)


def _intersectBboxes(bbox1, bbox2):
	"""returns the intersection of the two bboxes.
	"""
	return (
		max(bbox1[0], bbox2[0]),
		max(bbox1[1], bbox2[1]),
		min(bbox1[2], bbox2[2]),
		min(bbox1[3], bbox2[3]))


def _isEmpty(bbox):
	"""returns true if bbox is empty.
	"""
	return bbox[0]>=bbox[2] or bbox[1]>=bbox[3]


def _computeIntersectionForSequence(seq1, seq2):
	"""helps _computeIntersection; see comment there.
	"""
	if seq1 is None:
		return seq2
	if seq2 is None:
		return seq1

	commonBoxes = []
	for box1 in seq1:
		for box2 in seq2:
			commonBox = _intersectBboxes(box1, box2)
			if not _isEmpty(commonBox):
				commonBoxes.append(commonBox)
	return commonBoxes


def _computeCircleBbox(circle):
	"""helps _getBboxesFor.
	"""
	return _makeSphericalBbox(
		circle.center[0]-circle.radius,
		circle.center[1]-circle.radius,
		circle.center[0]+circle.radius,
		circle.center[1]+circle.radius)


def _computeEllipseBbox(ellipse):
	"""helps _getBboxesFor.

	TODO: Make tighter by actually using minor axis.
	"""
	return _makeSphericalBbox(
		ellipse.center[0]-ellipse.smajAxis,
		ellipse.center[1]-ellipse.smajAxis,
		ellipse.center[0]+ellipse.smajAxis,
		ellipse.center[1]+ellipse.smajAxis)


def _computeBoxBbox(box):
	"""helps _getBboxesFor.

	Note that the box boundaries are great circles.
	"""
	maxDec = max(-90, min(90, box.center[1]+box.boxsize[1]))
	minDec = max(-90, min(90, box.center[1]-box.boxsize[1]))

	if maxDec>90-1e-10:
		yield (0, minDec, 360, 90)
		return
	if minDec<-90+1e-10:
		yield (0, -90, 360, maxDec)
		return

	upperBBs = GCSegment.fromDegrees(
		box.center[0]-box.boxsize[0], maxDec,
		box.center[0]+box.boxsize[0], maxDec
		).getBBs()
	lowerBBs = GCSegment.fromDegrees(
		box.center[0]-box.boxsize[0], minDec,
		box.center[0]+box.boxsize[0], minDec
		).getBBs()

	for bbox in _makeSphericalBbox(
			*joinBboxes(fromRad(upperBBs[0]), fromRad(lowerBBs[0]))):
		yield bbox
	if len(upperBBs)==2: # stitching required
		assert len(lowerBBs)==2
		for bbox in _makeSphericalBbox(
				*joinBboxes(fromRad(upperBBs[1]), fromRad(lowerBBs[1]))):
			yield bbox


def _computePolygonBbox(poly):
	"""helps _getBboxesFor.
	"""
	leftBoxes, rightBoxes = [], []

	def addBoxes(b):
		rightBoxes.append(fromRad(b[0]))
		if len(b)>1:
			leftBoxes.append(fromRad(b[1]))

	firstPoint = lastPoint = poly.vertices[0]
	for point in poly.vertices[1:]:
		curSegment = GCSegment.fromDegrees(
			lastPoint[0], lastPoint[1], point[0], point[1])
		addBoxes(list(curSegment.getBBs()))
		lastPoint = point

	try:
		curSegment = GCSegment.fromDegrees(
			lastPoint[0], lastPoint[1], firstPoint[0], firstPoint[1])
	except ValueError: # probably a null segment since the authors
	                   # closed the polygon.  Ignore this.
		pass
	else:
		addBoxes(list(curSegment.getBBs()))

	yield joinBboxes(*rightBoxes)
	if leftBoxes:
		yield joinBboxes(*leftBoxes)


def _computeAllSkyBbox(geo):
	"""helps _getBboxesFor.
	"""
	yield (0, -90, 360, 90)


def _computeSpaceIntervalBbox(geo):
	"""helps _getBboxesFor.

	PositionInterval could have all kinds of weird coordinate systems.
	We only check there's exactly two dimensions and otherwise hope for the
	best.
	"""
	if geo.frame.nDim!=2:
		raise ValueError("Only PositionsIntervals with nDim=2 are supported"
			" for bboxes.")

	lowerLimit = geo.lowerLimit
	if lowerLimit is None:
		lowerLimit = (0, -90)

	upperLimit = geo.upperLimit
	if upperLimit is None:
		upperLimit = (360, 90)
	return _makeSphericalBbox(lowerLimit[0], lowerLimit[1],
		upperLimit[0], upperLimit[1])


def _computeUnionBbox(geo):
	"""helps _getBboxesFor.

	Union is just returning all bboxes from our child geometries.
	"""
	for child in geo.children:
		for bbox in _getBboxesFor(child):
			yield bbox


def _computeIntersectionBbox(geo):
	"""helps _getBboxesFor.
	"""
# This is surprisingly involved, since our children may yield an arbitrary 
#	number of part boxes; each of those could contribute to an intersection.
# To figure out the intersection, we need to intersect each part bbox with
# each other part bbox and keep whatever is non-empty.
	commonBboxes = None
	for child in geo.children:
		commonBboxes = _computeIntersectionForSequence(commonBboxes,
			list(_getBboxesFor(child)))
	for bbox in commonBboxes:
		yield bbox

def _computeDifferenceBbox(geo):
	"""helps _getBboxesFor.

	(we ignore the cut-out).
	"""
	return _getBboxesFor(geo.children[0])

def _computeNotBbox(geo):
	"""helps _getBboxesFor.

	(we ignore the cut-out and always return the entire sky)
	"""
# of course, we could provide a saner implementation of _computeIntersection
# which then would make up to eight bboxes out of such a thing.
# Never mind, people shouldn't do this anyway.
	return _computeAllSkyBbox(geo)



_BBOX_COMPUTERS = {
	"Circle": _computeCircleBbox,
	"Ellipse": _computeEllipseBbox,
	"Box": _computeBoxBbox,
	"Polygon": _computePolygonBbox,
	"AllSky": _computeAllSkyBbox,
	"SpaceInterval": _computeSpaceIntervalBbox,
	"Union": _computeUnionBbox,
	"Intersection": _computeIntersectionBbox,
	"Difference": _computeDifferenceBbox,
	"Not": _computeNotBbox,
}


def _getBboxesFor(geo):
	"""yields one or two bboxes for a conformed geometry.

	Two bboxes are returned when the geometry overlaps the stitching point.

	A geometry is conformed if it's been conformed to what's coming back
	from getStandardFrame() above.
	"""
	geoName = geo.__class__.__name__
	if geoName not in _BBOX_COMPUTERS:
		raise common.STCInternalError("Do now know how to compute the bbox of"
			" %s."%geoName)
	
	for bbox in _BBOX_COMPUTERS[geoName](geo):
		yield bbox


def fromRad(bbox):
	return tuple(a/utils.DEG for a in bbox)


def joinBboxes(*bboxes):
	"""returns a bounding box encompassing all the the bboxes passed in.

	No input bbox must cross the stitching line; they must be normalized,
	i.e., lower left and upper right corners.
	"""
	if not bboxes:
		raise common.InternalError("bbox join without bbox")
	minRA, maxRA = utils.Supremum, utils.Infimum
	minDec, maxDec = utils.Supremum, utils.Infimum

	for ra0, dec0, ra1, dec1 in bboxes:
		minRA = min(minRA, ra0)
		minDec = min(minDec, dec0)
		maxRA = max(maxRA, ra1)
		maxDec = max(maxDec, dec1)
	
	return (minRA, minDec, maxRA, maxDec)


def getBboxes(ast):
	"""iterates over the bboxes of the areas within ast.

	bboxes are (ra0, de0, ra1, de1) in ICRS degrees.
	"""
	astc = conform.conform(ast, getStandardFrame())
	for area in astc.areas:
		for bbox in _getBboxesFor(area):
			yield bbox

