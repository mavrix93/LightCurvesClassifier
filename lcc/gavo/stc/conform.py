"""
"Conforming" of STCSpecs, i.e., bringing one to the system and units of the
other.

You can only conform STCSpecs rather than individual components, since 
usually you need the whole information for the transformation (e.g.,
space and time for velocities.
"""

#c Copyright 2008-2016, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from gavo.stc import sphermath
from gavo.stc import times
from gavo.stc import units
from gavo.stc import common


class SphercLoader(object):
	"""A hack to delay loading of spherc.

	We should probably use one of the many lazy import solutions and use
	it for both what we're doing here and in coords.AstWCSLoader.
	"""
	def __getattr__(self, *args):
		from gavo.stc import spherc
		globals()["spherc"] = spherc
		return getattr(spherc, *args)

spherc = SphercLoader()


_conformedAttributes = [("time", "timeAs"), ("place", "areas"), 
	("freq", "freqAs"), ("redshift", "redshiftAs"), ("velocity", "velocityAs")]


def _transformAreas(areas, sTrafo, srcFrame, destFrame):
	newAreas = []
	for a in areas:
		if a.frame is not srcFrame:
			raise common.STCError("Cannot transform areas in frame different from"
				" from the position frame.")
		newAreas.append(a.getTransformed(sTrafo, destFrame))
	return newAreas

i = [0]

def iterSpatialChanges(baseSTC, sysSTC, slaComp=False):
	"""yields changes to baseSTC to bring places and velocities to the
	system and units of sysSTC.

	sixTrans is a sphermath.SVConverter instance.

	If the frame or units are not defined in sysSTC, there are taken from
	baseSTC.
	"""
	if baseSTC.place is None or sysSTC.place is None:
		return  # nothing to conform in space
	sixTrans = sphermath.SVConverter.fromSTC(baseSTC, slaComp=slaComp)
	destFrame, srcFrame = sysSTC.place.frame, baseSTC.place.frame

	bPlace, bVel = baseSTC.place, baseSTC.velocity
	trafo = spherc.getTrafoFunction(baseSTC.place.frame.asTriple(),
		sysSTC.place.frame.asTriple(), sixTrans)
	if bPlace.value:
		sv = trafo(sixTrans.to6(baseSTC.place.value, 
			getattr(baseSTC.velocity, "value", None)), sixTrans)
		pos, vel = sixTrans.from6(sv)
	else:
		pos, vel = None, None

	# build spatial items to change if necessary
	if bPlace:
		yield "place", bPlace.change(value=pos, frame=destFrame)
		if baseSTC.areas:
			yield "areas", _transformAreas(baseSTC.areas, 
				sixTrans.getPlaceTransformer(trafo), srcFrame, destFrame)

	# build velocity items to change if necessary
	if bVel:
		yield "velocity", bVel.change(value=vel, frame=destFrame)
		if baseSTC.velocityAs:
			yield "velocityAs", _transformAreas(baseSTC.velocityAs, 
				sixTrans.getVelocityTransformer(trafo, bPlace.value), srcFrame, 
				destFrame)


def iterTemporalChanges(baseSTC, sysSTC):
	if baseSTC.time is None or sysSTC.time is None:
		return # nothing to conform in time
	destFrame = sysSTC.time.frame
	transform = times.getTransformFromSTC(baseSTC, sysSTC)
	if transform is None:
		return # we're already conforming
	if baseSTC.time.value:
		yield "time", baseSTC.time.change(value=transform(
			baseSTC.time.value), frame=destFrame)
	if baseSTC.timeAs:
		yield "timeAs", tuple(ta.getTransformed(transform, destFrame)
			for ta in baseSTC.timeAs)


def conformUnits(baseSTC, sysSTC):
	"""returns baseSTC in the units of sysSTC.
	"""
	changes = []
	for attName, dependentName in _conformedAttributes:
		changes.extend(units.iterUnitAdapted(baseSTC, sysSTC,
			attName, dependentName))
	return baseSTC.change(**dict(changes))


def conformSystems(baseSTC, sysSTC, relativistic=False, slaComp=False):
	"""conforms places and velocities in fromSTC with toSTC including 
	precession and reference frame fixing.
	"""
	changes = [("astroSystem", sysSTC.astroSystem)]
	changes.extend(iterSpatialChanges(baseSTC, sysSTC, slaComp=slaComp))
	changes.extend(iterTemporalChanges(baseSTC, sysSTC))
	return conformUnits(baseSTC.change(**dict(changes)), sysSTC)


def conform(baseSTC, sysSTC, **kwargs):
	"""returns baseSTC in the units and the system of sysSTC.
	"""
	if baseSTC.astroSystem==sysSTC.astroSystem:
		return conformUnits(baseSTC, sysSTC)
	else:
		return conformSystems(baseSTC, sysSTC, **kwargs)


def getSimple2Converter(srcSTC, destSTC, slaComp=True):
	"""returns a function that transforms lat and long in srcSTC to lat and
	long in destSTC.

	srcSTC and destSTC are ASTs.  Of course, all this
	only works if srcSTC and destSTC are both SPHER2-flavored.
	"""
	sixTrans = sphermath.SVConverter.fromSTC(srcSTC, slaComp=slaComp)
	trafo = spherc.getTrafoFunction(srcSTC.place.frame.asTriple(),
		destSTC.place.frame.asTriple(), sixTrans)

	def convert(ra, dec):
		pos, vel = sixTrans.from6(
			trafo(sixTrans.to6((ra, dec), None), sixTrans))
		return pos[0], pos[1]
	
	return convert
