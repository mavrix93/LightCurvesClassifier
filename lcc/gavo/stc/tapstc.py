"""
The subset of STC proposed by the TAP spec.

Use this rather than the full-blown STC library for TAP and friends.
TAP's semi-sanitation of STC needs some special handling anyway,
and this is much faster than the full-blown mess.
"""

#c Copyright 2008-2016, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from __future__ import with_statement

from gavo import utils
from gavo.stc import common
from gavo.stc import stcsast
from gavo.utils import pgsphere


TAP_SYSTEMS = set(
	['ICRS', 'FK4', 'FK5', 'GALACTIC', 'RELOCATABLE', 'UNKNOWN', '', "BROKEN",
		"UNKNOWNFrame"])

# universally ignored
TAP_REFPOS = set(
	['BARYCENTER', 'GEOCENTER', 'HELIOCENTER', 'LSR', 'TOPOCENTER',
		'RELOCATABLE', 'UNKNOWNREFPOS'])

# only SPHERICAL2 supported, all others raise errors
TAP_FLAVORS = set(
	["CARTESIAN2", "CARTESIAN3", "SPHERICAL2"])


################## transformations between TAP STC reference systems

UNIVERSALLY_COMPATIBLE = set(['RELOCATABLE', 'UNKNOWN', '', "BROKEN", None])

TRANSFORMS = {
# From "ICRS" (really, FK5 J2000, and the lo-prec) to...
	'FK4': (1.5651864333666516, -0.0048590552804904244, -1.5763681043529187),
	'FK5': None,
	'ICRS': None,
	'GALACTIC': (1.3463560974407338, -1.0973190018372752, 0.57477052472873258),
}


def _getEulersFor(frame):
	if not frame in TRANSFORMS:
		raise common.STCValueError("Unknown reference frame: %s"%frame)
	return TRANSFORMS[frame]


def getPGSphereTrafo(fromSys, toSys):
	"""returns a pgsphere expression fragment to turn a pgsphere geometry
	from fromSys to toSys.

	fromSys and toSys are system designations like for TAP.

	If the systems are "compatible" (i.e., no transformation is deemed necessary),
	None is returned.  A GeometryError is raised for incomprehensible system
	specifications.
	"""
	if (fromSys in UNIVERSALLY_COMPATIBLE
			or toSys in UNIVERSALLY_COMPATIBLE):
		return None
	if fromSys=='ICRS':
		template = "+strans(%f,%f,%f)"
		angles = _getEulersFor(toSys)
	elif toSys=='ICRS':
		angles = _getEulersFor(fromSys)
		template = "-strans(%f,%f,%f)"
	else:
		t1 = getPGSphereTrafo(fromSys, 'ICRS')
		t2 = getPGSphereTrafo('ICRS', toSys)
		return "%s%s"%(t1 or "", t2 or "")
	if angles:
		return template%angles
	return None


def getTAPSTC(stcInstance):
	"""returns a tap system identifier for an STC AstroSystem.

	This is stc.astroSystem.spaceFrame.refFrame if existing and 
	TAP-defined, UNKNOWN otherwise.
	"""
	rf = None
	if stcInstance.astroSystem and stcInstance.astroSystem.spaceFrame:
		rf = stcInstance.astroSystem.spaceFrame.refFrame
	if rf not in TAP_SYSTEMS:
		return "UNKNOWN"
	return rf


@utils.memoized
def getSTCForTAP(tapIdentifier):
	"""returns an stc AST for a tap reference system identifier.

	The tapIdentifier is any string in which the first item is the reference 
	system.  Everything else is ignored (this is because it seems someone
	intended additional specs like "BARYCENTER" to be legal, although
	there really is nothing we can do about them).
	"""
	if tapIdentifier:
		tapIdentifier = utils.identifierPattern.findall(tapIdentifier)[0]
	if tapIdentifier in ["BROKEN", '', "UNKNOWN"]:
		tapIdentifier = "UNKNOWNFrame"
	ast = stcsast.parseSTCS("Position %s"%tapIdentifier)
	if tapIdentifier=='BROKEN':
		ast.broken = True
	return ast



############################# TAP simplified STC-S
# The simplified STC-S is a simple regular grammar for the position specs
# plus a context-free part for set operations.  The regular part we
# do with REs, for the rest there's a simple recursive descent parser.
#
# From the literal we either create a pgsphere geometry ready for ingestion
# or, when operators enter, an GeomExpr object.  Since at least pgsphere
# does not support geometric operators, this must be handled in the morph code.
# To make this clear, its flatten method just raises an Exception.
#
# The regions expressible in pgsphere are returned as pgsphre objects.
# This is because I feel all this should only be used for ingesting data
# ("table upload") and thus carrying around the frame is pointless;
# you can, however, retrieve a guess for the frame from the returned
# object's cooSys attribute (which is convenient for the morphers).


class GeomExpr(object):
	"""a sentinel object to be processed by morphers.
	"""
	def __init__(self, frame, operator, operands):
		self.cooSys = frame
		self.operator, self.operands = operator.upper(), operands

	def flatten(self):
		raise common.STCSParseError("Cannot serialize STC-S.  Did you use"
			" Union or Intersection outside of CONTAINS or INTERSECTS?")

	def _flatLogic(self, template, operand):
		if isinstance(operand, GeomExpr):
			return operand.asLogic(template)
		else:
			return template%operand.asPgSphere()

	def asLogic(self, template):
		if self.operator=="UNION":
			logOp = " OR "
		elif self.operator=="INTERSECTION":
			logOp = " AND "
		elif self.operator=="NOT":
			return "NOT (%s)"%self._flatLogic(template, self.operands[0])
		else:
			raise NotImplementedError("No logic for operator '%s'"%self.operator)
		return logOp.join(
			'(%s)'%self._flatLogic(template, op) for op in self.operands)


def _make_pgsposition(coords):
	if len(coords)!=2:
		raise common.STCSParseError("STC-S points want two coordinates.")
	return pgsphere.SPoint(*coords)


def _make_pgscircle(coords):
	if len(coords)!=3:
		raise common.STCSParseError("STC-S circles want three numbers.")
	return pgsphere.SCircle(pgsphere.SPoint(*coords[:2]), coords[2])


def _make_pgsbox(coords):
	if len(coords)!=4:
		raise common.STCSParseError("STC-S boxes want four numbers.")
	x,y,w,h = coords
	return pgsphere.SPoly((
		pgsphere.SPoint(x-w/2, y-h/2),
		pgsphere.SPoint(x-w/2, y+h/2),
		pgsphere.SPoint(x+w/2, y+h/2),
		pgsphere.SPoint(x+w/2, y-h/2)))


def _make_pgspolygon(coords):
	if len(coords)<6 or len(coords)%2:
		raise common.STCSParseError(
			"STC-S polygons want at least three number pairs")
	return pgsphere.SPoly(
		[pgsphere.SPoint(*p) for p in utils.iterConsecutivePairs(coords)])


def _makePgSphereInstance(match):
	"""returns a utils.pgsphere instance from a match of simpleStatement in
	the simple STCS parser below.
	"""
	if match["flavor"] and match["flavor"].strip().upper()!="SPHERICAL2":
		raise common.STCSParseError("Only SPHERICAL2 STC-S supported here")
	refFrame = 'UnknownFrame'
	if match["frame"]:
		refFrame = match["frame"].strip()
	# refFrame gets thrown away here; to use it, we'd have to generate
	# ADQL nodes, and that would be clumsy for uploads.  See rant above.
	handler = globals()["_make_pgs%s"%match["shape"].lower()]
	res = handler(
		tuple(float(s)*utils.DEG for s in match["coords"].strip().split() if s))
	res.cooSys = refFrame
	return res

def _makeRE(strings):
	return "|".join(sorted(strings, key=lambda s: -len(s)))

@utils.memoized
def getSimpleSTCSParser():
	from gavo.imp.pyparsing import (
		Regex, CaselessKeyword, OneOrMore, Forward, Suppress,
		Optional, ParseException, ParseSyntaxException)

	with utils.pyparsingWhitechars(" \t\n\r"):
		frameRE = _makeRE(TAP_SYSTEMS)
		refposRE = _makeRE(TAP_REFPOS)
		flavorRE = _makeRE(TAP_FLAVORS)
		systemRE = (r"(?i)\s*"
			r"(?P<frame>%s)?\s*"
			r"(?P<refpos>%s)?\s*"
			r"(?P<flavor>%s)?\s*")%(
				frameRE, refposRE, flavorRE)
		coordsRE = r"(?P<coords>(%s\s*)+)"%utils.floatRE

		simpleStatement = Regex("(?i)\s*"
			"(?P<shape>position|circle|box|polygon)"
			+systemRE
			+coordsRE)
		simpleStatement.setName("STC-S geometry")
		simpleStatement.addParseAction(lambda s,p,t: _makePgSphereInstance(t))
		system = Regex(systemRE)
		system.setName("STC-S system spec")
		region = Forward()
		notExpr = CaselessKeyword("NOT") + Suppress('(') + region + Suppress(')')
		notExpr.addParseAction(lambda s,p,t: GeomExpr("UNKNOWN", "NOT", (t[1],)))
		opExpr = (
			(CaselessKeyword("UNION") | CaselessKeyword("INTERSECTION"))("op")
			+ Optional(Regex(frameRE))("frame") 
			+ Optional(Regex(refposRE)) + Optional(Regex(flavorRE))
			+ Suppress("(")
			+ region + OneOrMore(region)
			+ Suppress(")"))
		opExpr.addParseAction(
			lambda s,p,t: GeomExpr(str(t["frame"]), t[0].upper(), t[2:]))
		region << (simpleStatement | opExpr | notExpr)
		
	def parse(s):
		if s is None or not s.strip(): # special service: Null values
			return None
		if isinstance(s, pgsphere.PgSAdapter):
			return s

		try:
			res = utils.pyparseString(region, s, parseAll=True)[0]
			if not res.cooSys or res.cooSys.lower()=='unknownframe':  # Sigh.
				res.cooSys = "UNKNOWN"
			return res
		except (ParseException, ParseSyntaxException), msg:
			raise common.STCSParseError("Invalid STCS (%s)"%str(msg))

	return parse


parseSimpleSTCS = getSimpleSTCSParser()


def simpleSTCSToPolygon(stcsExpr):
	"""returns an spoly for an STC-S region specification.

	This is used to let people upload VOTables with REGION items.
	"""
	if stcsExpr is None:
		return None
	return parseSimpleSTCS(stcsExpr).asPoly()


if __name__=="__main__":
# compute the Euler angles given above.  pgsphere has its rotation
# matrices opposite to ours (ccw rather than cw), hence the negation
	from kapteyn import celestial
	from gavo.stc import sphermath
	print "FK4:", tuple(-a for a in 
		sphermath.getEulerAnglesFromMatrix(
			celestial.skymatrix("icrs", "fk4 B1950.0")[0]))
	print "GAL:", tuple(-a for a in 
		sphermath.getEulerAnglesFromMatrix(
			celestial.skymatrix("icrs", "galactic")[0]))

