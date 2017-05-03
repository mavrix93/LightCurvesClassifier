"""
Converting ASTs to STC-S.

The strategy here is to first generate an STCS CST, remove defaults from it
and then flatten out the whole thing.

The AST serializers here either return a dictionary, which is then
updated to the current node's dictionary, or a tuple of key and value,
which is then added to the current dictionary.
"""

#c Copyright 2008-2016, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import datetime
import itertools

from gavo import utils
from gavo.stc import common
from gavo.stc import dm
from gavo.stc import stcs
from gavo.stc import syslib


def _combine(*dicts):
	"""updates the first dictionary with all further ones and returns it.

	If duplicate keys exist, later arguments will overwrite values set
	by earlier arguments.
	"""
	res = dicts[0]
	for d in dicts[1:]:
		res.update(d)
	return res


############## Reference Frames to CST

def refPosToCST(node):
	return {
		"refpos": node.standardOrigin,
		"planetaryEphemeris": node.planetaryEphemeris,}

stcsFlavors = {
	(2, "SPHERICAL"): "SPHER2",
	(3, "SPHERICAL"): "SPHER3",
	(3, "UNITSPHERE"): "UNITSPHER",
	(1, "CARTESIAN"): "CART1",
	(2, "CARTESIAN"): "CART2",
	(3, "CARTESIAN"): "CART3",
}

def _computeFlavor(node):
	try:
		return stcsFlavors[(node.nDim, node.flavor)]
	except KeyError:
		raise common.STCValueError("Coordinate Frame %s cannot"
			" be represented it STC-S"%node)

# Simple translations of STC-X reference frame literals to STC-S
_frameTrans = {
	"GALACTIC_II": "GALACTIC",
	None: "UNKNOWNFrame",
}

def _spaceFrameToCST(node):
	if node is None:
		return {"frame": "UNKNOWNFrame"}

	frame = node.refFrame
	frame = _frameTrans.get(frame, frame)
	return _combine({
		"flavor": _computeFlavor(node),
		"frame": frame,
		"equinox": node.equinox,},
		refPosToCST(node.refPos))

def _timeFrameToCST(node):
	if node is None:
		return {}
	return _combine({
		"timescale": node.timeScale,},
		refPosToCST(node.refPos))

def _spectralFrameToCST(node):
	if node is None:
		return {}
	return refPosToCST(node.refPos)

def _redshiftFrameToCST(node):
	if node is None:
		return {}
	return _combine({
		"redshiftType": node.type,
		"dopplerdef": node.dopplerDef,},
		refPosToCST(node.refPos))


############### Coordinates to CST

def _wiggleToCST(node, nDim):
	if node is None:
		return
	if isinstance(node, dm.CooWiggle):
		return node.values
	elif isinstance(node, dm.RadiusWiggle):
		return tuple((r,)*nDim for r in node.radii)
	else:
		raise common.STCValueError("Cannot serialize %s wiggles into STC-S"%
			node.__class__.__name__)


def _makeCooTreeMapper(cooType):
	"""returns a function returning a CST fragment for a coordinate.
	"""
	def toCST(node):
		if node.frame is None:  # no frame, no coordinates.
			return {}
		nDim = node.frame.nDim
		return {
			"error": _wiggleToCST(node.error, nDim),
			"resolution": _wiggleToCST(node.resolution, nDim),
			"pixSize": _wiggleToCST(node.pixSize, nDim),
			"unit": node.getUnitString(),
			"type": cooType,
			"pos": node.value or None,}
	return toCST


def _makeIntervalCoos(node):
	res = {}
	if node.lowerLimit or node.upperLimit:
		res["coos"] = [c for c in (node.lowerLimit, node.upperLimit) 
			if c is not None]
	return res


def _makeTimeIntervalCoos(node):
# Special-cased since these have (Start|Stop)Time
	if node.lowerLimit and node.upperLimit:
		type, coos = "TimeInterval", (node.lowerLimit, node.upperLimit)
	elif node.lowerLimit:
		type, coos = "StartTime", (node.lowerLimit,)
	elif node.upperLimit:
		type, coos = "StopTime", (node.upperLimit,)
	else:
		type, coos = "TimeInterval", ()
	return {
		"type": type,
		"coos": coos}


def _makeAreaTreeMapper(areaType, cooMaker=_makeIntervalCoos):
	"""returns a CST fragment for an area.

	areaType this CST type of the node returned, cooMaker is a function
	that receives the node and returns a dictionary containing at least
	a coos key.  It can set other keys as well (e.g. 
	_makeTimeIntervalCoos needs to override the type key).
	"""
	def toCST(node):
		return _combine({
			"fillfactor": node.fillFactor,
			"type": areaType},
			cooMaker(node))
	return toCST


def _makePhraseTreeMapper(cooMapper, areaMapper, frameMapper,
		getASTItems):
	"""returns a mapper building a CST fragment for a subphrase.

	cooMapper and areaMapper are functions returning CST fragments
	for coordinates and areas of this type, respectively.

	getASTItems is a function that receives the AST root and has to
	return either None (no matching items found in AST) or a pair
	of coordinate and area, where area may be None.  Use _makeASTItemsGetter
	to build these functions.

	The function returned expects the root of the AST as argument.
	"""
	def toCST(astRoot):
		items = getASTItems(astRoot)
		if items is None:
			return {}
		coo, area = items
		areaKeys = {}
		if area:
			areaKeys = areaMapper(area)
		cooKeys = cooMapper(coo)
		frame = coo.frame or area.frame
		return _combine(cooKeys,
			areaKeys,  # area keys come later to override cst key "type".
			frameMapper(frame))
	return toCST


def _makeASTItemsGetter(cooName, areaName):
	"""returns a function that extracts coordinates and areas of
	a certain type from an AST.

	The function does all kinds of sanity checks and raises STCValueErrors
	if those fail.

	If all goes well, it will return a pair coo, area.  coo is always
	non-None, area may be None.
	"""
	def getASTItems(astRoot):
		areas, coo = getattr(astRoot, areaName), getattr(astRoot, cooName)
		if not areas and not coo:
			return None
		if len(areas)>1:
			raise common.STCValueError("STC-S does not support more than one area"
				" but %s has length %d"%(areaName, len(areas)))
		if areas:
			area = areas[0]
		else:
			area = None
		return coo, area
	return getASTItems


def _spatialCooToCST(node, getBase=_makeCooTreeMapper("Position")):
	if node.frame is None:
		return {}
	cstNode = getBase(node)
	cstNode["size"] = _wiggleToCST(node.size, node.frame.nDim)
	if node.epoch is not None:
		yearDef = node.yearDef
		if yearDef is None:
			yearDef = "J"
		cstNode["epoch"] = yearDef+str(node.epoch)
	return cstNode


_timeToCST = _makePhraseTreeMapper(
	_makeCooTreeMapper("Time"), 
	_makeAreaTreeMapper("TimeInterval", _makeTimeIntervalCoos),
	_timeFrameToCST,
	_makeASTItemsGetter("time", "timeAs"))
_simpleSpatialToCST = _makePhraseTreeMapper(
	_spatialCooToCST,
	_makeAreaTreeMapper("PositionInterval"),
	_spaceFrameToCST,
	_makeASTItemsGetter("place", "areas"))
_spectralToCST = _makePhraseTreeMapper(
	_makeCooTreeMapper("Spectral"),
	_makeAreaTreeMapper("SpectralInterval"),
	_spectralFrameToCST,
	_makeASTItemsGetter("freq", "freqAs"))
_redshiftToCST = _makePhraseTreeMapper(
	_makeCooTreeMapper("Redshift"),
	_makeAreaTreeMapper("RedshiftInterval"),
	_redshiftFrameToCST,
	_makeASTItemsGetter("redshift", "redshiftAs"))
_velocityToCST = _makePhraseTreeMapper(
	_makeCooTreeMapper("VelocityInterval"),
	_makeAreaTreeMapper("VelocityInterval"),
	lambda _: {},  # Frame provided by embedding position
	_makeASTItemsGetter("velocity", "velocityAs"))

def _sysIdToCST(astRoot):
	if astRoot.astroSystem.libraryId:
		return syslib.stripIVOID(astRoot.astroSystem.libraryId)


def _makeAllSkyCoos(node):
	return {"geoCoos": ()}

def _makeCircleCoos(node):
	return {"geoCoos": node.center+(node.radius,)}

def _makeEllipseCoos(node):
	return {"geoCoos": node.center+(node.smajAxis, node.sminAxis, node.posAngle)}

def _makeBoxCoos(node):
	return {"geoCoos": node.center+node.boxsize}

def _makePolygonCoos(node):
	return {"geoCoos": tuple(itertools.chain(*node.vertices))}

def _makeConvexCoos(node):
	return {"geoCoos": tuple(itertools.chain(*node.vectors))}

def _makeSpaceIntervalCoos(node):
	return {"geoCoos": node.lowerLimit+node.upperLimit}

_compoundGeos = ["Union", "Difference", "Intersection", "Not"]

def _makeUnionCoos(node):
	children = []
	for c in node.children:
		nodeName = c.__class__.__name__
		base = {"subtype": nodeName}
		if c in _compoundGeos:
			children.append(_combine(base, _makeUnionCoos(c)))
		else:
			children.append(_combine(base,
				globals()["_make%sCoos"%nodeName](c)))
	return {"children": children}

_makeDifferenceCoos = _makeIntersectionCoos = _makeNotCoos = _makeUnionCoos

_geometryMappers = dict([(n, _makePhraseTreeMapper(
		_spatialCooToCST,
		_makeAreaTreeMapper(n, globals()["_make%sCoos"%n]),
		_spaceFrameToCST,
		_makeASTItemsGetter("place", "areas")))
	for n in ["AllSky", "Circle", "Ellipse", "Box", "Polygon", "Convex"]+
			_compoundGeos])

def _spatialToCST(astRoot):
	args = {}
	velocityArgs = _velocityToCST(astRoot)
	if velocityArgs:
		args = {"velocity": velocityArgs}
	node = (astRoot.areas and astRoot.areas[0]) or astRoot.place

	if not node:
		# This means we have neither a place nor a geometry but still
		# want a frame (e.g., velocity only)
		if args:
			args.update(_spaceFrameToCST(astRoot.astroSystem.spaceFrame))
			args["type"] = "Position"
	elif isinstance(node, (dm.SpaceCoo, dm.SpaceInterval)):
		args.update(_simpleSpatialToCST(astRoot))
	else: # Ok, it's a geometry
		args.update(_geometryMappers[node.__class__.__name__](astRoot))
	return args


############## Flattening of the CST

def _joinWithNull(strList):
	res = " ".join(s for s in strList if s is not None)
	if not res:
		return None
	return res


def _joinKeysWithNull(node, kwList, flatteners):
	"""returns a string made up of the non-null values in kwList in node.

	To make things a bit more flexible, you can give lists in kwList.
	Their elements will be inserted into the result as-is.

	Flatteners is a dictionary mapping keys from kwList to functions

	flat(val, node) -> string

	that turn a value for the keyword to a complete string.  
	_makeKeywordFlattener and _makeNoKeywordFlattener generate such functions.
	"""
	res = []
	for key in kwList:
		if isinstance(key, list):
			res.extend(key)
		elif key not in node:
			pass
		elif key in flatteners:
			res.append(flatteners[key](node[key], node))
		else:
			res.append(node[key])
	return _joinWithNull(res)


def _flattenValue(val, node=None):
	"""returns a sensible STC-S string representation for many sorts of
	values, dispatched on their type.

	This function can be used as a flattener.
	"""
	if val is None:
		return ""
	elif isinstance(val, basestring):
		return str(val)
	elif isinstance(val, (int, float)):
		return str(val)
	elif isinstance(val, (list, tuple)):
		return " ".join(_flattenValue(v) for v in val)
	elif isinstance(val, datetime.datetime):
		return val.isoformat()
	elif isinstance(val, common.ColRef):
		return '"%s"'%val.dest
	else:
		raise common.STCValueError("Cannot serialize %r to STC-S"%val)


def _makePosValueFlattener(key):
	"""returns a flattener for position values of type key.

	The trick is to suppress key when the node already represents a position
	type.  Thus, we generate "Time 2" rather than Time Time 2 analogous to
	"TimeInterval [...] Time  2".
	"""
	def flattenPosition(val, node):
		if val is not None:
			if node["type"]==key:
				return _flattenValue(val)
			else:
				return "%s %s"%(key, _flattenValue(val))
	return flattenPosition


def _makeKeywordFlattener(keyword):
	"""returns a function returning a flattened value with keyword in front.
	"""
	if keyword:
		fmtStr = "%s %%s"%keyword
	else:
		fmtStr = "%s"
	def flatten(val, node):
		if val is not None and val!=():
			return fmtStr%(_flattenValue(val))
	return flatten


def _flattenRefPos(val, node):
	return _joinWithNull([node["refpos"], node["planetaryEphemeris"]])


# Keywords for items common to all coordinates.
_commonFlatteners = {
	"fillfactor": _makeKeywordFlattener("fillfactor"),
	"unit": _makeKeywordFlattener("unit"),
	"error": _makeKeywordFlattener("Error"),
	"resolution": _makeKeywordFlattener("Resolution"),
	"size": _makeKeywordFlattener("Size"),
	"pixSize": _makeKeywordFlattener("PixSize"),
	"epoch": _makeKeywordFlattener("Epoch"),
	"coos": _flattenValue,
	"refpos": _flattenRefPos,
}


def _make1DCooFlattener(posKey, frameKeys):
	"""returns a flattener for 1-D coordinates (time, spectral, redshift).
	"""
	flatteners = {
		"pos": _makePosValueFlattener(posKey),
		}
	flatteners.update(_commonFlatteners)
	keyList = ["type", "fillfactor"]+frameKeys+["coos", "pos", 
		"unit", "error", "resolution", "pixSize"]
	def flatten(node):
		return _joinKeysWithNull(node, keyList, flatteners)
	return flatten


def _makeVelocityFlattener():
	"""returns a flattener for velocities.

	This is only used by _makePositionFlattener, since velocity is a subclause.
	"""
	flatteners = {
		"pos": _makePosValueFlattener("VelocityInterval"),
		}
	flatteners.update(_commonFlatteners)

	def flattenVelocity(val, node):
		"""custom flattener for velocities, used by _flattenPosition.
		"""
		res = []
		if val:
			if val.get("coos") is not None:
				res.extend(["VelocityInterval", _joinKeysWithNull(val, 
					["fillfactor", "coos"], flatteners)])
			if val.get("pos") is not None:
				res.extend(["Velocity", _joinKeysWithNull(val, ["pos"], flatteners)])
			if not res:
				res.append("Velocity")
			res.append(_joinKeysWithNull(val, 
				["unit", "error", "resolution", "size", "pixSize"], flatteners))
		return _joinWithNull(res)

	return flattenVelocity


def _makeSpatialFlattener():
	def flattenCompoundChildren(childList, node):
		"""custom flattener for compounds (i.e., and, or, not)
		"""
		res = []
		for c in childList:
			if "geoCoos" in c:  # it's an atomic geometry
				res.append("%s %s"%(
					c["subtype"], _flattenValue(c["geoCoos"])))
			else: # it's a compound
				res.append("%s %s"%(c["subtype"],
					flattenCompoundChildren(c["children"], node)))
		if "geoCoos" in node:  # it's atomic, no parens required
			return " ".join(res)
		else:
			return "(%s)"%(" ".join(res))

	flatteners = {
		"pos": _makePosValueFlattener("Position"),
		"geoCoos": _makeKeywordFlattener(""),
		"velocity": _makeVelocityFlattener(),
		"children": flattenCompoundChildren,
	}
	flatteners.update(_commonFlatteners)

	def flattenPosition(node):
		"""returns an STC-S representation of position and velocity.
		"""
		return _joinKeysWithNull(node, ["type", "fillfactor", "frame", 
			"equinox", "refpos", "flavor", "epoch", "coos", "geoCoos", "children", 
			"pos", "unit", "error", "resolution", "size", "pixSize", "velocity"], 
			flatteners)
	
	return flattenPosition


# generate top-level flatteners

_flattenTime = _make1DCooFlattener("Time", ["timescale", "refpos"])
_flattenSpectral = _make1DCooFlattener("Spectral", ["refpos"])
_flattenRedshift = _make1DCooFlattener("Redshift", 
	["refpos", "redshiftType", "dopplerdef"])
_flattenSpatial = _makeSpatialFlattener()

def _flattenSystem(node):
	if node:
		return "System %s"%node


def _flattenCST(cst):
	"""returns a flattened string for an STCS CST.

	Flattening destroys the tree.
	"""
	return "\n".join([s for s in (
			_flattenTime(cst.get("time", {})),
			_flattenSpatial(cst.get("space", {})),
			_flattenSpectral(cst.get("spectral", {})),
			_flattenRedshift(cst.get("redshift", {})),
			_flattenSystem(cst.get("libSystem")),)
		if s])


def getSTCS(astRoot):
	"""returns an STC-S string for an AST.
	"""
	cst = stcs.removeDefaults({
		"time": _timeToCST(astRoot),
		"space": _spatialToCST(astRoot),
		"spectral": _spectralToCST(astRoot),
		"redshift": _redshiftToCST(astRoot),
		"libSystem": _sysIdToCST(astRoot),
	})
	return _flattenCST(cst)


def getSpatialSystem(astRoot):
	"""returns a phrase for the spatial system (for manual STC-S generation).
	"""
	cst = stcs.removeDefaults({"space": _spatialToCST(astRoot)})
	return _joinKeysWithNull(cst["space"], ["frame", 
			"equinox", "refpos", "flavor", "epoch"], _commonFlatteners)


def _boxMapperFactory(colDesc):
	"""A factory for Boxes.
	"""
	if colDesc["dbtype"]!="box":
		return

	if colDesc.original.stc:
		systemString = getSpatialSystem(colDesc.original.stc)
	else:
		systemString = "UNKNOWN"

	def mapper(val):
		if val is None:
			return ""
		else:
			return "Box %s %s %s %s %s"%((systemString,)+val[0]+val[1])
	colDesc["datatype"], colDesc["arraysize"] = "char", "*"
	return mapper
utils.registerDefaultMF(_boxMapperFactory)
