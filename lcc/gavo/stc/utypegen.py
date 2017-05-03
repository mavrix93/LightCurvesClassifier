"""
Generating a utype/value sequence for ASTs.

Yet another insane serialization for an insane data model.  Sigh.

The way we come up with the STC utypes here is described in an IVOA note.

Since the utypes are basically xpaths into STC-X, there is not terribly
much we need to do here.  However, due to STC-X being a nightmare,
certain rules need to be formulated what utypes to generate.

Here, we use UtypeMakers for this.  There's a default UtypeMaker
that implements the basic algorithm of the STC note (in iterUtypes,
a method that yields all utype/value pairs for an STC-X node, which
is a stanxml Element).

To customize what is being generated, define _gener_<child name>
methods, where <child name> is a key within the dictionaries
returned by stanxml.Element's getChildDict method.

To make the definition of the _gener_ methods easer, there's
the handles decorator that you can pass a list of such child names.
"""

#c Copyright 2008-2016, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from gavo import utils
from gavo.stc import common
from gavo.stc import stcxgen
from gavo.stc.stcx import STC


#################### utype maker definition

def handles(seq):
	"""is a decorator for UtypeMaker methods.

	It adds a "handles" attribute as evaluated by AutoUtypeMaker.
	"""
	def deco(meth):
		meth.handles = seq
		return meth
	return deco


class UtypeMaker_t(type):
	"""A metaclass to facilite easy definition of UtypeMakers.

	This metaclass primarily operates on the handles hints left by the
	decorator.
	"""
	def __init__(cls, name, bases, dict):
		type.__init__(cls, name, bases, dict)
		cls._createHandlesMethods(dict.values())
	
	def _createHandlesMethods(cls, items):
		for item in items:
			for name in getattr(item, "handles", ()):
				setattr(cls, "_gener_"+name, item)


class UtypeMaker(object):
	"""An object encapsulating information on how to turn a stanxml
	node into a sequence of utype/value pairs.

	This is an "universal" base, serving as a simple default.
	Any class handling specific node types must fill out at least
	the rootType attribute, giving the utype at which this UtypeMaker
	should kick in.

	By default, utype/value pairs are only returned for nonempty
	element content.  To change this, define _gener_<name>(node,
	prefix) -> iterator methods.

	The actual pairs are retrieved by calling iterUtypes(node,
	parentPrefix).
	"""
	__metaclass__ = UtypeMaker_t

	# attributes that don't get serialized to utypes per spec
	bannedAttributes = set("id frame_id coord_system_id unit"
		" pos_angle_unit pos_unit spectral_unit time_unit"
		" vel_time_unit gen_unit xsi:type ucd xmlns:stc xmlns xmlns:xsi"
		" xsi:schemaLocation".split())

	rootType = None

	def _generPlain(self, name, child, prefix):
		childType = utypejoin(prefix, name)
		maker = _getUtypeMaker(childType)
		for item in child:
			for pair in maker.iterUtypes(item, childType):
				yield pair

	def _gener__colRef(self, name, child, prefix):
		yield prefix, child[0]

	def iterUtypes(self, node, prefix):
		children = node.getChildDict()
		if node.text_:
			yield prefix, node.text_
		for attName, name in node.iterAttNames():
			if name not in self.bannedAttributes:
				val = getattr(node, attName)
				if val is not None:
					yield "%s.%s"%(prefix, name.split(":")[-1]), val
		for name, child in children.iteritems():
			handler = getattr(self, "_gener_"+name, self._generPlain)
			for pair in handler(name, child, prefix):
				yield pair


class _NotImplementedUtypeMaker(UtypeMaker):
	def _generPlain(self, name, child, prefix):
		raise common.STCNotImplementedError("Cannot create utypes for %s yet."%
			self.utypeFrag)


#################### utype specific makers


class _CoordFrameMaker(UtypeMaker):
	@handles(common.stcRefPositions)
	def _refPos(self, name, child, prefix):
		if name!='UNKNOWNRefPos':
			yield utypejoin(prefix, "ReferencePosition"), name
		for pair in self._generPlain("ReferencePosition", child, prefix):
			yield pair


class TimeFrameMaker(_CoordFrameMaker):
	rootType = "AstroCoordSystem.TimeFrame"
	@handles(common.stcTimeScales)
	def _timeScale(self, name, child, prefix):
		yield utypejoin(prefix, "TimeScale"), name


class SpaceFrameMaker(_CoordFrameMaker):
	rootType = "AstroCoordSystem.SpaceFrame"

	@handles(common.stcSpaceRefFrames)
	def _coordFrame(self, name, child, prefix):
		myPrefix = utypejoin(prefix, "CoordRefFrame")
		yield myPrefix, name
		for pair in self._generPlain(None, child, myPrefix):
			yield pair

	@handles(common.stcCoordFlavors)
	def _coordFlavor(self, name, child, prefix):
		prefix = utypejoin(prefix, "CoordFlavor")
		yield prefix, name
		if child:
			if child[0].coord_naxes!="2":
				yield utypejoin(prefix, "coord_naxes"), child[0].coord_naxes
			yield utypejoin(prefix, "handedness"), child[0].handedness


class RedshiftFrameMaker(_CoordFrameMaker):
	rootType = "AstroCoordSystem.RedshiftFrame"
	
	def iterUtypes(self, node, prefix):
		for pair in _CoordFrameMaker.iterUtypes(self, node, prefix):
			yield pair


class SpectralFrameMaker(_CoordFrameMaker):
	rootType = "AstroCoordSystem.SpectralFrame"


class _TimeValueMaker(UtypeMaker):
	@handles(["ISOTime", "JDTime", "MJDTime"])
	def _absoluteTime(self, name, child, prefix):
		yield utypejoin(prefix, "xtype"), name
		for item in child:
			for pair in self.iterUtypes(item, prefix):
				yield pair


class TimeInstantMaker(_TimeValueMaker):
	rootType = "AstroCoords.Time.TimeInstant"

class StartTimeMaker(_TimeValueMaker):
	rootType = "AstroCoordArea.TimeInterval.StartTime"

class StopTimeMaker(_TimeValueMaker):
	rootType = "AstroCoordArea.TimeInterval.StopTime"


#################### toplevel code

def utypejoin(*utypes):
	return ".".join(u for u in utypes if u)


# A resolver of element names to their handling classes.  For most
# elements, this is just a plain UtypeMaker.
_getUtypeMaker = utils.buildClassResolver(
	UtypeMaker, 
	globals().values(),
	default=UtypeMaker(),
	instances=True, 
	key=lambda obj:obj.rootType)


def getUtypes(ast, includeDMURI=False, suppressXtype=True):
	"""returns a lists of utype/value pairs for an STC AST.

	If you pass includeDMURI, a utype/value pair for the data model URI will
	be  generated in addition to what comes in from ast.
	"""
	cst = stcxgen.astToStan(ast, STC.STCSpec)
	utypes = []
	for utype, val in _getUtypeMaker("").iterUtypes(cst, ""):
		if val is None or val=='':
			continue
		if suppressXtype:
			if utype.endswith("xtype"):
				continue
		utypes.append(("stc:"+utype, val))
	if includeDMURI:
		utypes.append(("stc:DataModel.URI", common.STCNamespace))
	utypes.sort()
	return utypes
