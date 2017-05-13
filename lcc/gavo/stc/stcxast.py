"""
Building ASTs from STC-X trees.

The idea here is run buildTree on an ElementTree of the STC-X input.

buildTree has a dictionary mapping element names to handlers.  This dictionary
is built with a modicum of metaprogramming within _getHandlers.

Each handler receives the ElementTree node it is to operate on, the current
buildArgs (i.e., a dictionary containing for building instances collected by
buildTree while walking the tree), and a context object.

Handlers yield keyword-value pairs that are added to the buildArgs.  If
the value is a tuple or list, it will be appended to the current value
for that keyword, otherwise it will fill this keyword.  Overwrites are
not allowed.
"""

#c Copyright 2008-2016, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from gavo import utils
from gavo.stc import common
from gavo.stc import dm
from gavo.stc import syslib
from gavo.stc import times
from gavo.stc import units


WIGGLE_TYPES = ["error", "resolution", "size", "pixSize"]


class SIBLING_ASTRO_SYSTEM(object):
	"""A sentinel class to tell the id resolver to use the sibling AstroCoordSys
	element."""


####################### Helpers

def STCElement(name):
	return utils.ElementTree.QName(common.STCNamespace, name)
_n = STCElement


def _localname(qName):
	"""hacks the local tag name from a {ns}-serialized qName.
	"""
	qName = str(qName)
	return qName[qName.find("}")+1:]


def _passthrough(node, buildArgs, context):
	"""yields the items of buildArgs.

	This can be used for "no-op" elements.
	"""
	return buildArgs.iteritems()


def _noIter(ign, ored):
	if False: yield None

def _buildTuple(val):
	return (val,)


def _makeUnitYielder(unitKeys, prefix="", tuplify=False):
	"""returns a function that yields unit information from an elementTree
	node.
	"""
	if tuplify:
		mkRes = _buildTuple
	else:
		mkRes = utils.identity
	def yieldUnits(node, buildArgs):
		for key in unitKeys:
			if key in node.attrib:
				yield prefix+key, mkRes(node.get(key))
			elif key in buildArgs:
				yield prefix+key, buildArgs[key]
	return yieldUnits


def _makeKeywordBuilder(kw):
	"""returns a builder that returns the node's text content under kw.
	"""
	def buildKeyword(node, buildArgs, context):
		yield kw, node.text
	return buildKeyword



def _makeKwValuesBuilder(kwName, tuplify=False, units=_noIter):
	"""returns a builder that takes vals from the buildArgs and
	returns a tuple of them under kwName.

	The vals key is left by builders like _buildVector.
	"""
	if tuplify:
		def buildNode(node, buildArgs, context):
			yield kwName, (tuple(buildArgs["vals"]),)
			for res in units(node, buildArgs): yield res
	else:
		def buildNode(node, buildArgs, context): #noflake: previous def conditional
			yield kwName, (buildArgs["vals"],)
			for res in units(node, buildArgs): yield res
	return buildNode


def _makeKwValueBuilder(kwName, tuplify=False, units=_noIter):
	"""returns a builder that takes vals from the buildArgs and
	returns a single value under kwName.

	The vals key is left by builders like _buildVector.
	"""
	if tuplify:
		def buildNode(node, buildArgs, context):
			yield kwName, tuple(buildArgs.get("vals", ())),
			for res in units(node, buildArgs): yield res
	else:
		def buildNode(node, buildArgs, context): #noflake: previous def conditional
			yield kwName, buildArgs.get("vals", None),
			for res in units(node, buildArgs): yield res
	return buildNode


def _makeKwFloatBuilder(kwName, multiple=True, units=_noIter):
	"""returns a builder that returns float(node.text) under kwName.

	The builder will also yield unit keys if units are present.

	If multiple is True, the values will be returned in 1-tuples, else as
	simple values.
	"""
	if multiple:
		def buildNode(node, buildArgs, context):
			if isinstance(node.text, common.ColRef):
				yield kwName, (node.text,)
			elif node.text and node.text.strip():
				yield kwName, (float(node.text),)
			for res in units(node, buildArgs): yield res
	else:
		def buildNode(node, buildArgs, context): #noflake: previous def conditional
			if isinstance(node.text, common.ColRef):
				yield kwName, node.text
			elif node.text and node.text.strip():
				yield kwName, float(node.text)
			for res in units(node, buildArgs): yield res
	return buildNode


def _makeNodeBuilder(kwName, astObject):
	"""returns a builder that makes astObject with the current buildArgs
	and returns the thing under kwName.
	"""
	def buildNode(node, buildArgs, context):
		buildArgs["id"] = node.get("id", None)
		yield kwName, astObject(**buildArgs)
	return buildNode


def _fixSpectralUnits(node, buildArgs, context):
	unit = None
	if "unit" in node.attrib:
		unit = node.get("unit")
	if "unit" in buildArgs:
		unit = buildArgs["unit"]
	if "spectral_unit" in buildArgs:
		unit = buildArgs["spectral_unit"]
		del buildArgs["spectral_unit"]
	buildArgs["unit"] = unit


def _fixTimeUnits(node, buildArgs, context):
	unit = None
	if "unit" in node.attrib:
		unit = node.get("unit")
	if "unit" in buildArgs:
		unit = buildArgs["unit"]
	if "time_unit" in buildArgs:
		unit = buildArgs["time_unit"]
		del buildArgs["time_unit"]
	buildArgs["unit"] = unit


def _fixRedshiftUnits(node, buildArgs, context):
	sUnit = node.get("unit")
	if "unit" in buildArgs:
		sUnit = buildArgs["unit"]
	if "pos_unit" in buildArgs:
		sUnit = buildArgs["pos_unit"]
		del buildArgs["pos_unit"]
	vUnit = node.get("vel_time_unit")
	if "vel_time_unit" in buildArgs:
		vUnit = buildArgs["vel_time_unit"]
		del buildArgs["vel_time_unit"]
	buildArgs["unit"] = sUnit
	buildArgs["velTimeUnit"] = vUnit


def _makeSpatialUnits(nDim, *unitSources):
	"""returns a units value from unitSources.

	The tuple has length nDim, unitSources are arguments that are either
	None, strings, or tuples.  The first non-None-one wins, strings and 1-tuples
	are expanded to length nDim.
	"""
	for unit in unitSources:
		if not unit:
			continue
		if isinstance(unit, (tuple, list)):
			if len(unit)==1:
				return tuple(unit*nDim)
			elif len(unit)==nDim:
				return tuple(unit)
			else:
				raise common.STCValueError("Cannot construct %d-dimensional units from"
					" %s."%(nDim, repr(unit)))
		else: # a string or something similar
			return (unit,)*nDim
	return None


def _fixSpatialUnits(node, buildArgs, context):
	nDim = context.peekDim()

	# buildArgs["unit"] may have been left in build_args from upstream
	buildArgs["unit"] = _makeSpatialUnits(nDim, buildArgs.pop("unit", None),
		node.get("unit", "").split())

	# This only kicks in for velocities
	buildArgs["velTimeUnit"] = _makeSpatialUnits(nDim, 
		buildArgs.pop("vel_time_unit", ()), node.get("vel_time_unit", "").split())
	if not buildArgs["velTimeUnit"]:
		del buildArgs["velTimeUnit"]

	if not buildArgs["unit"]:
		# it's actually legal to have to unit on the position but on some
		# wiggle (sigh).  Adopt the first one we find if that's true.
		for wiggleType in WIGGLE_TYPES:
			if buildArgs.has_key(wiggleType):
				if buildArgs[wiggleType].origUnit:
					buildArgs["unit"] = buildArgs[wiggleType].origUnit
					break
		else:
			del buildArgs["unit"]
	
	# sometimes people give position1d for nDim=2...  *Presumably*
	# actual units are the same on both axes then.  Sigh
	mainUnit = buildArgs.get("unit")
	if mainUnit and len(mainUnit)==2 and mainUnit[1] is None:
		buildArgs["unit"] = (mainUnit[0], mainUnit[0])


_unitFixers = {
	"spectralFrame": _fixSpectralUnits,
	"redshiftFrame": _fixRedshiftUnits,
	"timeFrame": _fixTimeUnits,
	"spaceFrame": _fixSpatialUnits,
}

def _fixUnits(frameName, node, buildArgs, context):
	"""changes the keys in buildArgs to match the requirements of node.

	This fans out to frame type-specific helper functions.  The principle is:
	Attributes inherited from lower-level items (i.e. the specific values)
	override a unit specification on node.
	"""
	return _unitFixers[frameName](node, buildArgs, context)


def _iterCooMeta(node, context, frameName):
	"""yields various meta information for coordinate-like objects.
	
	For frame, it returns a proxy for a coordinate's reference frame.
	For unit, if one is given on the element, override whatever we may 
	have got from downtree.

	Rules for inferring the frame:

	If there's a frame id on node, use it. 
	
	Else see if there's a coo sys id on the frame.  If it's missing, take 
	it from the context, then make a proxy to the referenced system's 
	spatial frame.
	"""
	if "frame_id" in node.attrib:
		yield "frame", IdProxy(idref=node.get("frame_id"))
	elif "coord_system_id" in node.attrib:
		yield "frame", IdProxy(idref=node.get("frame_id"), useAttr=frameName)
	else:
		yield "frame", IdProxy(idref=context.sysIdStack[-1], 
			useAttr=frameName)
	if "fill_factor" in node.attrib and node.get("fill_factor"):
		yield "fillFactor", float(node.get("fill_factor"))
	if "id" in node.attrib and node.get("id"):
		yield "id", node.get("id")


# A dictionary mapping STC-X element names to the dimensionality of
# coordinates within them.  You only need to give them here if _guessNDim
# doesn't otherwise the it right.
_dimExceptions = {
}

def _guessNDim(kw):
	"""guesses the number of dimensions that should be present under the STC-X
	element named kw by inspecting the name.
	"""
	if kw in _dimExceptions:
		return _dimExceptions[kw]
	if "3" in kw:
		return 3
	elif "2" in kw:
		return 2
	else:
		return 1


def _makeIntervalBuilder(kwName, astClass, frameName, tuplify=False):
	"""returns a builder that makes astObject with the current buildArgs
	and fixes its frame reference.
	"""
	if tuplify:
		def mkVal(v):
			if isinstance(v, (tuple, list)):
				return v
			else:
				return (v,)
	else:
		def mkVal(v): #noflake: previous def conditional
			return v
	def buildNode(node, buildArgs, context):
		context.pushDim(_guessNDim(_localname(node.tag)))
		for key, value in _iterCooMeta(node, context, frameName):
			buildArgs[key] = value
		if "lowerLimit" in buildArgs:
			buildArgs["lowerLimit"] = mkVal(buildArgs["lowerLimit"][0])
		if "upperLimit" in buildArgs:
			buildArgs["upperLimit"] = mkVal(buildArgs["upperLimit"][0])
		_fixUnits(frameName, node, buildArgs, context)
		buildArgs["origUnit"] = (buildArgs.pop("unit", None),
			buildArgs.pop("velTimeUnit", None))
		context.popDim()
		yield kwName, (astClass(**buildArgs),)
	return buildNode


def _fixWiggles(buildArgs):
	"""modifies buildArgs so all wiggles are properly wrapped in their
	classes.
	"""
	for wiggleType in WIGGLE_TYPES:
		localArgs = {}
		wigClass = None

		# pop any units destined for us from buildArgs -- boy, this whole
		# units stuff is messy.  How the heck was that meant to work?
		velTimeUnit = buildArgs.pop(wiggleType+"vel_time_unit", None)
		if wiggleType+"unit" in buildArgs:
			localArgs["origUnit"] = (buildArgs.pop(wiggleType+"unit", None),
				velTimeUnit)
		if wiggleType+"pos_unit" in buildArgs:
			localArgs["origUnit"] = (buildArgs.pop(wiggleType+"pos_unit", None),
				velTimeUnit)

		if wiggleType in buildArgs:
			localArgs["values"] = tuple(buildArgs.pop(wiggleType))
			wigClass = dm.CooWiggle
		elif wiggleType+"Radius" in buildArgs:
			wigClass = dm.RadiusWiggle
			localArgs["radii"] = buildArgs.pop(wiggleType+"Radius")
		elif wiggleType+"Matrix" in buildArgs:
			localArgs["matrices"] = buildArgs.pop(wiggleType+"Matrix")
			wigClass = dm.MatrixWiggle
		if wigClass is not None:
			buildArgs[wiggleType] = wigClass(**localArgs)


def _makePositionBuilder(kw, astClass, frameName, tuplify=False):
	"""returns a builder for a coordinate of astClass to be added with kw.
	"""
	def buildPosition(node, buildArgs, context):
		context.pushDim(_guessNDim(_localname(node.tag)))
		if buildArgs.get("vals"):
			buildArgs["value"] = buildArgs["vals"][0]
			# Fix 1D space coordinates
			if tuplify and not isinstance(buildArgs["value"], (list, tuple)):
				buildArgs["value"] = (buildArgs["value"],)
			del buildArgs["vals"]
		for key, value in _iterCooMeta(node, context, frameName):
			buildArgs[key] = value
		_fixWiggles(buildArgs)
		_fixUnits(frameName, node, buildArgs, context)
		context.popDim()
		yield kw, astClass(**buildArgs)
	return buildPosition


class ContextActions(object):
	"""A specification of context actions for certain elements.

	You will want to override both start and stop.  The methods
	should not change node.
	"""
	def start(self, context, node):
		pass

	def stop(self, context, node):
		pass


################ Coordinate systems

_xlinkHref = utils.ElementTree.QName(common.XlinkNamespace, "href")

def _buildAstroCoordSystem(node, buildArgs, context):
	buildArgs["id"] = node.get("id", None)
	# allow non-qnamed href, too, mainly for accomodating our
	# namespace-eating relational resource importer
	if _xlinkHref in node.attrib:
		hrefVal = node.attrib[_xlinkHref]
	elif "xlink:href" in node.attrib:
		hrefVal = node.attrib["xlink:href"]
	else:
		hrefVal = None

	if hrefVal is None:
		newEl = dm.CoordSys(**buildArgs)
	else:
		newEl = syslib.getLibrarySystem(hrefVal).change(**buildArgs)

	# Hack -- make sure we have a good id here, even when this means
	# a violation of our non-mutability ideology.
	if newEl.id is None:
		newEl.id = utils.intToFunnyWord(id(newEl))
	yield "astroSystem", newEl


def _buildPlanetaryEphem(node, buildArgs, context):
	res = node.text.strip()
	if res:
		yield 'planetaryEphemeris', res


def _buildRefpos(node, buildArgs, context):
	refposName = _localname(node.tag)
	if refposName=="UNKNOWNRefPos":
		refposName = None
	yield 'refPos', dm.RefPos(standardOrigin=refposName,
		**buildArgs)

def _buildFlavor(node, buildArgs, context):
	yield 'flavor', _localname(node.tag)
	naxes = node.get("coord_naxes")
	if naxes is not None:
		yield 'nDim', int(naxes)

def _buildRefFrame(node, buildArgs, context):
	frameName  = _localname(node.tag)
	if frameName=="UNKNOWNFrame":
		yield 'refFrame', None
	else:
		yield 'refFrame', frameName
	for item in buildArgs.iteritems():
		yield item

def _makeFrameBuilder(attName, frameObj, **defaults):
	"""returns a function yielding keywords for frames.  
	
	You can pass additional defaults.
	"""
	def buildFrame(node, buildArgs, context):
		if "value_type" in node.attrib:  # for redshifts
			buildArgs["type"] = node.get("value_type")
		buildArgs["id"] = node.get("id")

		for key, val in defaults.iteritems():
			if key not in buildArgs:
				buildArgs[key] = val
		yield attName, frameObj(**buildArgs)
	return buildFrame


################# Coordinates

class CooSysActions(ContextActions):
	"""Actions for containers of coordinates.

	The actions push and pop the system ids of the coordinate containers
	so leaves can build their frame proxies from them.

	If none are present, None is pushed, which is to be understood as
	"use any ol' AstroCoordSystem you can find".
	"""
	def start(self, context, node):
		context.sysIdStack.append(node.get("coord_system_id", 
			SIBLING_ASTRO_SYSTEM))
	
	def stop(self, context, node):
		context.sysIdStack.pop()


def _buildTime(node, buildArgs, context):
	"""adds vals from the time node.

	node gets introspected to figure out what kind of time we're talking
	about.  The value always is a datetime instance.
	"""
	if isinstance(node.text, common.ColRef):
		yield "vals", (node.text,)
	else:
		parser = {
			"ISOTime": times.parseISODT,
			"JDTime": lambda v: times.jdnToDateTime(float(v)),
			"MJDTime": lambda v: times.mjdToDateTime(float(v)),
		}[_localname(node.tag)]
		yield "vals", (parser(node.text),)


_handledUnits = ("unit", "vel_time_unit", "pos_unit")
_buildFloat = _makeKwFloatBuilder("vals", 
	units=_makeUnitYielder(_handledUnits, tuplify=True))

_unitKeys = ("unit", "vel_time_unit")
_genUnitKeys = ("pos_unit", "time_unit", "spectral_unit", "angle_unit",
	"gen_unit")

def _buildVector(node, buildArgs, context):
	if 'vals' in buildArgs:
		yield 'vals', (tuple(buildArgs["vals"]),)
	for uk in _unitKeys:
		if uk in buildArgs:
			yield uk, tuple(buildArgs[uk])
	for uk in _genUnitKeys:
		if uk in buildArgs:
			yield "unit", tuple(buildArgs[uk])
	

def _buildEpoch(node, buildArgs, context):
	yield "yearDef", node.get("yearDef", "J")
	yield "epoch", float(node.text)


################# Geometries

class BoxActions(ContextActions):
	"""Context actions for Boxes: register a special handler for Size.
	"""
	boxHandlers = {
		_n("Size"): _makeKwValueBuilder("boxsize", tuplify=True, units=
			_makeUnitYielder(("unit",), "size")),
	}
	def start(self, context, node):
		context.specialHandlerStack.append(self.boxHandlers)
	def stop(self, context, node):
		context.specialHandlerStack.pop()


def _buildHalfspace(node, buildArgs, context):
	yield "vectors", (tuple(buildArgs["vector"])+tuple(buildArgs["offset"]),)


def _adaptCircleUnits(buildArgs):
	buildArgs["unit"] = buildArgs.pop("unit", ("deg", "deg"))
	if "radiuspos_unit" in buildArgs:
		buildArgs["radius"] = units.getBasicConverter(
			buildArgs.pop("radiuspos_unit"), buildArgs["unit"][0])(
				buildArgs["radius"])


def _adaptEllipseUnits(buildArgs):
	buildArgs["unit"] = buildArgs.pop("unit", ("deg", "deg"))
	if "smajAxispos_unit" in buildArgs:
		buildArgs["smajAxis"] = units.getBasicConverter(
			buildArgs.pop("smajAxispos_unit"), buildArgs["unit"][0])(
				buildArgs["smajAxis"])
	if "sminAxispos_unit" in buildArgs:
		buildArgs["sminAxis"] = units.getBasicConverter(
			buildArgs.pop("sminAxispos_unit"), buildArgs["unit"][0])(
				buildArgs["sminAxis"])
	if "posAngleunit" in buildArgs:
		buildArgs["posAngle"] = units.getBasicConverter(
			buildArgs.pop("posAngleunit"), "deg")(buildArgs["posAngle"])


def _adaptBoxUnits(buildArgs):
	buildArgs["unit"] = buildArgs.get("unit", ("deg", "deg"))
	if "sizeunit" in buildArgs:
		su = buildArgs.pop("sizeunit")
		if isinstance(su, basestring):
			su = (su, su)
		buildArgs["boxsize"] = units.getVectorConverter(su,
			buildArgs["unit"])(buildArgs["boxsize"])


def _makeGeometryBuilder(astClass, adaptDepUnits=None):
	"""returns a builder for STC-S geometries.
	"""
	def buildGeo(node, buildArgs, context):
		context.pushDim(2)
		for key, value in _iterCooMeta(node, context, "spaceFrame"):
			buildArgs[key] = value
		_fixSpatialUnits(node, buildArgs, context)
		if adaptDepUnits:
			adaptDepUnits(buildArgs)
		buildArgs["origUnit"] = (buildArgs.pop("unit", None), None)
		context.popDim()
		if isinstance(node.text, common.ColRef):
			buildArgs["geoColRef"] = common.GeometryColRef(str(node.text))
		yield 'areas', (astClass(**buildArgs),)
	return buildGeo


def _validateCompoundChildren(buildArgs):
	"""makes sure that all children of a future compound geometry agree in
	units and propagates units as necessary.

	origUnit attributes of children are nulled out in the process.  Sorry
	'bout ignoring immutability.
	"""
	children = buildArgs.pop("areas")
	cUnits, selfUnit = [], buildArgs.pop("unit", None)
	for c in children:
		if c.origUnit!=(None,None):
			cUnits.append(c.origUnit)
			c.origUnit = None

	if len(set(cUnits))>1:
		raise common.STCNotImplementedError(
			"Different units within compound children are not supported")
	elif len(set(cUnits))==1:
		ou = (selfUnit, None)
		if selfUnit is not None and ou!=cUnits[0]:
			raise common.STCNotImplementedError(
				"Different units on compound and compound children are not supported")
		buildArgs["origUnit"] = cUnits[0]
	else:
		if selfUnit is not None:
			buildArgs["origUnit"] = (selfUnit, None)
	buildArgs["children"] = children


def _makeCompoundBuilder(astClass):
	def buildCompound(node, buildArgs, context):
		_validateCompoundChildren(buildArgs)
		buildArgs.update(_iterCooMeta(node, context, "spaceFrame"))
		yield "areas", (astClass(**buildArgs),)
	return buildCompound


################# Toplevel

_areasAndPositions = [("timeAs", "time"), ("areas", "place"),
	("freqAs", "freq"), ("redshiftAs", "redshift"), 
	("velocityAs", "velocity")]

def _addPositionsForAreas(buildArgs):
	"""adds positions for areas defined by buildArgs.

	This only happens if no position is given so far.  The function is a
	helper for _adaptAreaUnits.  BuildArgs is changed in place.
	"""
	for areaAtt, posAtt in _areasAndPositions:
		if buildArgs.get(areaAtt) and not buildArgs.get(posAtt):
			areas = buildArgs[areaAtt]
			posAttrs = {}
			for area in areas:
				if area.origUnit is not None:
					posAttrs["unit"] = area.origUnit[0]
					if area.origUnit[1]:
						posAttrs["velTimeUnit"] = area.origUnit[1]
					area.origUnit = None
					break

			# if no spatial area had a unit, it's probably something like AllSky,
			# but we still must have *something*, anything
			if posAtt=="place" and areas and posAttrs["unit"] is None:
				posAttrs["unit"] = ("deg", "deg")

			buildArgs[posAtt] = area.getPosition(posAttrs)


def _adaptAreaUnits(buildArgs):
	"""changes area's units in buildArgs to match the positions's units.

	When areas without positions are present, synthesize the appropriate
	positions to hold units.
	"""
	_addPositionsForAreas(buildArgs)
	for areaAtt, posAtt in _areasAndPositions:
		newAreas = []
		for area in buildArgs.get(areaAtt, ()):
			if area.origUnit is not None and area.origUnit[0] is not None:
				newAreas.append(area.adaptValuesWith(
					buildArgs[posAtt].getUnitConverter(area.origUnit)))
			else:
				newAreas.append(area)
		buildArgs[areaAtt] = tuple(newAreas)
			

def _buildToplevel(node, buildArgs, context):
	_adaptAreaUnits(buildArgs)
	if "astroSystem" not in buildArgs:
		# even for a disastrous STC-X, make sure there's a AstroCoords
		# with rudimentary space and time frames
		buildArgs["astroSystem"] = dm.CoordSys(
			timeFrame=dm.TimeFrame(refPos=dm.RefPos()), 
			spaceFrame=dm.SpaceFrame(refPos=dm.RefPos(),
				flavor="SPHERICAL", nDim=2))
	yield 'stcSpec', ((node.tag, dm.STCSpec(**buildArgs)),)


class IdProxy(common.ASTNode):
	"""A stand-in for a coordinate system during parsing.

	We do this to not depend on ids being located before positions.  STC
	should have that in general, but let's be defensive here.
	"""
	_a_idref = None
	_a_useAttr = None
	
	def resolve(self, idMap):
		ob = idMap[self.idref]
		if self.useAttr:
			return getattr(ob, self.useAttr)
		return ob


def resolveProxies(forest):
	"""replaces IdProxies in the AST sequence forest with actual references.
	"""
	map = {}
	for rootTag, ast in forest:
		ast.buildIdMap()
		map.update(ast.idMap)
	for rootTag, ast in forest:
		map[SIBLING_ASTRO_SYSTEM] = ast.astroSystem
		for node in ast.iterNodes():
			for attName, value in node.iterAttributes(skipEmpty=True):
				if isinstance(value, IdProxy):
					setattr(node, attName, value.resolve(map))


class STCXContext(object):
	"""A parse context containing handlers, stacks, etc.

	A special feature is that there are "context-active" tags.  For those
	the context gets notified by buildTree when their processing is started
	or ended.  We use this to note the active coordinate systems during, e.g.,
	AstroCoords parsing.
	"""
	def __init__(self, elementHandlers, activeTags, **kwargs):
		self.sysIdStack = []
		self.nDimStack = []
		self.specialHandlerStack = [{}]
		self.elementHandlers = elementHandlers
		self.activeTags = activeTags
		for k, v in kwargs.iteritems():
			setattr(self, k, v)

	def getHandler(self, elementName):
		"""returns a builder for the qName elementName.

		If no such handler exists, we return None.
		"""
		if elementName in self.specialHandlerStack[-1]:
			return self.specialHandlerStack[-1][elementName]
		return self.elementHandlers.get(elementName)

	def startTag(self, node):
		self.activeTags[node.tag].start(self, node)

	def endTag(self, node):
		self.activeTags[node.tag].stop(self, node)
	
	def pushDim(self, nDim):
		self.nDimStack.append(nDim)
	
	def popDim(self):
		return self.nDimStack.pop()
	
	def peekDim(self):
		return self.nDimStack[-1]


_yieldErrUnits = _makeUnitYielder(_handledUnits, "error")
_yieldPSUnits = _makeUnitYielder(_handledUnits, "pixSize")
_yieldResUnits = _makeUnitYielder(_handledUnits, "resolution")
_yieldSzUnits = _makeUnitYielder(_handledUnits, "size")

# A sequence of tuples (dict builder, [stcxElementNames]) to handle
# STC-X elements by calling functions
_stcBuilders = [
	(_buildFloat, ["C1", "C2", "C3"]),
	(_buildTime, ["ISOTime", "JDTime", "MJDTime"]),
	(_buildVector, ["Value2", "Value3"]),
	(_buildRefpos, common.stcRefPositions),
	(_buildFlavor, common.stcCoordFlavors),
	(_buildRefFrame, common.stcSpaceRefFrames),

	(_makePositionBuilder('place', dm.SpaceCoo, "spaceFrame", tuplify=True), 
		["Position1D", "Position3D", "Position2D"]),
	(_makePositionBuilder('velocity', dm.VelocityCoo, "spaceFrame", 
			tuplify=True),
		["Velocity1D", "Velocity3D", "Velocity2D"]),

	(_makeKwValuesBuilder("resolution", tuplify=True, units=_yieldResUnits), 
		["Resolution2", "Resolution3"]),
	(_makeKwValuesBuilder("pixSize", tuplify=True, units=_yieldPSUnits), 
		["PixSize2", "PixSize3"]),
	(_makeKwValuesBuilder("error", tuplify=True, units=_yieldErrUnits), 
		["Error2", "Error3"]),
	(_makeKwValuesBuilder("size", tuplify=True, units=_yieldSzUnits), 
		["Size2", "Size3"]),

	(_makeKwFloatBuilder("resolutionRadius", units=_yieldResUnits), 
		["Resolution2Radius", "Resolution3Radius"]),
	(_makeKwFloatBuilder("pixSizeRadius", units=_yieldPSUnits), 
		["PixSize2Radius", "PixSize3Radius"]),
	(_makeKwFloatBuilder("errorRadius", units=_yieldErrUnits), 
		["Error2Radius", "Error3Radius"]),
	(_makeKwFloatBuilder("sizeRadius", units=_yieldSzUnits), 
		["Size2Radius", "Size3Radius"]),

	(_makeKwValuesBuilder("resolutionMatrix", units=_yieldResUnits), 
		["Resolution2Matrix", "Resolution3Matrix"]),
	(_makeKwValuesBuilder("pixSizeMatrix", units=_yieldSzUnits), 
		["PixSize2Matrix", "PixSize3Matrix"]),
	(_makeKwValuesBuilder("errorMatrix", units=_yieldErrUnits), 
		["Error2Matrix", "Error3Matrix"]),
	(_makeKwValuesBuilder("sizeMatrix", units=_yieldSzUnits), 
		["Size2Matrix", "Size3Matrix"]),

	(_makeKwValuesBuilder("upperLimit", tuplify=True), 
		["HiLimit2Vec", "HiLimit3Vec"]),
	(_makeKwValuesBuilder("lowerLimit", tuplify=True), 
		["LoLimit2Vec", "LoLimit3Vec"]),

	(_makeIntervalBuilder("areas", dm.SpaceInterval, "spaceFrame", tuplify=True),
		["PositionScalarInterval", "Position2VecInterval",
			"Position3VecInterval"]),
	(_makeIntervalBuilder("velocityAs", dm.VelocityInterval, "spaceFrame", 
			tuplify=True),
		["VelocityScalarInterval", "Velocity2VecInterval",
			"Velocity3VecInterval"]),

	(_makeGeometryBuilder(dm.AllSky), ["AllSky", "AllSky2"]),
	(_makeGeometryBuilder(dm.Circle, _adaptCircleUnits), ["Circle", "Circle2"]),
	(_makeGeometryBuilder(dm.Ellipse, _adaptEllipseUnits), [
		"Ellipse", "Ellipse2"]),
	(_makeGeometryBuilder(dm.Box, _adaptBoxUnits), ["Box", "Box2"]),
	(_makeGeometryBuilder(dm.Polygon), ["Polygon", "Polygon2"]),
	(_makeGeometryBuilder(dm.Convex), ["Convex", "Convex2"]),
	(_makeCompoundBuilder(dm.Union), ["Union", "Union2"]),
	(_makeCompoundBuilder(dm.Intersection), ["Intersection", "Intersection2"]),
	(_makeCompoundBuilder(dm.Difference), ["Difference", "Difference2"]),
	(_makeCompoundBuilder(dm.Not), ["Negation", "Negation2"]),

	(_buildToplevel, ["ObservatoryLocation", "ObservationLocation",
		"STCResourceProfile", "STCSpec"]),
	(_passthrough, ["ObsDataLocation", "AstroCoords", "TimeInstant",
		"AstroCoordArea", "Position"]),
]


def _getHandlers():
	handlers = {
		_n("AstroCoordSystem"): _buildAstroCoordSystem,
		_n("PlanetaryEphem"): _buildPlanetaryEphem,
		_n("Error"): _makeKwFloatBuilder("error", units=_yieldErrUnits),
		_n("PixSize"): _makeKwFloatBuilder("pixSize", units=_yieldPSUnits),
		_n("Resolution"): _makeKwFloatBuilder("resolution", units=_yieldResUnits),
		_n("Size"): _makeKwFloatBuilder("size", units=_yieldSzUnits),

		_n("Redshift"): _makePositionBuilder('redshift', dm.RedshiftCoo, 
			"redshiftFrame"), 
		_n("Spectral"): _makePositionBuilder('freq', 
			dm.SpectralCoo, "spectralFrame"), 
		_n("StartTime"): _makeKwValueBuilder("lowerLimit"),
		_n("StopTime"): _makeKwValueBuilder("upperLimit"),
		_n("LoLimit"): _makeKwFloatBuilder("lowerLimit"),
		_n("HiLimit"): _makeKwFloatBuilder("upperLimit"),
		_n("Time"): _makePositionBuilder('time', dm.TimeCoo, "timeFrame"),
		_n("Timescale"): _makeKeywordBuilder("timeScale"),
		_n("TimeScale"): _makeKeywordBuilder("timeScale"),
		_n("Equinox"): _makeKeywordBuilder("equinox"),
		_n("Value"): _makeKwFloatBuilder("vals"),

		_n("Epoch"): _buildEpoch,
		_n("Radius"): _makeKwFloatBuilder("radius", multiple=False,
			units=_makeUnitYielder(("pos_unit",), "radius")),
		_n("Center"): _makeKwValueBuilder("center", tuplify=True,
			units=_makeUnitYielder(("unit",))), 
		_n("SemiMajorAxis"): _makeKwFloatBuilder("smajAxis", multiple=False,
			units=_makeUnitYielder(("pos_unit",), "smajAxis")),
		_n("SemiMinorAxis"): _makeKwFloatBuilder("sminAxis", multiple=False,
			units=_makeUnitYielder(("pos_unit",), "sminAxis")),
		_n("PosAngle"): _makeKwFloatBuilder("posAngle", multiple=False,
			units=_makeUnitYielder(("unit",), "posAngle")),
		_n("Vertex"): _makeKwValuesBuilder("vertices", tuplify=True), 
		_n("Vector"): _makeKwValueBuilder("vector", tuplify=True),
		_n("Offset"): _makeKwFloatBuilder("offset"),
		_n("Halfspace"): _buildHalfspace,
	
		_n('TimeFrame'): _makeFrameBuilder('timeFrame', dm.TimeFrame,
			timeScale="TT"),
		_n('SpaceFrame'): _makeFrameBuilder('spaceFrame', dm.SpaceFrame),
		_n('SpectralFrame'): _makeFrameBuilder('spectralFrame', dm.SpectralFrame),
		_n('RedshiftFrame'):  _makeFrameBuilder('redshiftFrame', dm.RedshiftFrame),


		_n("DopplerDefinition"): _makeKeywordBuilder("dopplerDef"),
		_n("TimeInterval"): _makeIntervalBuilder("timeAs", dm.TimeInterval,
			"timeFrame"),
		_n("SpectralInterval"): _makeIntervalBuilder("freqAs", 
			dm.SpectralInterval, "spectralFrame"),
		_n("RedshiftInterval"): _makeIntervalBuilder("redshiftAs", 
			dm.RedshiftInterval, "redshiftFrame"),
	}
	for builder, stcEls in _stcBuilders:
		for el in stcEls:
			handlers[_n(el)] = builder
	return handlers

getHandlers = utils.CachedGetter(_getHandlers)


def _getActiveTags():
	return {
		_n("AstroCoords"): CooSysActions(),
		_n("AstroCoordArea"): CooSysActions(),
		_n("Box"): BoxActions(),
		_n("Box2"): BoxActions(),
	}

getActiveTags = utils.CachedGetter(_getActiveTags)


def buildTree(csNode, context):
	"""traverses the ElementTree cst, trying handler functions for
	each node.

	The handler functions are taken from the context.elementHandler
	dictionary that maps QNames to callables.  These callables have
	the signature handle(STCNode, context) -> iterator, where the
	iterator returns key-value pairs for inclusion into the argument
	dictionaries for STCNodes.

	Unknown nodes are simply ignored.  If you need to bail out on certain
	nodes, raise explicit exceptions in handlers.
	"""
	resDict = {}

	# Elements with no handlers are ignored (add option to fail on these?)
	if context.getHandler(csNode.tag) is None:
		return

	if csNode.tag in context.activeTags:
		context.startTag(csNode)

	# collect constructor keywords from child nodes
	for child in csNode:
		for res in buildTree(child, context):
			if res is None:  # ignored child
				continue
			k, v = res
			if isinstance(v, (tuple, list)):
				resDict[k] = resDict.get(k, ())+v
			else:
				if k in resDict:
					raise common.STCInternalError("Attempt to overwrite key '%s', old"
						" value %s, new value %s (this should probably have been"
						" a tuple)"%(k, resDict[k], v))
				resDict[k] = v
	
	# collect constructor keywords from this node's handler
	for res in context.getHandler(csNode.tag)(csNode, resDict, context):
		yield res

	if csNode.tag in context.activeTags:
		context.endTag(csNode)


def parseFromETree(eTree):
	"""returns a sequence of pairs (root element, AST) for eTree containing
	parsed STC-X.
	"""
	context = STCXContext(elementHandlers=getHandlers(),
		activeTags=getActiveTags())
	parsed = dict(buildTree(eTree, context))
	if "stcSpec" not in parsed:
		raise common.STCXBadError("No STC-X found in or below %r"%eTree)
	forest = parsed["stcSpec"]
	resolveProxies(forest)
	return [(rootTag, ast.polish()) for rootTag, ast in forest]


def parseSTCX(stcxLiteral):
	"""returns a sequence of pairs (root element, AST) for the STC-X
	specifications in stcxLiteral.
	"""
	return parseFromETree(utils.ElementTree.fromstring(stcxLiteral))
