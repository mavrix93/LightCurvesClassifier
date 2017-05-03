"""
Definition of the structure of the internal representation (the AST).

For now, we want to be able to capture what STC-S can do (and a bit more).  
This means that we do not support generic coordinates (yet), elements,
xlink and all the other stuff.
"""

#c Copyright 2008-2016, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import itertools
import operator
import re

from gavo import utils
from gavo.stc import times
from gavo.stc import units
from gavo.stc import common
from gavo.utils import pgsphere


################ Coordinate Systems


class RefPos(common.ASTNode):
	"""is a reference position.

	Right now, this is just a wrapper for a RefPos id, as defined by STC-S,
	or None for Unknown.
	"""
# If we ever support non-standard origins, they should go into a different
# class, I guess.  Or, we'd need a sentinel for standardOrigin (like,
# NONSTANDARD).  None, anyway, is for Unknown, and we shouldn't change that.
	_a_standardOrigin = None
	_a_planetaryEphemeris = None


NullRefPos = RefPos()

class _CoordFrame(common.ASTNode):
	"""is an astronomical coordinate frame.
	"""
	_a_name = None
	_a_refPos = None

	def _setupNode(self):
		if self.refPos is None:
			self.refPos = NullRefPos

	def isSpherical(self):
		"""returns True if this is a frame deemed suitable for space
		frame transformations.

		This is really a property of stc.sphermath rather than of the
		data model, but it's more convenient to have this as a frame
		method.
		"""
		return (isinstance(self, SpaceFrame)
			and self.nDim>1
			and self.flavor=="SPHERICAL")


class TimeFrame(_CoordFrame):
	nDim = 1
	_a_timeScale = None


class SpaceFrame(_CoordFrame):
	_a_flavor = "SPHERICAL"
	_a_nDim = None
	_a_refFrame = None
	_a_equinox = None  # if non-null, it has to match [BJ][0-9]+[.][0-9]+

	def _setupNode(self):
		if self.refFrame=="J2000":
			self.refFrame = "FK5"
			self.equinox = "J2000.0"
		elif self.refFrame=="B1950":
			self.refFrame = "FK4"
			self.equinox = "B1950.0"
		if self.nDim is None:
			self.nDim = 2
		_CoordFrame._setupNode(self)

	def getEquinox(self):
		"""returns a datetime.datetime instance for the frame's equinox.

		It will return None if no equinox is given, and it may raise an
		STCValueError if an invalid equinox string has been set.
		"""
		if self.equinox is None:
			return None
		mat = re.match("([B|J])([0-9.]+)", self.equinox)
		if not mat:
			raise common.STCValueError("Equinoxes must be [BJ]<float>, but %s isn't"%(
				self.equinox))
		if mat.group(1)=='B':
			return times.bYearToDateTime(float(mat.group(2)))
		else:
			return times.jYearToDateTime(float(mat.group(2)))

	def asTriple(self):
		"""returns a triple defining the space frame for spherc's purposes.

		This is for the computation of coordinate transforms.  Since we only
		do coordinate transforms for spherical coordinate systems, this
		will, for now, raise STCValueErrors if everything but 2 or 3D SPHERICAL 
		flavours.  The other cases need more thought anyway.
		"""
		if self.flavor!="SPHERICAL" or (self.nDim!=2 and self.nDim!=3):
			raise common.STCValueError("Can only conform 2/3-spherical coordinates")
		return (self.refFrame, self.getEquinox(), self.refPos.standardOrigin)


class SpectralFrame(_CoordFrame):
	nDim = 1


class RedshiftFrame(_CoordFrame):
	nDim = 1
	_a_dopplerDef = None
	_a_type = None


class CoordSys(common.ASTNode):
	"""is an astronomical coordinate system.
	"""
	_a_timeFrame = None
	_a_spaceFrame = None
	_a_spectralFrame = None
	_a_redshiftFrame = None
	_a_name = None
	_a_libraryId = None   # for standard coordinate systems, the ivo://whatever.


class _CooTypeSentinel(object):
	"""is a base for type indicators.

	Never instantiate any of these.
	"""

class SpectralType(_CooTypeSentinel):
	posAttr = "freq"

class TimeType(_CooTypeSentinel):
	posAttr = "time"

class SpaceType(_CooTypeSentinel):
	posAttr = "place"

class RedshiftType(_CooTypeSentinel):
	posAttr = "redshift"

class VelocityType(_CooTypeSentinel):
	posAttr = "velocity"


############### Coordinates and their intervals


class _WiggleSpec(common.ASTNode):
	"""A base for "wiggle" specifications.

	These are Errors, Resolutions, Sizes, and PixSizes.  They may come
	as simple coordinates (i.e., scalars or vectors) or, in 2 and 3D,
	as radii or matrices (see below).  In all cases, two values may
	be given to indicate ranges.

	These need an adaptValuesWith(converter) method that will return a wiggle of
	the same type but with every value replaced with the result of the
	application of converter to that value.
	"""


class CooWiggle(_WiggleSpec):
	"""A wiggle given in coordinates.

	The values attributes stores them just like coordinates are stored.
	"""
	_a_values = ()
	_a_origUnit = None

	inexactAttrs = set(["values"])

	def adaptValuesWith(self, unitConverter):
		if unitConverter is None:
			return self
		return self.change(values=tuple(unitConverter(v) for v in self.values))

	def getValues(self):
		return self.values


class RadiusWiggle(_WiggleSpec):
	"""An wiggle given as a radius.

	If unit adaption is necessary and the base value is a vector, the radii
	are assumed to be of the dimension of the first vector component.
	"""
	_a_radii = ()
	_a_origUnit = None

	inexactAttrs = set(["radii"])

	def adaptValuesWith(self, unitConverter):
		if unitConverter is None:
			return self
		return self.change(radii=tuple(unitConverter(itertools.repeat(r))[0] 
			for r in self.radii))
	
	def getValues(self):
		return self.radii


class MatrixWiggle(_WiggleSpec):
	"""A matrix for specifying wiggle.

	The matrix/matrices are stored as sequences of sequences; see 
	stcxgen._wrapMatrix for details.
	"""
	_a_matrices = ()
	_a_origUnit = None

	def adaptValuesWith(self, unitConverter):
		raise common.STCValueError("Matrix wiggles cannot be transformed.")


class _CoordinateLike(common.ASTNode):
	"""An abstract base for everything that has a frame.

	They can return a position object of the proper type and with the
	same unit as self.

	When deriving from _CoordinateLike, you have at some point to define
	a cType class attribute that has values in the _CooTypeSentinels above.
	"""
	_a_frame = None
	_a_name = None

	def getPosition(self, initArgs=None):
		"""returns a position appropriate for this class.

		This is a shallow copy of the xCoo object itself for xCoos, 
		xCoo for xInterval, and SpaceCoo for Geometries.  Common attributes
		are copied to the new object.
		"""
		posClass = _positionClassMap[self.cType]
		if initArgs is None:
			initArgs = {}
		for name, default in posClass._nodeAttrs:
			if name!="id" and name not in initArgs:
				initArgs[name] = getattr(self, name, default)
		return posClass(**initArgs)


class _Coordinate(_CoordinateLike):
	"""An abstract base for coordinates.

	They have an iterTransformed(convFunc) method iterating over
	constructor keys that have to be changed when some convFunc is
	applied to the coordinate.  These may be multiple values when,
	e.g., errors are given or for geometries.

	Since these only make sense together with units, some elementary
	unit handling is required.  Since we keep the basic unit model
	of STC, this is a bit over-complicated.

	First, for the benefit of STC-S, a method getUnitString() ->
	string or None is required.  It should return an STC-S-legal
	unit string.

	Second, a method getUnitArgs() -> dict or None is required.
	It has to return a dictionary with all unit-related constructor
	arguments (that's unit and velTimeUnit for the standard coordinate
	types).  No None values are allowed; if self's units are not
	defined, return None.

	Third, a method getUnitConverter(otherUnits) -> function or None is required.
	OtherUnits can be a tuple or a result of getUnitArgs.  The tuple is
	interpreted as (baseUnit, timeUnit).  The function returned must
	accept self's coordinate values in otherUnit and return them in self's
	unit(s).  This is the function that iterTransformed requires.
	"""
	_a_error = None
	_a_resolution = None
	_a_pixSize = None
	_a_value = None
	_a_size = None

	_dimensionedAttrs = ["error", "resolution", "pixSize", "size"]

	inexactAttrs = set(["value"])

	def _setupNode(self):
		for name in self._dimensionedAttrs:
			wiggle = getattr(self, name)
			if wiggle and wiggle.origUnit is not None:
				setattr(self, name, wiggle.adaptValuesWith(
					self.getUnitConverter(wiggle.origUnit)))
		self._setupNodeNext(_Coordinate)

	def iterTransformed(self, converter):
		if self.value is not None:
			yield "value", converter(self.value)
		for attName in self._dimensionedAttrs:
			wiggle = getattr(self, attName)
			if wiggle:
				yield attName, wiggle.adaptValuesWith(converter)

		
class _OneDMixin(object):
	"""provides attributes for 1D-Coordinates (Time, Spectral, Redshift)
	"""
	_a_unit = None

	def getUnitString(self):
		return self.unit

	def getUnitConverter(self, otherUnits):
		if self.unit is None or not otherUnits:
			return None
		if isinstance(otherUnits, dict):
			otherUnits = (otherUnits["unit"],)
		return units.getBasicConverter(self.unit, otherUnits[0], True)

	def getUnitArgs(self):
		if self.unit:
			return {"unit": self.unit}

	def getValues(self):
		return [self.value]


class _SpatialMixin(object):
	"""provides attributes for positional coordinates.

	In addition to unit management, this is also carries an epoch in years.
	You can, in addition, set yearDef.  If None, Julian years are implied,
	but you can have B for Bessel years.
	"""
	_a_unit = ()
	_a_epoch = None
	_a_yearDef = None

	cType = SpaceType

	def getUnitString(self):
		if self.unit:
			if len(set(self.unit))==1:
				return self.unit[0]
			else:
				return " ".join(self.unit)

	def getUnitConverter(self, otherUnits):
		if self.unit is None or not otherUnits:
			return None
		if isinstance(otherUnits, dict):
			otherUnits = (otherUnits["unit"],)
		f = units.getVectorConverter(self.unit, otherUnits[0], True)
		return f

	def getUnitArgs(self):
		return {"unit": self.unit}

	def getValues(self):
		if self.value is None:
			return []
		return self.value


class _VelocityMixin(object):
	"""provides attributes for velocities.
	"""
	_a_unit = ()
	_a_velTimeUnit = ()
	_a_epoch = None
	_a_yearDef = None

	cType = VelocityType

	def _setupNode(self):
		if self.unit:
			if not self.velTimeUnit or len(self.unit)!=len(self.velTimeUnit):
				raise common.STCValueError("Invalid units for Velocity: %s/%s."%(
					repr(self.unit), repr(self.velTimeUnit)))
		self._setupNodeNext(_VelocityMixin)

	def getUnitString(self):
		if self.unit:
			strs = ["%s/%s"%(u, tu) 
				for u, tu in itertools.izip(self.unit, self.velTimeUnit)]
			if len(set(strs))==1:
				return strs[0]
			else:
				return " ".join(strs)

	def getUnitConverter(self, otherUnits):
		if self.unit is None or not otherUnits:
			return None
		if isinstance(otherUnits, dict):
			otherUnits = (otherUnits["unit"], otherUnits["velTimeUnit"])
		return units.getVelocityConverter(self.unit, self.velTimeUnit,
			otherUnits[0], otherUnits[1], True)

	def getUnitArgs(self):
		return {"unit": self.unit, "velTimeUnit": self.velTimeUnit}


class _RedshiftMixin(object):
	"""provides attributes for redshifts.
	"""
	_a_velTimeUnit = None
	_a_unit = None

	cType = RedshiftType

	def _setupNode(self):
		if self.unit and not self.velTimeUnit:
			raise common.STCValueError("Invalid units for Redshift: %s/%s."%(
				repr(self.unit), repr(self.velTimeUnit)))
		self._setupNodeNext(_RedshiftMixin)

	def getUnitString(self):
		if self.unit:
			return "%s/%s"%(self.unit, self.velTimeUnit)

	def getUnitConverter(self, otherUnits):
		if self.unit is None or not otherUnits:
			return None
		if isinstance(otherUnits, dict):
			otherUnits = (otherUnits["unit"], otherUnits["velTimeUnit"])
		return units.getRedshiftConverter(self.unit, self.velTimeUnit, 
			otherUnits[0], otherUnits[1], True)

	def getUnitArgs(self):
		return {"unit": self.unit, "velTimeUnit": self.velTimeUnit}


class SpaceCoo(_Coordinate, _SpatialMixin):
	pgClass = pgsphere.SPoint

class VelocityCoo(_Coordinate, _VelocityMixin): pass
class RedshiftCoo(_Coordinate, _RedshiftMixin): pass

class TimeCoo(_Coordinate, _OneDMixin):
	cType = TimeType

class SpectralCoo(_Coordinate, _OneDMixin):
	cType = SpectralType


_positionClassMap = {
	SpectralType: SpectralCoo,
	TimeType: TimeCoo,
	SpaceType: SpaceCoo,
	RedshiftType: RedshiftCoo,
	VelocityType: VelocityCoo,
}


class _CoordinateInterval(_CoordinateLike):
	_a_lowerLimit = None
	_a_upperLimit = None
	_a_fillFactor = None
	_a_origUnit = None
	
	inexactAttrs = set(["lowerLimit", "upperLimit"])

	def adaptValuesWith(self, converter):
		changes = {"origUnit": None}
		if self.lowerLimit is not None:
			changes["lowerLimit"] = converter(self.lowerLimit)
		if self.upperLimit is not None:
			changes["upperLimit"] = converter(self.upperLimit)
		return self.change(**changes)

	def getTransformed(self, sTrafo, destFrame):
		ll, ul = self.lowerLimit, self.upperLimit
		if ll is None:
			return self.change(upperLimit=sTrafo(ul), frame=destFrame)
		elif ul is None:
			return self.change(lowerLimit=sTrafo(ll), frame=destFrame)
		else:
			return self.change(upperLimit=sTrafo(ul), lowerLimit=sTrafo(ll), 
				frame=destFrame)


	def getValues(self):
		return [l for l in (self.lowerLimit, self.upperLimit) if l is not None]

class SpaceInterval(_CoordinateInterval):
	cType = SpaceType

	# See fromPgSphere docstring on this
	pgClass = pgsphere.SBox

	def getValues(self):
		return reduce(lambda a,b: a+b, _CoordinateInterval.getValues(self))
	
	def getTransformed(self, sTrafo, destFrame):
		# for n-d coordinates, upper and lower limit can be difficult
		# under rotations.  We need to look into this (>2 would need separate
		# support)
		ll, ul = self.lowerLimit, self.upperLimit
		if (self.frame.nDim==1
				or (self.lowerLimit is None or self.upperLimit is None)):
			return _CoordinateInterval.getTransformed(self, sTrafo, destFrame)
		elif self.frame.nDim==2:
			vertices = [sTrafo(coo) for coo in (
				(ll[0], ll[1]), (ul[0], ll[1]), (ll[0], ul[1]), (ul[0], ul[1]))]
			xVals = [coo[0] for coo in vertices]
			yVals = [coo[1] for coo in vertices]
			return self.change(upperLimit=(max(xVals), max(yVals)),
				lowerLimit=(min(xVals), min(yVals)), frame=destFrame)
		else:
			raise NotImplemented("Cannot yet transform coordinate intervals"
				" in n>2 dims.")

	@classmethod
	def fromPg(cls, frame, pgBox):
		return cls(frame=frame,
			lowerLimit=(pgBox.corner1.x/utils.DEG, pgBox.corner1.y/utils.DEG),
			upperLimit=(pgBox.corner2.x/utils.DEG, pgBox.corner2.y/utils.DEG))


# Service for stcsast -- this may go away again
PositionInterval = SpaceInterval


class VelocityInterval(_CoordinateInterval):
	cType = VelocityType

class RedshiftInterval(_CoordinateInterval):
	cType = RedshiftType

class TimeInterval(_CoordinateInterval):
	cType = TimeType

	def adaptValuesWith(self, converter):
		# timeIntervals are unitless; units only refer to errors, etc,
		# which we don't have here.
		return self


class SpectralInterval(_CoordinateInterval):
	cType = SpectralType



################ Geometries

class _Geometry(_CoordinateLike):
	"""A base class for all kinds of geometries.

	Geometries may have "dependent" quantities like radii, sizes, etc.  For
	those, the convention is that if they are 1D, they must be expressed in the
	unit  of the first component of the position units, otherwise (in particular,
	for box size) in the full unit of the position.  This has to be made sure by
	the client.

	To make this work, Geometries are unit adapted on STC adoption.
	Since their dependents need to be adapted as well, they have to
	define adaptDependents(...) methods.  They take the units for
	all dependent quantities (which may all be None).  This is used
	in stxast.

	Also getTransformed usually needs to be overridden for these.

	Geometries may contain two sorts of column references; ordinary ones
	are just stand-ins of actual values, while GeometryColRefs describe the
	whole thing in a database column.
	"""
	_a_size = None
	_a_fillFactor = None
	_a_origUnit = None
	_a_geoColRef = None

	cType = SpaceType

	def getValues(self):
		if self.geoColRef:
			return [self.geoColRef]
		else:
			return self._getValuesSplit()


class AllSky(_Geometry):
	def getTransformed(self, sTrafo, destFrame):
		return self.change(frame=destFrame)

	def adaptValuesWith(self, converter):
		return self

	def adaptDepUnits(self):
		pass

	def _getValuesSplit(self):
		return []
	

class Circle(_Geometry):
	_a_center = None
	_a_radius = None

	pgClass = pgsphere.SCircle

	def getTransformed(self, sTrafo, destFrame):
		return self.change(center=sTrafo(self.center), frame=destFrame)

	def adaptValuesWith(self, converter):
		sTrafo = units.getBasicConverter(converter.fromUnit[0], 
			converter.toUnit[0])
		return self.change(center=converter(self.center), 
			radius=sTrafo(self.radius))

	def _getValuesSplit(self):
		return [self.center[0], self.center[1], self.radius]

	@classmethod
	def fromPg(cls, frame, sCircle):
		return cls(frame=frame,
			center=(sCircle.center.x/utils.DEG, sCircle.center.y/utils.DEG),
			radius=(sCircle.radius/utils.DEG))


class Ellipse(_Geometry):
	_a_center = None
	_a_smajAxis = _a_sminAxis = None
	_a_posAngle = None

	def getTransformed(self, sTrafo, destFrame):
# XXX TODO: actually rotate the ellipse.
		return self.change(center=sTrafo(self.center), frame=destFrame)

	def adaptValuesWith(self, converter):
		sTrafo = units.getBasicConverter(converter.fromUnit[0], 
			converter.toUnit[0])
		return self.change(center=converter(self.center), 
			smajAxis=sTrafo(self.smajAxis), sminAxis=sTrafo(self.sminAxis))

	def _getValuesSplit(self):
		return list(self.center)+[self.smajAxis]+[self.sminAxis]+[
			self.posAngle]


class Box(_Geometry):
	_a_center = None
	_a_boxsize = None

	def getTransformed(self, sTrafo, destFrame):
		"""returns a Polygon corresponding to this Box after rotation.
		"""
		center, boxsize = self.center, self.boxsize
		return Polygon(vertices=tuple(sTrafo(coo) for coo in (
			(center[0]-boxsize[0], center[1]-boxsize[1]),
			(center[0]-boxsize[0], center[1]+boxsize[1]),
			(center[0]+boxsize[0], center[1]+boxsize[1]),
			(center[0]+boxsize[0], center[1]-boxsize[1]))), frame=destFrame)

	def adaptValuesWith(self, converter):
		return self.change(center=converter(self.center), 
			boxsize=converter(self.boxsize))

	def _getValuesSplit(self):
		return list(self.center)+list(self.boxsize)


class Polygon(_Geometry):
	_a_vertices = ()

	pgClass = pgsphere.SPoly

	def getTransformed(self, sTrafo, destFrame):
		return self.change(vertices=tuple(sTrafo(v) for v in self.vertices), 
			frame=destFrame)

	def adaptValuesWith(self, converter):
		return self.change(vertices=tuple(converter(v) for v in self.vertices))

	def _getValuesSplit(self):
		return reduce(operator.add, self.vertices)

	@classmethod
	def fromPg(cls, frame, sPoly):
		return cls(frame=frame,
			vertices=[(p.x/utils.DEG, p.y/utils.DEG) 
				for p in sPoly.points])


class Convex(_Geometry):
	_a_vectors = ()

	def getTransformed(self, sTrafo, destFrame):
		raise common.STCNotImplementedError("Cannot transform convexes yet.")

	def adaptValuesWith(self, converter):
		raise common.STCNotImplementedError("Cannot adapt units for convexes yet.")

	def _getValuesSplit(self):
		return reduce(operator.add, self.vectors)


class _Compound(_Geometry):
	"""A set-like operator on geometries.
	"""
	_a_children = ()

	def polish(self):
		for node in self.children:
			if node.frame is None:
				node.frame = self.frame
			getattr(node, "polish", lambda: None)()


	def adaptValuesWith(self, converter):
		return self.change(children=[child.adaptValuesWith(converter)
			for child in self.children])

	def _applyToChildren(self, function):
		newChildren, changes = [], False
		for c in self.children:
			nc = function(c)
			newChildren.append(nc)
			changes = changes or (c is not nc)
		if changes:
			return self.change(children=newChildren)
		else:
			return self

	def binarizeOperands(self):
		"""returns self with binarized operands.

		If no operand needed binarizing, self is returned.
		"""
		res = self._applyToChildren(binarizeCompound)
		return res

	def debinarizeOperands(self):
		"""returns self with debinarized operands.

		If no operand needed debinarizing, self is returned.
		"""
		return self._applyToChildren(debinarizeCompound)

	def getTransformed(self, sTrafo, destFrame):
		return self.change(children=tuple(
			child.getTransformed(sTrafo, destFrame) for child in self.children),
			frame=destFrame)


class _MultiOpCompound(_Compound):
	"""is a compound that has a variable number of operands.
	"""


class Union(_MultiOpCompound): pass
class Intersection(_MultiOpCompound): pass
class Difference(_Compound): pass
class Not(_Compound): pass


def _buildBinaryTree(compound, items):
	"""returns a binary tree of nested instances compound instances.

	items has to have at least length 2.
	"""
	items = list(items)
	root = compound.change(children=items[-2:])
	items[-2:] = []
	while items:
		root = compound.change(children=[items.pop(), root])
	return root


def binarizeCompound(compound):
	"""returns compound as a binary tree.

	For unions and intersections, compounds consisting of more than two
	operands will be split up into parts of two arguments each.
	"""
	if not isinstance(compound, _Compound):
		return compound
	compound = compound.binarizeOperands()
	if len(compound.children)==1:
		return compound.children[0]
	elif len(compound.children)==2:
		return compound
	else:
		newChildren = [compound.children[0], 
			_buildBinaryTree(compound, compound.children[1:])]
		return compound.change(children=newChildren)


def debinarizeCompound(compound):
	"""returns compound with flattened operators.
	"""
	if not isinstance(compound, _Compound):
		return compound
	compound = compound.debinarizeOperands()
	newChildren, changes = [], False
	for c in compound.children:
		if c.__class__==compound.__class__:
			newChildren.extend(c.children)
			changes = True
		else:
			newChildren.append(c)
	if changes:
		return compound.change(children=newChildren)
	else:
		return compound


################ Toplevel

class STCSpec(common.ASTNode):
	"""is an STC specification, i.e., the root of an STC tree.
	"""
	_a_astroSystem = None
	_a_systems = ()
	_a_time = None
	_a_place = None
	_a_freq = None
	_a_redshift = None
	_a_velocity = None
	_a_timeAs = ()
	_a_areas = ()
	_a_freqAs = ()
	_a_redshiftAs = ()
	_a_velocityAs = ()

	@property
	def sys(self):
		return self.astroSystem

	def buildIdMap(self):
		if hasattr(self, "idMap"):
			return
		self.idMap = {}
		for node in self.iterNodes():
			if node.id:
				self.idMap[node.id] = node

	def polish(self):
		"""does global fixups when parsing is finished.

		This method has to be called after the element is complete.  The
		standard parsers do this.

		For convenience, it returns the instance itself.
		"""
		# Fix local frames if not given (e.g., manual construction)
		if self.place is not None and self.place.frame is None:
			self.place.frame = self.astroSystem.spaceFrame
		for area in self.areas:
			if area.frame is None:
				area.frame = self.astroSystem.spaceFrame
			getattr(area, "polish", lambda: None)()

# Operations here cannot be in a _setupNode since when parsing from
# XML, there may be IdProxies instead of real objects.
		# Equinox for ecliptic defaults to observation time
		if self.place:
			frame = self.place.frame
			if frame and frame.equinox is None and frame.refFrame=="ECLIPTIC":
				if self.time and self.time.value:
					frame.equinox = "J%.8f"%(times.dateTimeToJYear(self.time.value))
		return self

	def _applyToAreas(self, function):
		newAreas, changes = [], False
		for a in self.areas:
			na = function(a)
			changes = changes or na is not a
			newAreas.append(na)
		if changes:
			return self.change(areas=newAreas)
		else:
			return self

	def binarize(self):
		"""returns self with any compound present brought to a binary tree.

		This will return self if nothing needs to change.
		"""
		return self._applyToAreas(binarizeCompound)

	def debinarize(self):
		"""returns self with any compound present brought to a binary tree.

		This will return self if nothing needs to change.
		"""
		return self._applyToAreas(debinarizeCompound)
	
	def getColRefs(self):
		"""returns a list of column references embedded in this AST.
		"""
		if not hasattr(self, "_colRefs"):
			self._colRefs = []
			for n in self.iterNodes():
				if hasattr(n, "getValues"):
					self._colRefs.extend(
						v.dest for v in n.getValues() if isinstance(v, common.ColRef))
		return self._colRefs
	
	def stripUnits(self):
		"""removes all unit specifications from this AST.

		This is intended for non-standalone STC, e.g., in VOTables, where
		external unit specifications are present.  Removing the units
		prevents "bleeding out" of conflicting in-STC specifications
		(that mostly enter through defaulting).

		This ignores the immutability of nodes and is in general a major pain.
		"""
		for node in self.iterNodes():
			if hasattr(node, "unit"):
				node.unit = node.__class__._a_unit
			if hasattr(node, "velTimeUnit"):
				node.velTimeUnit = node.__class__._a_unit


def fromPgSphere(refFrame, pgGeom):
	"""Returns an AST for a pgsphere object as defined in utils.pgsphere.

	This interprets the pgSphere box as a coordinate interval, which is wrong
	but probably what most VO protocols expect.
	"""
	frame = SpaceFrame(refFrame=refFrame)

	if isinstance(pgGeom, SpaceCoo.pgClass):
		return STCSpec(place=SpaceCoo.fromPg(frame, pgGeom))

	for stcGeo in [Circle, SpaceInterval, Polygon]:
		if isinstance(pgGeom, stcGeo.pgClass):
			return STCSpec(areas=[stcGeo.fromPg(frame, pgGeom)])
	
	raise common.STCValueError("Unknown pgSphere object %r"%pgGeom)
