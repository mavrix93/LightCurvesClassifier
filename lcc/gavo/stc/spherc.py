"""
Spherical sky coordinates and helpers.
"""

#c Copyright 2008-2016, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


# XXX TODO: Replace the actual transformations performed here with
# stuff from astropy.

from math import sin, cos
import math

import numpy
from numpy import linalg as la

from gavo.stc import common
from gavo.stc import sphermath
from gavo.stc import times
from gavo.stc import units
from gavo.utils import DEG, ARCSEC, memoized


############### Basic definitions for transforms

# Finding transformation sequences: This, in principle, is a standard
# graph problem.  However, we have lots of underspecified transforms,
# which makes building a Dijkstrable graph somewhat inconvenient.  So,
# instead of striving for an optimal shortest path, we go for a
# greedy search with some heuristics.  The most nonstandard feature is
# that nodes are built ad-hoc and noncircularity of the paths thorugh
# the "virtual" graph is checked on these ad-hoc nodes.

# The nodes in the graph are triples of (system, equinox, refpos).  The
# vertices are triples (fromNode, toNode, transform generator).
# Transform generators are functions 
#
# f(fromNode, toNode) -> (function or matrix)
#
# The arguments are node triples, the result either a function taking
# and returning 6-vectors or numpy matrices.  These functions may
# assume that only "appropriate" values are passed in as nodes, i.e.,
# they are not assumed to check that the are actually able to produce
# the requested transformation.

class _Wildcard(object): 
	"""is an object that compares equal to everything.

	This is used for underspecification of transforms, see SAME and
	ANYVAL below.
	"""
	def __init__(self, name):
		self.name = name
	
	def __repr__(self):
		return self.name

	def __ne__(self, other): return False
	def __eq__(self, other): return True


SAME = _Wildcard("SAME")
ANYVAL = _Wildcard("ANYVAL")

def _specifyTrafo(trafo, fromTuple, toTuple):
	"""fills in underspecified values in trafo from fromTuple and toTuple.

	The rules are: In the source, both SAME and ANYVAL are filled from
	fromTuple.  In the destination, SAME is filled from fromTuple,
	ANYVAL is filled from toTuple.

	The function returns a new transformation triple.
	"""
	src, dst, tgen = trafo
	newSrc, newDst = [], []
	for ind, val in enumerate(src):
		if val is SAME or val is ANYVAL:
			newSrc.append(fromTuple[ind])
		else:
			newSrc.append(val)
	for ind, val in enumerate(dst):
		if val is SAME:
			newDst.append(fromTuple[ind])
		elif val is ANYVAL:
			newDst.append(toTuple[ind])
		else:
			newDst.append(val)
	return tuple(newSrc), tuple(newDst), tgen


def _makeFindPath(transforms):
	"""returns a function for path finding in the virtual graph
	defined by transforms.

	Each transform is a triple of (fromNode, toNode, transformFactory).

	There's quite a bit of application-specific heuristics built in
	here, so there's litte you can do with this code outside of
	STC transforms construction.
	"""
	def findPath(fromTuple, toTuple, path=()):
		"""returns a sequence of transformation triples that lead from
		fromTuple to toTuple.

		fromTuple and toTuple are node triples (i.e., (system, equinox,
		refpoint)).

		The returned path is not guaranteed to be the shortest or even
		the numerically most stable.  It is the result of a greedy
		search for a cycle free path between the two "non-virtual" nodes.
		To keep the paths reasonable, we apply the heuristic that
		transformations keeping the system are preferable.

		The simple heuristics sometimes need help; e.g., the transformations
		below add explicit transformations to j2000 and b1950; you will always
		need this if your transformations include "magic" values for otherwise
		underspecified items.
		"""
		seenSystems = set(c[0] for c in path) | set(c[1] for c in path)
		candidates = [_specifyTrafo(t, fromTuple, toTuple) 
				for t in transforms if t[0]==fromTuple]
		# sort operations within the same reference system to the start
		candidates = [c for c in candidates if c[1][0]==toTuple[0]] + [
			c for c in candidates if c[1]!=toTuple[0]]
		for cand in candidates:
			srcSystem, dstSystem, tgen = cand
			# Ignore identities or trafos leading to cycles
			if srcSystem==dstSystem or dstSystem in seenSystems:
				continue
			if dstSystem==toTuple:  # If we are done, return result
				return path+(cand,)
			else:
				# Do the depth-first search
				np = findPath(dstSystem, toTuple, path+(cand,))
				if np:
					return np
	return findPath


def tupleMin(t1, t2):
	"""returns the element-wise minimum of two tuples:
	"""
	return tuple(min(i1, i2) for i1, i2 in zip(t1, t2))


def tupleMax(t1, t2):
	"""returns the element-wise maximum of two tuples:
	"""
	return tuple(max(i1, i2) for i1, i2 in zip(t1, t2))


############### Computation of precession matrices.

def prec_IAU1976(fromEquinox, toEquinox):
	"""returns the precession angles in the IAU 1976 system.

	The expressions are those of Lieske, A&A 73, 282.

	This function is for the precTheory argument of getPrecMatrix.
	"""
	# time differences have to be in julian centuries
	# captial T in Lieske
	fromDiff = times.getSeconds(fromEquinox-times.dtJ2000)/common.secsPerJCy 
	# lowercase T in Lieske
	toDiff = times.getSeconds(toEquinox-fromEquinox)/common.secsPerJCy  

	# Lieske's expressions yield arcsecs, fix below
	zeta = toDiff*(2306.2181+1.39656*fromDiff-0.000139*fromDiff**2
		)+toDiff**2*(0.30188-0.000344*fromDiff
		)+toDiff**3*0.017998
	z =    toDiff*(2306.2181+1.39656*fromDiff-0.000139*fromDiff**2
		)+toDiff**2*(1.09468+0.000066*fromDiff
		)+toDiff**3*0.018203
	theta = toDiff*(2004.3109-0.85330*fromDiff-0.000217*fromDiff**2
		)-toDiff**2*(0.42665+0.000217*fromDiff
		)-toDiff**3*0.041833
	return zeta*ARCSEC, z*ARCSEC, theta*ARCSEC


_dtB1850 = times.bYearToDateTime(1850)

def prec_Newcomb(fromEquinox, toEquinox):
	"""returns the precession angles for the newcomp

	This function is for the precTheory argument of getPrecMatrix.

	The expressions are Kinoshita's (1975)'s (SAOSR 364) 
	This is somewhat at odds with Yallop's choice of Andoyer in the FK4-FK5
	machinery below, but that really shouldn't matter.
	"""
	# time differences have to be in tropical centuries
	T = times.getSeconds(fromEquinox-_dtB1850)/(common.tropicalYear*86400*100)
	t = times.getSeconds(toEquinox-fromEquinox)/(common.tropicalYear*86400*100)

	polyVal = 2303.5548+(1.39720+0.000059*T)*T
	zeta = (polyVal+(0.30242-0.000269*T+0.017996*t)*t)*t
	z = (polyVal+(1.09478+0.000387*T+0.018324*t)*t)*t
	theta = (2005.1125+(-0.85294-0.000365*T)*T
		+(-0.42647-0.000365*T-0.041802*t)*t)*t
	return zeta*ARCSEC, z*ARCSEC, theta*ARCSEC


def getPrecMatrix(fromEquinox, toEquinox, precTheory):
	"""returns a precession matrix in the IAU(1976) system.

	fromEquinox and toEquinox are datetimes (in case of doubt, TT).

	precTheory(fromEquinox, toEquinox) -> zeta, z, theta computes the
	precession angles.  Defined in this module are prec_IAU1976 and 
	prec_Newcomb, but you can provide your own.  The angles must all be
	in rad.
	"""
	zeta, z, theta = precTheory(fromEquinox, toEquinox)
	return numpy.dot(
		numpy.dot(sphermath.getRotZ(-z), sphermath.getRotY(theta)),
		sphermath.getRotZ(-zeta))


_nullMatrix = numpy.zeros((3,3))
def threeToSix(matrix):
	"""returns a 6-matrix from a 3-matrix suitable for precessing our
	6-vectors.
	"""
	return numpy.concatenate((
		numpy.concatenate(  (matrix,      _nullMatrix), 1),
		numpy.concatenate(  (_nullMatrix, matrix     ), 1)))

def _getFullPrecMatrix(fromNode, toNode, precTheory):
	"""returns a full 6x6 matrix for transforming positions and proper motions.

	This only works for proper equatorial coordinates in both STC values.

	precTheory is a function returning precession angles.
	"""
	return threeToSix(getPrecMatrix(fromNode[1], toNode[1], precTheory))


def _getNewcombPrecMatrix(fromNode, toNode, sixTrans):
	return _getFullPrecMatrix(fromNode, toNode, prec_Newcomb)

def _getIAU1976PrecMatrix(fromNode, toNode, sixTrans):
	return _getFullPrecMatrix(fromNode, toNode, prec_IAU1976)


############### FK4-FK5 system transformation
# This follows the prescription of Yallop et al, AJ 97, 274

# Transformation matrix according to Yallop
_fk4ToFK5MatrixYallop = numpy.array([
	[0.999925678186902, -0.011182059642247, -0.004857946558960,
		0.000002423950176, -0.000000027106627, -0.000000011776558],
	[0.011182059571766, 0.999937478448132, -0.000027176441185,
		0.000000027106627, 0.000002723978783, -0.000000000065874],
	[0.004857946721186, -0.000027147426489, 0.9999881997387700,
		0.000000011776559, -0.000000000065816, 0.000002424101735],
	[-0.000541652366951, -0.237968129744288, 0.436227555856097,
		0.999947035154614, -0.011182506121805, -0.004857669684959],
	[0.237917612131583, -0.002660763319071,	-0.008537771074048,
		0.011182506007242, 0.999958833818833, -0.000027184471371],
	[-0.436111276039270, 0.012259092261564, 0.002119110818172,
		0.004857669948650, -0.000027137309539, 1.000009560363559]])

# Transformation matrix according to SLALIB-F
_fk4ToFK5MatrixSla = numpy.transpose(numpy.array([
	[+0.9999256782, +0.0111820610, +0.0048579479, 
		-0.000551, +0.238514, -0.435623],
	[-0.0111820611, +0.9999374784, -0.0000271474, 
		-0.238565, -0.002667, +0.012254],
	[-0.0048579477, -0.0000271765, +0.9999881997, 
		+0.435739, -0.008541, +0.002117],
	[+0.00000242395018, +0.00000002710663, +0.00000001177656, 
		+0.99994704, +0.01118251, +0.00485767],
	[-0.00000002710663, +0.00000242397878, -0.00000000006582, 
		-0.01118251, +0.99995883, -0.00002714],
	[-0.00000001177656, -0.00000000006587, +0.00000242410173, 
		-0.00485767, -0.00002718, +1.00000956]]))

# Inverse transformation matrix according to SLALIB-F
_fk5ToFK4Matrix = numpy.transpose(numpy.array([
[+0.9999256795, -0.0111814828, -0.0048590040, 
	-0.000551, -0.238560, +0.435730],
[+0.0111814828, +0.9999374849, -0.0000271557, 
	+0.238509, -0.002667, -0.008541],
[+0.0048590039, -0.0000271771, +0.9999881946, 
	-0.435614, +0.012254, +0.002117],
[-0.00000242389840, +0.00000002710544, +0.00000001177742, 
	+0.99990432, -0.01118145, -0.00485852],
[-0.00000002710544, -0.00000242392702, +0.00000000006585, 
	+0.01118145, +0.99991613, -0.00002716],
[-0.00000001177742, +0.00000000006585, -0.00000242404995, 
	+0.00485852, -0.00002717, +0.99996684]]))



# Positional correction due to E-Terms, in rad (per tropical century in the
# case of Adot, which is ok for sphermath._svPosUnit (Yallop et al, loc cit, p.
# 276)).  We ignore the difference between tropical and julian centuries.
_b1950ETermsPos = numpy.array([-1.62557e-6, -0.31919e-6, -0.13843e-6])
_b1950ETermsVel = numpy.array([1.245e-3, -1.580e-3, -0.659e-3])
_yallopK = common.secsPerJCy/(units.oneAU/1e3)
_yallopKSla = 21.095;
_pcPerCyToKmPerSec = units.getRedshiftConverter("pc", "cy", "km", "s")

# An SVConverter to bring 6-vectors to the spherical units Yallop prescribes.
_yallopSVConverter = sphermath.SVConverter((0,0,0), ("rad", "rad", "arcsec"), 
	(0,0,0), ("arcsec", "arcsec", "km"), ("cy", "cy", "s"))


def _svToYallop(sv, yallopK):
	"""returns r and rdot vectors suitable for Yallop's recipe from our
	6-vectors.
	"""
	(alpha, delta, prlx), (pma, pmd, rv) = _yallopSVConverter.from6(sv)

	yallopR = numpy.array([cos(alpha)*cos(delta),
		sin(alpha)*cos(delta), sin(delta)])
	yallopRd = numpy.array([
		-pma*sin(alpha)*cos(delta)-pmd*cos(alpha)*sin(delta),
		pma*cos(alpha)*cos(delta)-pmd*sin(alpha)*sin(delta),
		pmd*cos(delta)])+yallopK*rv*prlx*yallopR
	return yallopR, yallopRd, (rv, prlx)


def _yallopToSv(yallop6, yallopK, rvAndPrlx):
	"""returns a 6-Vector from a yallop-6 vector.

	rvAndPrlx is the third item of the return value of _svToYallop.
	"""
	rv, prlx = rvAndPrlx
	x,y,z,xd,yd,zd = yallop6
	rxy2 = x**2+y**2
	r = math.sqrt(z**2+rxy2)
	if rxy2==0:
		raise common.STCValueError("No spherical proper motion on poles.")
	alpha = math.atan2(y, x)
	if alpha<0:
		alpha += 2*math.pi
	delta = math.atan2(z, math.sqrt(rxy2))
	pma = (x*yd-y*xd)/rxy2
	pmd = (zd*rxy2-z*(x*xd+y*yd))/r/r/math.sqrt(rxy2)
	if abs(prlx)>1/sphermath.defaultDistance:
		rv = numpy.dot(yallop6[:3], yallop6[3:])/yallopK/prlx/r
		prlx = prlx/r
	return _yallopSVConverter.to6((alpha, delta, prlx), (pma, pmd, rv))


def fk4ToFK5(sixTrans, svfk4):
	"""returns an FK5 2000 6-vector for an FK4 1950 6-vector.

	The procedure used is described in Yallop et al, AJ 97, 274.  E-terms
	of aberration are always removed from proper motions, regardless of
	whether the objects are within 10 deg of the pole.
	"""
	if sixTrans.slaComp:
		transMatrix = _fk4ToFK5MatrixSla
		yallopK = _yallopKSla
	else:
		transMatrix = _fk4ToFK5MatrixYallop
		yallopK = _yallopK
	yallopR, yallopRd, rvAndPrlx = _svToYallop(svfk4, yallopK)

	# Yallop's recipe starts here
	if not sixTrans.slaComp:  # include Yallop's "small terms" in PM
		yallopVE = (yallopRd-_b1950ETermsVel
			+numpy.dot(yallopR, _b1950ETermsVel)*yallopR
			+numpy.dot(yallopRd, _b1950ETermsPos)*yallopR
			+numpy.dot(yallopRd, _b1950ETermsPos)*yallopRd)
	else:
		yallopVE = (yallopRd-_b1950ETermsVel
			+numpy.dot(yallopR, _b1950ETermsVel)*yallopR)

	yallop6 = numpy.concatenate((yallopR-(_b1950ETermsPos-
			numpy.dot(yallopR, _b1950ETermsPos)*yallopR),
		yallopVE))
	cnv = numpy.dot(transMatrix, yallop6)
	return _yallopToSv(cnv, yallopK, rvAndPrlx)


def fk5ToFK4(sixTrans, svfk5):
	"""returns an FK4 1950 6-vector for an FK5 2000 6-vector.

	This is basically a reversal of fk4ToFK5, except we're always operating
	in slaComp mode here.

	"""
	yallopR, yallopRd, rvAndPrlx = _svToYallop(svfk5, _yallopKSla)

	# first apply rotation...
	cnv = numpy.dot(_fk5ToFK4Matrix, 
		numpy.concatenate((yallopR, yallopRd)))
	# ... then handle E-Terms; direct inversion of Yallop's equations is
	# troublesome, so I basically follow what slalib does.
	yallopR, yallopRd = cnv[:3], cnv[3:]
	spatialCorr = numpy.dot(yallopR, _b1950ETermsPos)*yallopR
	newRMod = sphermath.vabs(yallopR+_b1950ETermsPos*
		sphermath.vabs(yallopR)-spatialCorr)
	newR = yallopR+_b1950ETermsPos*newRMod-spatialCorr
	newRd = yallopRd+_b1950ETermsVel*newRMod-numpy.dot(
		yallopR, _b1950ETermsVel)*yallopR

	return _yallopToSv(numpy.concatenate((newR, newRd)),
		_yallopKSla, rvAndPrlx)


############### Galactic coordinates

_galB1950pole = (192.25*DEG, 27.4*DEG)
_galB1950zero = (265.6108440311*DEG, -28.9167903484*DEG)

_b1950ToGalTrafo = sphermath.computeTransMatrixFromPole(
	_galB1950pole, _galB1950zero)
_b1950ToGalMatrix = threeToSix(_b1950ToGalTrafo)

# For convenience, a ready-made matrix, taken basically from SLALIB
_galToJ2000Matrix = threeToSix(numpy.transpose(numpy.array([
	[-0.054875539695716, -0.873437107995315, -0.483834985836994],
	[ 0.494109453305607, -0.444829589431879,  0.746982251810510],
	[-0.867666135847849, -0.198076386130820,  0.455983795721093]])))


############### Supergalactic coordinates

_galToSupergalTrafo = sphermath.computeTransMatrixFromPole(
	(47.37*DEG, 6.32*DEG), (137.37*DEG, 0))
_galToSupergalMatrix = threeToSix(_galToSupergalTrafo)


############### Ecliptic coordinates

def _getEclipticMatrix(epoch):
	"""returns the rotation matrix from equatorial to ecliptic at datetime epoch.

	Strictly, epoch should be a TDB.
	"""
	t = times.getSeconds(epoch-times.dtJ2000)/common.secsPerJCy
	obliquity = (84381.448+(-46.8150+(-0.00059+0.001813*t)*t)*t)*ARCSEC
	return sphermath.getRotX(obliquity)

def _getFromEclipticMatrix(fromNode, toNode, sixTrans):
	return threeToSix(numpy.transpose(_getEclipticMatrix(fromNode[1])))

def _getToEclipticMatrix(fromNode, toNode, sixTrans):
	emat = _getEclipticMatrix(fromNode[1])
	return threeToSix(emat)


############### ICRS a.k.a. Hipparcos
# This is all parallel to IAU sofa, i.e. no zonal corrections, etc.
# From FK5hip

def cross(vec1, vec2):
	"""returns the cross product of two 3-vectors.

	This should really be somewhere else...
	"""
	return numpy.array([
		vec1[1]*vec2[2]-vec1[2]*vec2[1],
		vec1[2]*vec2[0]-vec1[0]*vec2[2],
		vec1[0]*vec2[1]-vec1[1]*vec2[0],
	])

# Compute transformation from orientation of FK5
_fk5ToICRSMatrix = sphermath.getMatrixFromEulerVector(
	numpy.array([-19.9e-3, -9.1e-3, 22.9e-3])*ARCSEC)
_icrsToFK5Matrix = numpy.transpose(_fk5ToICRSMatrix)

# Spin of FK5 in FK5 system
_fk5SpinFK5 = numpy.array([-0.30e-3, 0.60e-3, 0.70e-3])*ARCSEC/365.25
# Spin of FK5 in ICRS
_fk5SpinICRS = numpy.dot(_fk5ToICRSMatrix, _fk5SpinFK5)

def fk5ToICRS(sixTrans, svFk5):
	"""returns a 6-vector in ICRS for a 6-vector in FK5 J2000.
	"""
	spatial = numpy.dot(_fk5ToICRSMatrix, svFk5[:3])
	vel = numpy.dot(_fk5ToICRSMatrix,
		svFk5[3:]+cross(svFk5[:3], _fk5SpinFK5))
	return numpy.concatenate((spatial, vel))


def icrsToFK5(sixTrans, svICRS):
	"""returns a 6-vector in FK5 J2000 for an ICRS 6-vector.
	"""
	spatial = numpy.dot(_icrsToFK5Matrix, svICRS[:3])
	corrForSpin = svICRS[3:]-cross(svICRS[:3], _fk5SpinICRS)
	vel = numpy.dot(_icrsToFK5Matrix, corrForSpin)
	return numpy.concatenate((spatial, vel))


############### Reference positions
# XXX TODO: We don't transform anything here.  Yet.  This will not
# hurt for moderate accuracy requirements in the stellar and
# extragalactic regime but makes this library basically useless for
# solar system work.

def _transformRefpos(sixTrans, sixVec):
	return sixVec


############### Top-level code


def _Constant(val):
	"""returns a transform factory always returning val.
	"""
	return lambda fromSTC, toSTC, sixTrans: val


# transforms are triples of fromNode, toNode, transform factory.  Due to
# the greedy nature of your "virtual graph" searching, it's generally a
# good idea to put more specific transforms further up.

_findTransformsPath = _makeFindPath([
	(("FK4", times.dtB1950, SAME), ("FK5", times.dtJ2000, SAME),
		_Constant(fk4ToFK5)),
	(("FK5", times.dtJ2000, SAME), ("FK4", times.dtB1950, SAME),
		_Constant(fk5ToFK4)),
	(("FK5", times.dtJ2000, SAME), ("GALACTIC_II", ANYVAL, SAME),
		_Constant(la.inv(_galToJ2000Matrix))),
	(("GALACTIC_II", ANYVAL, SAME), ("FK5", times.dtJ2000, SAME),
		_Constant(_galToJ2000Matrix)),
	(("FK4", times.dtB1950, SAME), ("GALACTIC_II", ANYVAL, SAME),
		_Constant(_b1950ToGalMatrix)),
	(("GALACTIC_II", ANYVAL, SAME), ("FK4", times.dtB1950, SAME),
		_Constant(la.inv(_b1950ToGalMatrix))),
	(("GALACTIC_II", ANYVAL, SAME), ("SUPER_GALACTIC", ANYVAL, SAME),
		_Constant(_galToSupergalMatrix)),
	(("SUPER_GALACTIC", ANYVAL, SAME), ("GALACTIC_II", ANYVAL, SAME),
		_Constant(la.inv(_galToSupergalMatrix))),
	(("FK5", ANYVAL, SAME), ("FK5", times.dtJ2000, SAME),
		_getIAU1976PrecMatrix),
	(("FK4", ANYVAL, SAME), ("FK4", times.dtB1950, SAME),
		_getNewcombPrecMatrix),
	(("FK5", ANYVAL, SAME), ("FK5", ANYVAL, SAME),
		_getIAU1976PrecMatrix),
	(("FK4", ANYVAL, SAME), ("FK4", ANYVAL, SAME),
		_getNewcombPrecMatrix),
	(("ECLIPTIC", SAME, SAME), ("FK5", SAME, SAME),
		_getFromEclipticMatrix),
	(("FK5", SAME, SAME), ("ECLIPTIC", SAME, SAME),
		_getToEclipticMatrix),
	(("FK5", times.dtJ2000, SAME), ("ICRS", ANYVAL, SAME),
		_Constant(fk5ToICRS)),
	(("ICRS", ANYVAL, SAME), ("FK5", times.dtJ2000, SAME),
		_Constant(icrsToFK5)),
	((SAME, SAME, ANYVAL), (SAME, SAME, ANYVAL),
		_Constant(_transformRefpos)),
])


_precessionFuncs = set([_getNewcombPrecMatrix, _getIAU1976PrecMatrix])

def _contractPrecessions(toContract):
	"""contracts the precessions in toContract.
	
	No checks done.  This is only intended as a helper for _simplifyPath.
	"""
	return toContract[0][0], toContract[-1][1], toContract[0][-1]


def _simplifyPath(path):
	"""tries to simplify path by contracting mulitple consecutive precessions.

	These come in since our path finding algorithm sucks.  This is mainly
	done for numerical reasons since the matrices would be contracted for
	computation anyway.
	"""
# Sorry about this complex mess.  Maybe we want a more general optimization
# framework.
	if path is None:
		return path
	newPath, toContract = [], []
	curPrecFunc = None
	for t in path:
		if curPrecFunc:
			if t[-1] is curPrecFunc:
				toContract.append(t)
			else:
				newPath.append(_contractPrecessions(toContract))
				if t[-1] in _precessionFuncs:
					curPrecFunc, toContract = t[-1], [t]
				else:
					curPrecFunc, toContract = None, []
					newPath.append(t)
		else:
			if t[-1] in _precessionFuncs:
				curPrecFunc = t[-1]
				toContract = [t]
			else:
				newPath.append(t)
	if toContract:
		newPath.append(_contractPrecessions(toContract))
	return newPath

def _contractMatrices(ops):
	"""combines consecutive numpy.matrix instances in the sequence
	ops by dot-multiplying them.
	"""
	newSeq, curMat = [], None
	for op in ops:
		if isinstance(op, numpy.ndarray):
			if curMat is None:
				curMat = op
			else:
				curMat = numpy.dot(curMat, op)
		else:
			if curMat is not None:
				newSeq.append(curMat)
				curMat = None
			newSeq.append(op)
	if curMat is not None:
		newSeq.append(curMat)
	return newSeq
	

def _pathToFunction(trafoPath, sixTrans):
	"""returns a function encapsulating all operations contained in
	trafoPath.

	The function receives and returns a 6-vector.  trafoPath is altered.
	"""
	trafoPath.reverse()
	steps = _contractMatrices([factory(srcTrip, dstTrip, sixTrans)
		for srcTrip, dstTrip, factory in trafoPath])
	expr = []
	for index, step in enumerate(steps):
		if isinstance(step, numpy.ndarray):
			expr.append("numpy.dot(steps[%d], "%index)
		else:
			expr.append("steps[%d](sixTrans, "%index)
	vars = {"steps": steps, "numpy": numpy}
	exec ("def transform(sv, sixTrans): return %s"%
		"".join(expr)+"sv"+(")"*len(expr))) in vars
	return vars["transform"]


def nullTransform(sv, sixTrans):
	return sv


@memoized
def getTrafoFunction(srcTriple, dstTriple, sixTrans):
	"""returns a function that transforms 6-vectors from the system
	described by srcTriple to the one described by dstTriple.

	The triples consist of (system, equinox, refpoint).

	If no transformation function can be produced, the function raises
	an STCValueError.

	sixTrans is a sphermath.SVConverter instance, used here for communication
	of input details and user preferences.
	"""
	# special case the identity since it's indistingishable from a failed
	# search otherwise
	if srcTriple==dstTriple:
		return nullTransform
	trafoPath = _simplifyPath(_findTransformsPath(srcTriple, dstTriple))
	if trafoPath is None:
		raise common.STCValueError("Cannot find a transform from %s to %s"%(
			srcTriple, dstTriple))
	return _pathToFunction(trafoPath, sixTrans)
