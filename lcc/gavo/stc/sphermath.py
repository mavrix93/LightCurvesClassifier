"""
Spherical geometry and related helper functions.
"""

#c Copyright 2008-2016, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import math
import new
import numpy

from gavo.stc import common
from gavo.stc import units

from gavo.utils.mathtricks import cartToSpher, spherToCart #noflake

# filled in for distances not given, in rad (units also insert this for
# parallaxes too small)
defaultDistance = units.maxDistance*units.onePc/units.oneAU

# Units spherical coordinates have to be in for transformation to/from
# 6-vectors; this is all done in the bowels of SVConverter
_svPosUnit = ("rad", "rad", "AU")
_svVPosUnit = ("rad", "rad", "AU")
_svVTimeUnit = ("d", "d", "d")
# Light speed in AU/d
_lightAUd = 86400.0/499.004782


def getRotX(angle):
	"""returns a 3-rotation matrix for rotating angle radians around x.
	"""
	c, s = math.cos(angle), math.sin(angle)
	return numpy.array([[1, 0, 0], [0, c, s], [0, -s, c]])


def getRotY(angle):
	"""returns a 3-rotation matrix for rotating angle radians around y.
	"""
	c, s = math.cos(angle), math.sin(angle)
	return numpy.array([[c, 0, -s], [0, 1, 0], [s, 0, c]])


def getRotZ(angle):
	"""returns a 3-rotation matrix for rotating angle radians around u.
	"""
	c, s = math.cos(angle), math.sin(angle)
	return numpy.array([[c, s, 0], [-s, c, 0], [0, 0, 1]])


def getMatrixFromEulerAngles(z1, x, z2):
	"""returns a 3-rotation matrix for the z-x-z Euler angles.

	There are some functions to obtain such angles below.
	"""
	return numpy.dot(
		numpy.dot(getRotZ(z2), getRotX(x)), getRotZ(z1))


def getEulerAnglesFromMatrix(matrix):
	"""returns zxz Euler angles from a rotation matrix.

	This is improvised, and someone should look up a numerically sound way
	to do this.
	"""
# while I cannot see why, this clearly is broken in some way.
	z1 = math.atan2(matrix[2,0], -matrix[2,1])
	z2 = math.atan2(matrix[0,2], matrix[1,2])
	x = math.atan2(math.sqrt(matrix[2,0]**2+matrix[2,1]**2), matrix[2,2])
	return z1, x, z2


def getMatrixFromEulerVector(eulerVector):
	"""returns a rotation matrix for an Euler vector.

	An euler vector gives the rotation axis, its magnitude the angle in rad.

	This function is a rip-off of SOFA's rv2m.

	eulerVector is assumed to be a numpy array.
	"""
	x, y, z = eulerVector
	phi = math.sqrt(x**2+y**2+z**2)
	sp, cp = math.sin(phi), math.cos(phi)
	f = 1-cp
	if phi!=0:
		x, y, z = eulerVector/phi
	return numpy.array([
		[x**2*f+cp, x*y*f+z*sp,  x*z*f-y*sp],
		[y*x*f-z*sp, y**2*f+cp, y*z*f+x*sp],
		[z*x*f+y*sp, z*y*f-x*sp, z**2*f+cp]])


def computeTransMatrixFromPole(poleCoo, longZeroCoo, changeHands=False): 
	"""returns a transformation matrix to transform from the reference
	system into a rotated system.

	The rotated system is defined by its pole, the spherical coordinates
	at which it has longitude zero and whether or not it is right handed.

	All angles are in rad.
	"""
# when moving from numpy here, replace this with the like-named
# function from utils.mathtricks.
	x = spherToCart(*longZeroCoo)
	z = spherToCart(*poleCoo)
	if abs(numpy.dot(x, z))>1e-5:
		raise common.STCValueError("%s and %s are not valid pole/zero points for"
			" a rotated coordinate system"%(poleCoo, longZeroCoo))
	y = (z[1]*x[2]-z[2]*x[1], z[2]*x[0]-z[0]*x[2], z[0]*x[1]-z[1]*x[0])
	if changeHands:
		y = (-y[0], -y[1], -y[2])
	return numpy.array([x,y,z])


def vabs(naVec):
	return math.sqrt(numpy.dot(naVec, naVec))


def _ensureSphericalFrame(coo):
	"""raises an error if coo's frame is not suitable for holding spherical
	coordinates.
	XXX TODO: assert spatial and vel coos have the same frame, etc.
	"""
	if not coo.frame.isSpherical():
		raise common.STCValueError("%s is not a valid frame for transformable"
			" spherical coordinates."%(coo.frame))


############## Code for handling relativistic correction in 6-Vector conversion
# Warning: This has massive issues with numerics.  Don't use.

def _pleaseEinsteinToSpher(sv):
	"""undoes relativistic corrections from 6-vector sv.

	This follows sofa's pvstar.  sv is changed in place.
	"""
	radialProj, radialV, tangentialV = _decomposeRadial(sv[:3], sv[3:])
	betaRadial = radialProj/_lightAUd
	betaTangential = vabs(tangentialV)/_lightAUd

	d = 1.0+betaRadial
	w = 1.0-betaRadial**2-betaTangential**2
	if d==0.0 or w<0:
		return
	delta = math.sqrt(w)-1.0
	if betaRadial==0:
		radialV = (betaRadial-delta)/(betaRadial*d)*radialV
	sv[3:] = 1/d*radialV


def _decomposeRadial(r, rd):
	"""returns the components of rd radial and tangential to r.
	"""
	rUnit = r/vabs(r)
	radialProj = numpy.dot(rUnit, rd)
	radialVector = radialProj*rUnit
	tangentialVector = rd-radialVector
	return radialProj, radialVector, tangentialVector


def _solveStumpffEquation(betaR, betaT, maxIter=100):
	"""returns the solution of XXX.

	If the solution fails to converge within maxIter iterations, it
	raises an STCError.
	"""
	curEstR, curEstT = betaR, betaT
	od, odel, odd, oddel = 0, 0, 0, 0
	for i in range(maxIter):
		d = 1.+curEstT
		delta = math.sqrt(1.-curEstR**2-curEstT**2)-1.0
		curEstR = d*betaR+delta
		curEstT = d*betaT
		if i: # check solution so far after at least one iteration
			dd = abs(d-od)
			ddel = abs(delta-odel)
			if dd==odd and ddel==oddel:
				break
			odd = dd
			oddel = ddel
		od = d
		odel = delta
	else:
		raise common.STCError(
			"6-vector relativistic correction failed to converge")
	return curEstR, curEstT, d, delta


def _pleaseEinsteinFromSpher(sv):
	"""applies relativistic corrections to the 6-vector sv.

	This follows sofa's starpv.  sv is changed in place.
	"""
	radialProj, radialV, tangentialV = _decomposeRadial(sv[:3], sv[3:])
	betaRadial = radialProj/_lightAUd
	betaTangential = vabs(tangentialV)/_lightAUd

	betaSR, betaST, d, delta = _solveStumpffEquation(betaRadial, betaTangential)
	# replace old velocity with velocity in inertial system
	if betaSR!=0:
		radialV = (d+delta/betaSR)*radialV
	sv[3:] = radialV+(d*tangentialV)

################# End relativistic code.

class SVConverter(object):
	"""A container for the conversion from spherical coordinates
	to 6-Vectors.

	You create one with an example of your data; these are values
	and units of STC objects, and everything may be None if it's
	not given.

	The resulting object has methods to6 taking values
	like the one provided by you and returning a 6-vector, and from6
	returning a pair of such values.

	Further, the converter has the attributes	distGiven,
	posdGiven, and distdGiven signifying whether these items are
	expected or valid on return.  If posVals is None, no transforms
	can be computed.

	The relativistic=True constructior argument requests that the
	transformation be Lorentz-invariant.  Do not use that, though,
	since there are unsolved numerical issues.

	The slaComp=True constructor argument requests that some
	operations exterior to the construction are done as slalib does
	them, rather than alternative approaches.
	"""
	posGiven = distGiven = posdGiven = distdGiven = True
	defaultDistance = units.maxDistance*units.onePc/units.oneAU

	def __init__(self, posVals, posUnit, velVals=None, velSUnit=None, 
			velTUnit=None, relativistic=False, slaComp=False):
		self.relativistic, self.slaComp = relativistic, slaComp
		self._determineFeatures(posVals, velVals)
		self._computeUnitConverters(posUnit, velSUnit, velTUnit)
		self._makeTo6()
		self._makeFrom6()

	def _determineFeatures(self, posVals, velVals):
		if posVals is None:
			# No position has been given; that is possible if only "wiggles"
			# were specified.  We'd have to transform those, too, but we
			# don't for now.
			self.distGiven = self.posdGiven = False
			self._velDefault = None
			return

		if len(posVals)==2:
			self.distGiven = False
		if velVals is None:
			self.posdGiven = False
			self._velDefault = None
		else:
			if len(velVals)==2:
				self.distdGiven = False
				self._velDefault = (0,0)
			else:
				self._velDefault = (0,0,0)

	def _computeUnitConverters(self, posUnit, velSUnit, velTUnit):
		dims = len(posUnit)
		self.toSVUnitsPos = units.getVectorConverter(posUnit, 
			_svPosUnit[:dims])
		self.fromSVUnitsPos = units.getVectorConverter(posUnit, 
			_svPosUnit[:dims], True)
		if self.posdGiven:
			dims = len(velSUnit)
			self.toSVUnitsVel = units.getVelocityConverter(velSUnit, velTUnit,
				_svVPosUnit[:dims], _svVTimeUnit[:dims])
			self.fromSVUnitsVel = units.getVelocityConverter(velSUnit, velTUnit,
				_svVPosUnit[:dims], _svVTimeUnit[:dims], True)

	def _makeTo6(self):
		velDefault = ""
		if not self.posdGiven:
			velDefault = "=None"
		code = ["def to6(self, pos, vel%s):"%velDefault]
		code.append("  pos = self.toSVUnitsPos(pos)")
		if self.posdGiven:
			code.append("  vel = self.toSVUnitsVel(vel)")
		if not self.distGiven:
			code.append("  pos = pos+(defaultDistance,)")
		if self.posdGiven:
			if not self.distdGiven:
				code.append("  vel = vel+(0,)")
		else:
			code.append("  vel = (0,0,0)")
		code.append("  (alpha, delta, r), (alphad, deltad, rd) = pos, vel")
		code.append("  sa, ca = math.sin(alpha), math.cos(alpha)")
		code.append("  sd, cd = math.sin(delta), math.cos(delta)")
		code.append("  x, y = r*cd*ca, r*cd*sa")
		code.append("  w = r*deltad*sd-cd*rd")
		code.append("  res = numpy.array([x, y, r*sd,"
			" -y*alphad-w*ca, x*alphad-w*sa, r*deltad*cd+sd*rd])")
		if self.relativistic:
			code.append("  _pleaseEinsteinFromSpher(res)")
		code.append("  return res")
		l = locals()
		exec "\n".join(code) in globals() , l
		self.to6 = new.instancemethod(l["to6"], self)

	def _makeFrom6(self):
		code = ["def from6(self, sv):"]
		if self.relativistic:
			code.append("  _pleaseEinsteinFromSpher(sv)")
		code.append("  pos, vel = self._svToSpherRaw(sv)")
		if not self.distGiven:
			code.append("  pos = pos[:2]")
		code.append("  pos = self.fromSVUnitsPos(pos)")
		if self.posdGiven:
			if not self.distdGiven:
				code.append("  vel = vel[:2]")
			code.append("  vel = self.fromSVUnitsVel(vel)")
		else:
			code.append("  vel = None")
		code.append("  return pos, vel")
		l = locals()
		exec "\n".join(code) in globals() , l
		self.from6 = new.instancemethod(l["from6"], self)

	def _svToSpherRaw(self, sv):
		"""returns spherical position and velocity vectors for the cartesian
		6-vector sv.

		This is based on SOFA's pv2s.
		"""
		x, y, z, xd, yd, zd = sv
		rInXY2 = x**2+y**2
		r2 = rInXY2+z**2
		rw = rTrue = math.sqrt(r2)

		if rTrue==0.:  # pos is null: use velocity for position
			x, y, z = sv[3:]
			rInXY2 = x**2+y**2
			r2 = rInXY2+z**2
			rw = math.sqrt(r2)

		rInXY = math.sqrt(rInXY2)
		xyp = x*xd+y*yd
		radialVel = 0
		if rw!=0:
			radialVel = xyp/rw+z*zd/rw
		
		if rInXY2!=0.:
			theta = math.atan2(y, x)
			if abs(theta)<1e-12: # null out to avoid wrapping to 2 pi
				theta = 0
			if theta<0:
				theta += 2*math.pi
			posValues = (theta, math.atan2(z, rInXY), rTrue)
			velValues = ((x*yd-y*xd)/rInXY2, (zd*rInXY2-z*xyp)/(r2*rInXY), radialVel)
		else:
			phi = 0
			if z!=0:
				phi = math.atan2(z, rInXY)
			posValues = (0, phi, rTrue)
			velValues = (0, 0, radialVel)
		return posValues, velValues

	def getPlaceTransformer(self, sixTrafo):
		"""returns a function that transforms 2- or 3-spherical coordinates
		using the 6-vector transformation sixTrafo.

		Regardless of whether we expect distances, the returned function always
		returns vectors of the same dimensionality as were passed in.

		This is used when transforming areas.
		"""
		def sTrafo(pos):
			make2 = len(pos)==2
			if self.distGiven and make2:
				pos = pos+(defaultDistance,)
			res, _ = self.from6(sixTrafo(self.to6(pos, self._velDefault), self))
			if make2:
				res = res[:2]
			return res
		return sTrafo
	
	def getVelocityTransformer(self, sixTrafo, basePos):
		"""returns a function that transforms velocities using sixTrafos
		at basePos.

		This is used when tranforming velocity intervals.
		"""
		def sTrafo(vel):
			return self.from6(sixTrafo(self.to6(basePos, vel), self))[1]
		return sTrafo

	@classmethod
	def fromSTC(cls, stc, **kwargs):
		"""returns a new 6-vector transform for coordinates in STC.
		"""
		pos, vel, posUnit, velUnitS, velUnitT = (None,)*5
		if stc.place:
			pos = stc.place.value
			posUnit = stc.place.unit
			if pos is None:  # if areas are there, fake a position of their
				if stc.areas:  # dimensionality
					pos = (0,)*stc.place.frame.nDim
		if stc.velocity:
			vel = stc.velocity.value
			velUnitS = stc.velocity.unit
			velUnitT = stc.velocity.velTimeUnit
		return cls(pos, posUnit, vel, velUnitS, velUnitT, **kwargs)


def toSpherical(threeVec):
	"""returns spherical coordinates for a cartesian 3-vector.

	threeVec needs not be normalized.
	"""
	rho = math.sqrt(threeVec[0]**2+threeVec[1]**2)
	long = math.atan2(threeVec[1], threeVec[0])
	lat = math.atan2(threeVec[2], rho)
	return long, lat


def toThreeVec(long, lat):
	"""returns a cartesian 3-vector for longitude and latitude.
	"""
	return (math.cos(lat)*math.cos(long), 
		math.cos(lat)*math.sin(long), 
		math.sin(lat))
