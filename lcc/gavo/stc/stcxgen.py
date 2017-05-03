"""
Converting ASTs to/from STC-X.

The basic idea for conversion to STC-X is that for every ASTNode in dm, there
is a serialize_<classname> function returning some xmlstan.  In general
they should handle the case when their argument is None and return None
in that case.

Traversal is done manually (i.e., by each serialize_X method) rather than
globally since the children in the AST may not have the right order to
keep XSD happy, and also since ASTs are actually a bit more complicated
than trees (e.g., coordinate frames usually have multiple parents).
"""

#c Copyright 2008-2016, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import itertools

from gavo import utils
from gavo.stc import common
from gavo.stc import dm
from gavo.stc.stcx import STC


def addId(node):
	"""adds a synthetic id attribute to node unless it's already
	there.
	"""
	if not hasattr(node, "id") or node.id is None:
		node.id = utils.intToFunnyWord(id(node))


def strOrNull(val):
	if val is None:
		return None
	elif isinstance(val, common.ColRef):
		return val
	else:
		return str(val)


def isoformatOrNull(val):
	if val is None:
		return None
	elif isinstance(val, common.ColRef):
		return val
	else:
		return val.isoformat()
	

def _getFromSTC(elName, itemDesc):
	"""returns the STC element elName or raises an STCValueError if
	it does not exist.

	itemDesc is used in the error message.  This is a helper for
	concise notation of reference frames.
	"""
	if elName is None:
		elName = "UNKNOWNFrame"
	try:
		return getattr(STC, elName)
	except AttributeError:
		raise common.STCValueError("No such %s: %s"%(itemDesc, elName))


class Context(object):
	"""is a generation context.

	It is used to pass around genration-related information.  Right now,
	that's primarily the root node.
	"""
	def __init__(self, rootNode):
		self.rootNode = rootNode
	
	def getPosForInterval(self, node):
		return getattr(self.rootNode, node.cType.posAttr)


############ Coordinate Systems

def serialize_RefPos(node, context):
	try:
		return getattr(STC, node.standardOrigin or "UNKNOWNRefPos")[
			STC.PlanetaryEphem[node.planetaryEphemeris]]
	except AttributeError:
		raise common.STCValueError(
			"No such standard origin: %s"%node.standardOrigin)


def _fudgeEquinox(eq):
# Incredibly, the schema requires not more than three figures after the
# comma for equinox.  Sigh.
	if eq is None:
		return None
	res = eq[0]+"%.3f"%float(eq[1:])
	# Do some cosmetics
	if res.endswith("00"):
		res = res[:-2]
	return res

def serialize_SpaceFrame(node, context):
	if node is None: return
	addId(node)
	return STC.SpaceFrame(id=node.id)[
		STC.Name[node.name], 
		_getFromSTC(node.refFrame, "reference frame")[
			STC.Equinox[_fudgeEquinox(node.equinox)]],
		serialize_RefPos(node.refPos, context),
		_getFromSTC(node.flavor, "coordinate flavor")(
			coord_naxes=strOrNull(node.nDim))]


def serialize_TimeFrame(node, context):
	if node is None: return
	addId(node)
	return STC.TimeFrame(id=node.id)[
		STC.Name[node.name],
		STC.TimeScale[node.timeScale],
		serialize_RefPos(node.refPos, context),
	]

def serialize_SpectralFrame(node, context):
	if node is None: return
	addId(node)
	return STC.SpectralFrame(id=node.id)[
		STC.Name[node.name],
		serialize_RefPos(node.refPos, context),
	]

def serialize_RedshiftFrame(node, context):
	if node is None: return
	addId(node)
	return STC.RedshiftFrame(id=node.id, value_type=node.type)[
		STC.Name[node.name],
		STC.DopplerDefinition[node.dopplerDef],
		serialize_RefPos(node.refPos, context),
	]

def serialize_CoordSys(node, context):
	addId(node)
	if node.libraryId:
		return STC.AstroCoordSystem(id=node.id,
			href=node.libraryId)
	else:
		return STC.AstroCoordSystem(id=node.id)[
			serialize_TimeFrame(node.timeFrame, context),
			serialize_SpaceFrame(node.spaceFrame, context),
			serialize_SpectralFrame(node.spectralFrame, context),
			serialize_RedshiftFrame(node.redshiftFrame, context),]


############ Coordinates


def _wrapValues(element, valSeq, mapper=strOrNull):
	"""returns the items of valSeq as children of element, mapped with mapper.
	"""
	if valSeq is None:
		return []
	return [element[mapper(v)] for v in valSeq]


def _serialize_Wiggle(node, serializer, wiggles):
	if node is None:
		return
	cooClass, radiusClass, matrixClass = wiggles
	if isinstance(node, dm.CooWiggle):
		return _wrapValues(cooClass, node.values, serializer),
	elif isinstance(node, dm.RadiusWiggle):
		return [radiusClass[strOrNull(r)] for r in node.radii]
	elif isinstance(node, dm.MatrixWiggle):
		return [matrixClass[_wrapMatrix(m, strOrNull)] for m in node.matrices]
	else:
		raise common.STCValueError("Cannot serialize %s errors to STC-X"%
			node.__class__.__name__)


wiggleClasses = {
	"error": [
		(STC.Error, None, None),
		(STC.Error2, STC.Error2Radius, STC.Error2Matrix),
		(STC.Error3, STC.Error3Radius, STC.Error3Matrix),],
	"resolution": [
		(STC.Resolution, None, None),
		(STC.Resolution2, STC.Resolution2Radius, STC.Resolution2Matrix),
		(STC.Resolution3, STC.Resolution3Radius, STC.Resolution3Matrix),],
	"size": [
		(STC.Size, None, None),
		(STC.Size2, STC.Size2Radius, STC.Size2Matrix),
		(STC.Size3, STC.Size3Radius, STC.Size3Matrix),],
	"pixSize": [
		(STC.PixSize, None, None),
		(STC.PixSize2, STC.PixSize2Radius, STC.PixSize2Matrix),
		(STC.PixSize3, STC.PixSize3Radius, STC.PixSize3Matrix),],
}


def _make1DSerializer(cooClass, valueSerializer):
	"""returns a serializer returning a coordinate cooClass.

	This will only work for 1-dimensional coordinates.  valueSerializer
	is a function taking the coordinate's value and returning some
	xmlstan.
	"""
	def serialize(node, context):
		res = cooClass[
			valueSerializer(node.value),
			_wrapValues(STC.Error, getattr(node.error, "values", ())),
			_wrapValues(STC.Resolution, getattr(node.resolution, "values", ())),
			_wrapValues(STC.PixSize, getattr(node.pixSize, "values", ())),
		]
		if not res.shouldBeSkipped():
			return res(unit=node.unit, 
				vel_time_unit=getattr(node, "velTimeUnit", None),
				frame_id=node.frame.id)
	return serialize

serialize_TimeCoo = _make1DSerializer(STC.Time,
	lambda value: STC.TimeInstant[STC.ISOTime[isoformatOrNull(value)]])
serialize_RedshiftCoo = _make1DSerializer(STC.Redshift,
	lambda value: STC.Value[strOrNull(value)])
serialize_SpectralCoo = _make1DSerializer(STC.Spectral,
	lambda value: STC.Value[strOrNull(value)])


_nones = (None, None, None)

def _wrap1D(val, unit=_nones, timeUnit=_nones):
	if not val:
		return
	if isinstance(val, common.ColRef):
		return val
	return str(val[0])

def _wrap2D(val, unit=_nones, timeUnit=_nones):
	if not val:
		return
	if isinstance(val, common.ColRef):
		return val
	return [STC.C1(pos_unit=unit[0], vel_time_unit=timeUnit[0])[val[0]], 
		STC.C2(pos_unit=unit[1], vel_time_unit=timeUnit[1])[val[1]]]

def _wrap3D(val, unit=_nones, timeUnit=_nones):
	if not val:
		return
	if isinstance(val, common.ColRef):
		return val
	return [STC.C1(pos_unit=unit[0], vel_time_unit=timeUnit[0])[val[0]], 
		STC.C2(pos_unit=unit[1], vel_time_unit=timeUnit[1])[val[1]], 
		STC.C3(pos_unit=unit[2], vel_time_unit=timeUnit[2])[val[2]]]

def _wrapMatrix(val, serializer):
	for rowInd, row in enumerate(val):
		for colInd, col in enumerate(row):
			yield getattr(STC, "M%d%d"%(rowInd, colInd))[serializer(col)]

_spatialPosClasses = (
	(STC.Position1D, STC.Value, _wrap1D),
	(STC.Position2D, STC.Value2, _wrap2D),
	(STC.Position3D, STC.Value3, _wrap3D),
)
_velocityPosClasses = (
	(STC.Velocity1D, STC.Value, _wrap1D),
	(STC.Velocity2D, STC.Value2, _wrap2D),
	(STC.Velocity3D, STC.Value3, _wrap3D),
)

def _getSpatialUnits(node):
	clsArgs, cooArgs = {}, {}
	if node.unit:
		if len(set(node.unit))==1:
			clsArgs["unit"] = node.unit[0]
		elif node.unit:
			cooArgs["unit"] = node.unit
		if hasattr(node, "velTimeUnit"):
			if len(set(node.velTimeUnit))==1:
				clsArgs["vel_time_unit"] = node.velTimeUnit[0]
			elif node.unit:
				cooArgs["timeUnit"] = node.velTimeUnit
	return clsArgs, cooArgs


def _makeSpatialCooSerializer(stcClasses):
	"""serializes a spatial coordinate.

	This is quite messy since the concrete choice of elements depends on
	the coordinate frame.
	"""
	def serialize(node, context):
		if node.frame.nDim is None and node.value:
			dimInd = len(node.value)-1
		else:
			dimInd = node.frame.nDim-1
		coo, val, serializer = stcClasses[dimInd]
		clsArgs, cooArgs = _getSpatialUnits(node)

		valueStan = val[serializer(node.value, **cooArgs)]
		res = coo[
				valueStan,
				[_serialize_Wiggle(getattr(node, wiggleType), 
						serializer, wiggleClasses[wiggleType][dimInd])
					for wiggleType in ["error", "resolution", "size", "pixSize"]],
			]
		if node.epoch:
			res[STC.Epoch(yearDef=node.yearDef)[str(node.epoch)]]
		if not res.shouldBeSkipped():
			return res(frame_id=node.frame.id, **clsArgs)
	return serialize

serialize_SpaceCoo = _makeSpatialCooSerializer(_spatialPosClasses)
serialize_VelocityCoo = _makeSpatialCooSerializer(_velocityPosClasses)


############# Intervals

def _make1DIntervalSerializer(intervClass, lowerClass, upperClass,
		valueSerializer):
	"""returns a serializer returning stan for a coordinate interval.

	This will only work for 1-dimensional coordinates.  valueSerializer
	is a function taking the coordinate's value and returning some
	xmlstan.

	Currently, error, resolution, and pixSize information is discarded
	for lack of a place to put them.
	"""
	def serialize(node, context):
		posNode = context.getPosForInterval(node)
		if isinstance(node.frame, dm.TimeFrame):
			unit = None  # time intervals have no units
		else:
			unit = posNode.unit
		return intervClass(unit=unit, 
				vel_time_unit=getattr(posNode, "velTimeUnit", None), 
				frame_id=node.frame.id, fill_factor=strOrNull(node.fillFactor))[
			lowerClass[valueSerializer(node.lowerLimit)],
			upperClass[valueSerializer(node.upperLimit)],
		]
	return serialize


serialize_TimeInterval = _make1DIntervalSerializer(STC.TimeInterval,
	STC.StartTime, STC.StopTime, lambda val: STC.ISOTime[isoformatOrNull(val)])
serialize_SpectralInterval = _make1DIntervalSerializer(STC.SpectralInterval,
	STC.LoLimit, STC.HiLimit, strOrNull)
serialize_RedshiftInterval = _make1DIntervalSerializer(STC.RedshiftInterval,
	STC.LoLimit, STC.HiLimit, strOrNull)


_posIntervalClasses = [
	(STC.PositionScalarInterval, STC.LoLimit, STC.HiLimit, _wrap1D),
	(STC.Position2VecInterval, STC.LoLimit2Vec, STC.HiLimit2Vec, _wrap2D),
	(STC.Position3VecInterval, STC.LoLimit3Vec, STC.HiLimit3Vec, _wrap3D),]
_velIntervalClasses = [
	(STC.VelocityScalarInterval, STC.LoLimit, STC.HiLimit, _wrap1D),
	(STC.Velocity2VecInterval, STC.LoLimit2Vec, STC.HiLimit2Vec, _wrap2D),
	(STC.Velocity3VecInterval, STC.LoLimit3Vec, STC.HiLimit3Vec, _wrap3D),]

def _makeSpatialIntervalSerializer(stcClasses):
	def serialize(node, context):
		intervClass, lowerClass, upperClass, valueSerializer = \
			stcClasses[node.frame.nDim-1]
		posNode = context.getPosForInterval(node)
		clsArgs, cooArgs = _getSpatialUnits(posNode)

# check where we should stick these units at some point
#		if len(set(posNode.unit))==1:
#			unit = posNode.unit[0]
#		elif posNode.unit:
#			units = posNode.unit

		return intervClass(frame_id=node.frame.id, fill_factor=node.fillFactor,
				**clsArgs)[
				lowerClass[valueSerializer(node.lowerLimit, **cooArgs)],
				upperClass[valueSerializer(node.upperLimit, **cooArgs)],
			]
	return serialize

serialize_SpaceInterval = _makeSpatialIntervalSerializer(_posIntervalClasses)
serialize_VelocityInterval = _makeSpatialIntervalSerializer(_velIntervalClasses)


############# Geometries


def _getDim(sampleValue):
	if sampleValue is None:
		return None
	if isinstance(sampleValue, float):
		return 1
	else: 
		return len(sampleValue)
	

def _makeBaseGeometry(cls, node, context):
	buildArgs = _getSpatialUnits(context.getPosForInterval(node))[0]
	res = cls(frame_id=getattr(node.frame, "id", None), 
		fill_factor=strOrNull(node.fillFactor), **buildArgs)
	return res


def serialize_AllSky(node, context):
	return _makeBaseGeometry(STC.AllSky, node, context)

def serialize_Circle(node, context):
# would you believe that the sequence of center and radius is swapped
# in sphere and circle?  Oh boy.
	if node.geoColRef:
		return STC.Circle[node.geoColRef]
	nDim = _getDim(node.center)
	if nDim==2:
		return _makeBaseGeometry(STC.Circle, node, context)[
			STC.Center[_wrap2D(node.center)],
			STC.Radius[node.radius],
		]
	elif nDim==3:
		return _makeBaseGeometry(STC.Sphere, node, context)[
			STC.Radius[node.radius],
			STC.Center[_wrap3D(node.center)],
		]
	else:
		raise common.STCValueError("Spheres are only defined in 2 and 3D")


def serialize_Ellipse(node, context):
	if node.geoColRef:
		return STC.Ellipse[node.geoColRef]
	if _getDim(node.center)==2:
		cls, wrap = STC.Ellipse, _wrap2D
	else:
		raise common.STCValueError("Ellipses are only defined in 2D")
	return _makeBaseGeometry(cls, node, context)[
		STC.Center[wrap(node.center)],
		STC.SemiMajorAxis[node.smajAxis],
		STC.SemiMinorAxis[node.sminAxis],
		STC.PosAngle[node.posAngle],
	]


def serialize_Box(node, context):
	if node.geoColRef:
		return STC.Box[node.geoColRef]
	if _getDim(node.center)!=2:
		raise common.STCValueError("Boxes are only available in 2D")
	return _makeBaseGeometry(STC.Box, node, context)[
		STC.Center[_wrap2D(node.center)],
		STC.Size[_wrap2D(node.boxsize)]]


def serialize_Polygon(node, context):
	if node.geoColRef:
		return STC.Polygon[node.geoColRef]
	if node.vertices and _getDim(node.vertices[0])!=2:
		raise common.STCValueError("Polygons are only available in 2D")
	return _makeBaseGeometry(STC.Polygon, node, context)[
		[STC.Vertex[STC.Position[_wrap2D(v)]] for v in node.vertices]]


def serialize_Convex(node, context):
	if node.geoColRef:
		return STC.Polygon[node.geoColRef]
	return _makeBaseGeometry(STC.Convex, node, context)[
		[STC.Halfspace[STC.Vector[_wrap3D(v[:3])], STC.Offset[v[3]]]
		for v in node.vectors]]


def serialize_MultiCompound(node, context):
	if len(node.children)<2:
		return _nodeToStan(node)
	return {"Union": STC.Union, "Intersection": STC.Intersection}[
		node.__class__.__name__][[_nodeToStan(c, context) for c in node.children]]
			

serialize_Union =  serialize_Intersection = serialize_MultiCompound

def serialize_Difference(node, context):
	if len(node.children)!=2:
		raise common.STCValueError("Difference is only supported with two operands")
	op1 = _nodeToStan(node.children[0], context)
	op2 = _nodeToStan(node.children[1], context)
	# Banzai!  To save myself the trouble of having all those icky *2
	# elements around, I hack op2's name.
	op2.name_ = op2.name_+"2"
	return STC.Difference[op1, op2]

def serialize_Not(node, context):
	if len(node.children)!=1:
		raise common.STCValueError("Not is only supported with one operand")
	return STC.Negation[_nodeToStan(node.children[0], context)]


############# Toplevel

def makeAreas(rootNode, context):
	"""serializes the areas contained in rootNode.

	This requires all kinds of insane special handling.
	"""
	if not rootNode.areas:
		return
	elif len(rootNode.areas)==1:
		return _nodeToStan(rootNode.areas[0], context)
	else:  # implicit union
		return STC.Region[
			STC.Union[
				[_nodeToStan(n, context) for n in rootNode.areas]]]


def _nodeToStan(astNode, context):
	"""returns xmlstan for whatever is in astNode.
	"""
	return globals()["serialize_"+astNode.__class__.__name__](astNode, context)


def nodeToStan(astNode):
	"""returns xmlstan for an AST node.
	"""
	context = Context(astNode)
	return _nodeToStan(astNode, context)


def astToStan(rootNode, stcRoot):
	"""returns STC stan for the AST rootNode wrapped in the stcRoot element.

	The first coordinate system defined in the AST is always used for
	the embedded coordinates and areas.
	"""
	context = Context(rootNode)
	stcRoot[_nodeToStan(rootNode.astroSystem, context)]
	return stcRoot[_nodeToStan(rootNode.astroSystem, context),
		STC.AstroCoords(coord_system_id=rootNode.astroSystem.id)[
			[_nodeToStan(n, context) for n in [rootNode.time,
				rootNode.place, rootNode.velocity, rootNode.freq, 
					rootNode.redshift] if n]
		],
		STC.AstroCoordArea(coord_system_id=rootNode.astroSystem.id)[
			[_nodeToStan(n, context) for n in rootNode.timeAs],
			makeAreas(rootNode, context),
			[_nodeToStan(n, context) for n in 
				itertools.chain(rootNode.velocityAs, rootNode.freqAs, 
					rootNode.redshiftAs)]],
	]


def getSTCXProfile(rootNode):
	return astToStan(rootNode, STC.STCResourceProfile).render(
		prefixForEmpty="stc")
