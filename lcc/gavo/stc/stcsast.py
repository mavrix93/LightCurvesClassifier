"""
Transformation of STC-S CSTs to STC ASTs.

The central function here is buildTree; the rest of the module basically
provides the handler functions.  All this is tied together in parseSTCS.
"""

#c Copyright 2008-2016, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from gavo.stc import common
from gavo.stc import dm
from gavo.stc import stcs
from gavo.stc import syslib


def buildTree(tree, context, pathFunctions={}, nameFunctions={},
		typeFunctions={}):
	"""traverses tree, calling functions on nodes.

	pathFunctions is a dictionary mapping complete paths (i.e., tuples
	of node labels) to handler functions, nameFunctions name a single
	label and are called for nodes that don't match a pathFunction if
	the last item of their paths is the label.  Both of these currently
	are not used.  Instead, everything hinges on the fallback, which is
	a node's type value (generated from the key words), matched against
	typeFunctions.

	The handler functions must be iterators.  If they yield anything,
	it must be key-value pairs.

	All key-value pairs are collected in a dictionary that is then
	returned.  If value is a tuple, it is appended to the current value
	for the key.

	Context is an arbitrary object containing ancillary information for
	building nodes.  What's in there and what's not is up to the functions
	and their callers.
	"""
	resDict = {}
	for path, node in stcs.iterNodes(tree):
		if path in pathFunctions:
			handler = pathFunctions[path]
		elif path and path[-1] in nameFunctions:
			handler = nameFunctions[path[-1]]
		elif node.get("type") in typeFunctions:
			handler = typeFunctions[node["type"]]
		else: # No handler, ignore this node
			continue
		for res in handler(node, context):
			k, v = res
			if isinstance(v, tuple):
				resDict.setdefault(k, []).extend(v)
			else:
				if k in resDict:
					raise common.STCInternalError("Attempt to overwrite key '%s', old"
						" value %s, new value %s (this should probably have been"
						" a tuple)"%(k, resDict[k], v))
				resDict[k] = v
	return resDict


class GenericContext(object):
	"""is an object that can be used for context.

	It simply exposes all its constructor arguments as attributes.
	"""
	def __init__(self, **kwargs):
		for k, v in kwargs.iteritems():
			setattr(self, k, v)


############## Coordinate systems

def _makeRefpos(node):
	refposName = node.get("refpos")
	if refposName=="UNKNOWNRefPos":
		refposName = None
	return dm.RefPos(standardOrigin=refposName,
		planetaryEphemeris=node.get("plEphemeris"))

def _buildRedshiftFrame(node, context):
	yield "redshiftFrame", dm.RedshiftFrame(dopplerDef=node["dopplerdef"], 
		type=node["redshiftType"], refPos=_makeRefpos(node))

# Simple translations of reference frame names from STC-S to STC-X

_frameTrans = {
	"GALACTIC": "GALACTIC_II",
	"UNKNOWNFrame": None,}

def _buildSpaceFrame(node, context):
	nDim, flavor = stcs.stcsFlavors[node["flavor"]]
	frame = node["frame"]
	frame = _frameTrans.get(frame, frame)
	equinox = None
	if node.get("equinox"):
		if "." in node["equinox"]: 
			equinox = node["equinox"]
		else: # allow J2000 and expand it to J2000.0
			equinox = node["equinox"]+".0"
	yield "spaceFrame", dm.SpaceFrame(refPos=_makeRefpos(node),
		flavor=flavor, nDim=nDim, refFrame=frame, equinox=equinox)

def _buildSpectralFrame(node, context):
	yield "spectralFrame", dm.SpectralFrame(
		refPos=_makeRefpos(node))

def _buildTimeFrame(node, context):
	ts = node.get("timescale")
	if ts=="nil":
		ts = None
	yield "timeFrame", dm.TimeFrame(refPos=_makeRefpos(node),
		timeScale=ts)

def getCoordSys(cst):
	"""returns constructor arguments for a CoordSys from an STC-S CST.
	"""
	args = buildTree(cst, None, nameFunctions={
		'redshift': _buildRedshiftFrame,
		'space': _buildSpaceFrame,
		'spectral': _buildSpectralFrame,
		'time': _buildTimeFrame,
	})
	return "system", dm.CoordSys(**args)


############## Coordinates and their intervals


def iterVectors(values, dim, spatial):
	"""iterates over dim-dimensional vectors made of values.

	The function does not check if the last vector is actually complete.
	"""
	if isinstance(values, common.ColRef):
		yield values
		return
	if dim==1 and not spatial:
		for v in values:
			yield v
	else:
		for index in range(0, len(values), dim):
			yield tuple(values[index:index+dim])


def _iterIntervals(coos, dim, spatial=False):
	"""iterates over pairs dim-dimensional vectors.

	It will always return at least one empty (i.e., None, None) pair.
	The last pair returned may be incomplete (specifying a start
	value only, supposedly) but not empty.
	"""
	first, startValue = True, None
	for item in iterVectors(coos, dim, spatial):
		if startValue is None:
			if first:
				first = False
			startValue = item
		else:
			yield (startValue, item)
			startValue = None
	if startValue is None:
		if first:
			yield (None, None)
	else:
		yield (startValue, None)


def _makeWiggleValues(nDim, val, minItems=None, maxItems=None, spatial=False):
	if val is None: 
		return
	values = _makeCooValues(nDim, val, minItems, maxItems, spatial)
	if not values:
		return
	if nDim>1:  # might be error radii if all values are equal
		if set([1])==set(len(set(v)) for v in values):
			return dm.RadiusWiggle(radii=tuple(v[0] for v in values))
	return dm.CooWiggle(values=values)


def _validateCoos(values, nDim, minItems, maxItems):
	"""makes sure values is valid a source of between minItems and maxItems
	nDim-dimensional tuples.

	minItems and maxItems may both be None to signify no limit.
	"""
	if isinstance(values, common.GeometryColRef):
		values.expectedLength = nDim
	numItems = len(values)/nDim
	if numItems*nDim!=len(values):
		# special case: a *single* ColRef is good for anything (could be
		# an array or something)
		if len(values)==1 and isinstance(values[0], common.ColRef):
			return
		raise common.STCSParseError("%s is not valid input to create %d-dimensional"
			" coordinates"%(values, nDim))
	if minItems is not None and numItems<minItems:
		raise common.STCSParseError("Expected at least %d coordinates in %s."%(
			minItems, values))
	if maxItems is not None and numItems>maxItems:
		raise common.STCValueError(
			"Expected not more than %d coordinates in %s."%(maxItems, values))


def _makeCooValues(nDim, values, minItems=None, maxItems=None, spatial=False):
	"""returns a list of nDim-Tuples made up of values.

	If values does not contain an integral multiple of nDim items,
	the function will raise an STCSParseError.  You can also optionally
	give a minimally or maximally expected number of tuples.  If the 
	constraints are violated, again an STCSParseError is raised.

	If spatial is true, tuples will be returned even for 1D data.
	"""
	if values is None:
		if minItems:
			raise common.STCSParseError("Expected at least %s coordinate items but"
				" found none."%minItems)
		else:
			return
	_validateCoos(values, nDim, minItems, maxItems)
	return tuple(v for v in iterVectors(values, nDim, spatial))


def _addUnitPlain(args, node, frame):
	args["unit"] = node.get("unit")


def _addUnitRedshift(args, node, frame):
	unit = node.get("unit")
	if unit=="nil":
		args["unit"] = ""
		args["velTimeUnit"] = None
	elif unit:
		parts = unit.split("/")
		if len(parts)!=2:
			raise common.STCSParseError("'%s' is not a valid unit for redshifts"%unit)
		args["unit"] = parts[0]
		args["velTimeUnit"] = parts[1]


def _mogrifySpaceUnit(unit, nDim):
	if unit:
		parts = unit.split()
		if len(parts)==nDim:
			return tuple(parts)
		elif len(parts)==1:
			return (unit,)*nDim
		else:
			raise common.STCSParseError("'%s' is not a valid for unit %d-dimensional"
				" spatial coordinates"%(unit, nDim))


def _addUnitSpatial(args, node, frame):
	unit, nDim = node.get("unit"), frame.nDim
	args["unit"] = _mogrifySpaceUnit(unit, nDim)


def _addUnitVelocity(args, node, frame):
	unit, nDim = node.get("unit"), frame.nDim
	if unit:
		su, vu = [], []
		parts = unit.split()
		for uS in parts:
			up = uS.split("/")
			if len(up)!=2:
				raise common.STCSParseError(
					"'%s' is not a valid unit for velocities."%uS)
			su.append(up[0])
			vu.append(up[1])
		args["unit"] = _mogrifySpaceUnit(" ".join(su), nDim)
		args["velTimeUnit"] = _mogrifySpaceUnit(" ".join(vu), nDim)


_unitMakers = {
	dm.SpectralType: _addUnitPlain,
	dm.TimeType: _addUnitPlain,
	dm.SpaceType: _addUnitSpatial,
	dm.RedshiftType: _addUnitRedshift,
	dm.VelocityType: _addUnitVelocity,
}


def _makeBasicCooArgs(node, frame, posClass, spatial=False):
	"""returns a dictionary containing constructor arguments common to
	all items dealing with coordinates.
	"""
	nDim = frame.nDim
	args = {
		"error": _makeWiggleValues(nDim, node.get("error"), maxItems=2,
			spatial=spatial),
		"resolution": _makeWiggleValues(nDim, node.get("resolution"), maxItems=2,
			spatial=spatial),
		"pixSize": _makeWiggleValues(nDim, node.get("pixSize"), maxItems=2,
			spatial=spatial),
		"size": _makeWiggleValues(nDim, node.get("size"), maxItems=2,
			spatial=spatial),
		"frame": frame,
	}
	if spatial and node.get("epoch"):
		args["epoch"] = float(node["epoch"][1:])
		args["yearDef"] = node["epoch"][0]
	_unitMakers[posClass.cType](args, node, frame)
	return args


def _makeCooBuilder(frameName, intervalClass, intervalKey,
		posClass, posKey, iterIntervKeys, spatial=False):
	"""returns a function(node, context) -> ASTNode for building a
	coordinate-like AST node.

	frameName is the name of the coordinate frame within
	context.system,

	(interval|pos)(Class|Key) are the class (key) to be used
	(returned) for the interval/geometry and simple coordinate found
	in the phrase.	If intervalClass is None, no interval/geometry
	will be built.

	iterIntervKeys is an iterator that yields key/value pairs for intervals
	or geometries embedded.

	Single positions are always expected under the coo key.
	"""
	positionExclusiveKeys = ["error", "resolution", "pixSize", "value",
		"size", "unit", "velTimeUnit", "epoch", "yearDef"]
	def builder(node, context):
		frame = getattr(context.system, frameName)
		nDim = frame.nDim
		args = _makeBasicCooArgs(node, frame, posClass, spatial)

		# Yield a coordinate
		if "pos" in node:
			args["value"] = _makeCooValues(nDim, node["pos"],
				minItems=1, maxItems=1, spatial=spatial)[0]
		else:
			args["value"] = None
		yield posKey, posClass(**args)

		# Yield an area if defined in this phrase and non-empty
		if intervalClass is None:
			return
		for key in positionExclusiveKeys:
			if key in args:
				del args[key]
		for k, v in iterIntervKeys(node, nDim, spatial=spatial):
			args[k] = v
		if "fillfactor" in node:
			args["fillFactor"] = node["fillfactor"]
		if len(set(args))>1: # don't yield intervals that just define a frame
			yield intervalKey, (intervalClass(**args),)

	return builder


def _makeIntervalKeyIterator(preferUpper=False):
	"""returns a function yielding ASTNode constructor keys for intervals.
	"""
	def iterKeys(node, nDim, spatial=False):
		res, coos = {}, node.get("coos", ())
		_validateCoos(coos, nDim, None, None)
		for interval in _iterIntervals(coos, nDim, spatial):
			if preferUpper:
				res["upperLimit"], res["lowerLimit"] = interval
			else:
				res["lowerLimit"], res["upperLimit"] = interval
		if res["upperLimit"]:
			yield "upperLimit", res["upperLimit"]
		if res["lowerLimit"]:
			yield "lowerLimit", res["lowerLimit"]
	return iterKeys



###################### Geometries


def _makeGeometryKeyIterator(argDesc, clsName):
	"""returns a key iterator for use with _makeCooBuilder that yields
	the keys particular to certain geometries.

	ArgDesc describes what keys should be parsed from the node's coos key.  
	It consists for tuples of name and type code, where type code is one of:

		- r -- a single real value.
		- v -- a vector of dimensionality given by the system (i.e., nDim).
		- rv -- a sequence of v items of arbitrary length.
		- cv -- a sequence of "Convex" vectors (dim 4) of arbitrary length.

	rv may only occur at the end of argDesc since it will consume all
	remaining coordinates.
	"""
	parseLines = [
		"def iterKeys(node, nDim, spatial=True):",
		'  if False: yield',  # make sure the thing is an iterator
		'  coos = node.get("coos", ())',
		'  yield "origUnit",'
		' _mogrifySpaceUnit(node.get("unit"), nDim)',
		"  try:",
		"    pass"]
	# Everthing below here just coordinates
	parseLines.extend([
		'    if isinstance(coos, common.GeometryColRef):',
		'      yield "geoColRef", coos',
		'      return'])
	for name, code in argDesc:
		if code=="r":
			parseLines.append('    yield "%s", coos.pop(0)'%name)
		elif code=="v":
			parseLines.append('    vec = coos[:nDim]')
			parseLines.append('    coos = coos[nDim:]')
			parseLines.append('    _validateCoos(vec, nDim, 1, 1)')
			parseLines.append('    yield "%s", tuple(vec)'%name)
		elif code=="rv":
			parseLines.append('    yield "%s", _makeCooValues(nDim, coos)'%name)
			parseLines.append('    coos = []')
		elif code=="cv":
			parseLines.append('    yield "%s", _makeCooValues(4, coos)'%name)
			parseLines.append('    coos = []')
	parseLines.append('  except IndexError:')
	parseLines.append('    raise common.STCSParseError("Not enough coordinates'
		' while parsing %s")'%clsName)
	parseLines.append(
		'  if coos: raise common.STCSParseError("Too many coordinates'
		' while building %s, remaining: %%s"%%coos)'%clsName)
	exec "\n".join(parseLines)
	return iterKeys  #noflake: name created via exec


def _makeGeometryKeyIterators():
	return dict(
		(clsName, _makeGeometryKeyIterator(argDesc, clsName))
		for clsName, argDesc in [
			("AllSky", []),
			("Circle", [('center', 'v'), ('radius', 'r')]),
			("Ellipse", [('center', 'v'), ('smajAxis', 'r'), ('sminAxis', 'r'), 
				('posAngle', 'r')]),
			("Box", [('center', 'v'), ('boxsize', 'v')]),
			("Polygon", [("vertices", "rv")]),
			("Convex", [("vectors", "cv")]),
			("PositionInterval", [("lowerLimit", "v"), ("upperLimit", "v")]),
		])

_geometryKeyIterators = _makeGeometryKeyIterators()


def _makeGeometryBuilder(cls):
	"""returns a builder for Geometries.

	See _makeGeometryKeyIterator for the meaning of the arguments.
	"""
	return _makeCooBuilder("spaceFrame", cls, "areas", dm.SpaceCoo,
		"place", _geometryKeyIterators[cls.__name__], spatial=True)


def _compoundGeometryKeyIterator(node, nDim, spatial):
	"""yields keys to configure compound geometries.
	"""
	children = []
	for c in node["children"]:
		childType = c["subtype"]
		destCls = getattr(dm, childType)
		if childType in _geometryKeyIterators:
			children.append(destCls(**dict(
				_geometryKeyIterators[childType](c, nDim, True))))
		else: # child is another compound geometry
			children.append(destCls(**dict(
				_compoundGeometryKeyIterator(c, nDim, True))))
	yield "children", children


def _makeCompoundGeometryBuilder(cls):
	"""returns a builder for compound geometries.
	"""
	return _makeCooBuilder("spaceFrame", cls, "areas", dm.SpaceCoo,
		"place", _compoundGeometryKeyIterator, spatial=True)


###################### Top level


def getCoords(cst, system):
	"""returns an argument dict for constructing STCSpecs for plain coordinates.
	"""
	context = GenericContext(system=system)

	return buildTree(cst, context, typeFunctions = {
		"Time": _makeCooBuilder("timeFrame", None, None,
			dm.TimeCoo, "time", None),
		"StartTime": _makeCooBuilder("timeFrame", dm.TimeInterval, "timeAs",
			dm.TimeCoo, "time", _makeIntervalKeyIterator()),
		"StopTime": _makeCooBuilder("timeFrame", dm.TimeInterval, "timeAs",
			dm.TimeCoo, "time", _makeIntervalKeyIterator(preferUpper=True)),
		"TimeInterval": _makeCooBuilder("timeFrame", dm.TimeInterval, "timeAs",
			dm.TimeCoo, "time", _makeIntervalKeyIterator()),

		"Position": _makeCooBuilder("spaceFrame", None, None, dm.SpaceCoo,
			"place", None, spatial=True),
		"PositionInterval": _makeCooBuilder("spaceFrame",
			dm.SpaceInterval, "areas", dm.SpaceCoo, "place",
			_makeIntervalKeyIterator(), spatial=True),
		"Velocity": _makeCooBuilder("spaceFrame",
			dm.VelocityInterval, "velocityAs", dm.VelocityCoo, "velocity",
			_makeIntervalKeyIterator(), spatial=True),
		"VelocityInterval": _makeCooBuilder("spaceFrame",
			dm.VelocityInterval, "velocityAs", dm.VelocityCoo, "velocity",
			_makeIntervalKeyIterator(), spatial=True),
		"AllSky": _makeGeometryBuilder(dm.AllSky),
		"Circle": _makeGeometryBuilder(dm.Circle),
		"Ellipse": _makeGeometryBuilder(dm.Ellipse),
		"Box": _makeGeometryBuilder(dm.Box),
		"Polygon": _makeGeometryBuilder(dm.Polygon),
		"Convex": _makeGeometryBuilder(dm.Convex),

		"Union": _makeCompoundGeometryBuilder(dm.Union),
		"Intersection": _makeCompoundGeometryBuilder(dm.Intersection),
		"Difference": _makeCompoundGeometryBuilder(dm.Difference),
		"Not": _makeCompoundGeometryBuilder(dm.Not),

		"Spectral": _makeCooBuilder("spectralFrame", None, None,
			dm.SpectralCoo, "freq", None),
		"SpectralInterval": _makeCooBuilder("spectralFrame", 
			dm.SpectralInterval, "freqAs", dm.SpectralCoo, "freq",
			_makeIntervalKeyIterator()),

		"Redshift": _makeCooBuilder("redshiftFrame", None, None,
			dm.RedshiftCoo, "redshift", None),
		"RedshiftInterval": _makeCooBuilder("redshiftFrame", 
			dm.RedshiftInterval, "redshiftAs", dm.RedshiftCoo, "redshift",
			_makeIntervalKeyIterator()),

	})


def parseSTCS(literal, grammarFactory=None):
	"""returns an STC AST for an STC-S expression.
	"""
	cst = stcs.getCST(literal, grammarFactory)
	if "libSystem" in cst:
		system = syslib.getLibrarySystem(cst["libSystem"])
	else:
		system = getCoordSys(cst)[1]
	args = {"astroSystem": system}
	args.update(getCoords(cst, system))
	return dm.STCSpec(**args).polish()


def parseQSTCS(literal):
	"""returns an STC AST for an STC-S expression with identifiers instead of
	values.

	The identifiers are denoted in double-quoted strings.  Legal identifiers
	follow the python syntax (i.e., these are *not* SQL quoted identifiers).
	"""
	return parseSTCS(literal, grammarFactory=stcs.getColrefGrammar)


if __name__=="__main__":
	print parseSTCS("Union FK5 (Box 12 -13 2 2 Not (Circle 14 -13.5 3))")
