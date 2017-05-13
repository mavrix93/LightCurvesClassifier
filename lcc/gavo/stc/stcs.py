"""
Parsing and generating STC-S

The general plan is to parse STC-S into some sort of tree (dictionaries
with list values, possibly containing more such dictionaries).  These
trees can then be processed into something roughly resembling the data
model, furnished with defaults, and processed by what essentially is
user code.

Extensions to what the note says:

	- After flavor, you can add an epoch using something like "Epoch J2000.0".
	- After the FK5, FK4 and ECLIPTIC frame specs, you can add an optional
		astroYear (Bnnnn, Jnnnn) designating a custom equinox.
	- There is a system subphrase that lets you specify a system from the
		STC library (without the ivo:// decoration).  It starts with System
		and is specifed last.  It will override all other system specifications.
	- If enabled, you can use identifiers in double quotes whereever values
		are allowed; this will generate column references.
	- After the reference position, you can optionally mention the planetary
		ephemeris used; currently, only JPL-DE200 and JPL-DE405 are allowed.
"""

#c Copyright 2008-2016, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from __future__ import with_statement


from gavo.imp.pyparsing import (
	Word, Literal, Optional, alphas, CaselessKeyword,
		ZeroOrMore, OneOrMore, StringEnd,
		Suppress, Forward, 
		Regex, alphanums,
		ParseException, ParseResults, 
		ParseSyntaxException)

from gavo import utils
from gavo.stc import common
from gavo.stc import stcsdefaults
from gavo.stc import times

class AComputedDefault(object):
	"""A sentinel for computed default values.
	"""
	pass


# STC-S spatial flavors, with dimensions and stc flavors
stcsFlavors = {
	"SPHER2": (2, "SPHERICAL"),
	"SPHER3": (3, "SPHERICAL"),
	"UNITSPHER": (3, "UNITSPHERE"),
	"CART1": (1, "CARTESIAN"),
	"CART2": (2, "CARTESIAN"),
	"CART3": (3, "CARTESIAN"),
}


spatialUnits = set(["deg", "arcmin", "arcsec", "m", "mm", "km", "AU", 
	"pc", "kpc", "Mpc", "rad"])
temporalUnits = set(["yr", "cy", "s", "d", "a"])
spectralUnits = set(["MHz", "GHz", "Hz", "Angstrom", "keV", "MeV", 
	"eV", "mm", "um", "nm", "m"])

def _assertGrammar(cond, msg, pos):
	if not cond:
		raise common.STCSParseError(msg, pos)


def _iterDictNode(node, path):
	"""does iterNode's work for dict nodes.
	"""
	for k, v in node.iteritems():
		if isinstance(v, list):
			subIter = _iterListNode(v, path+(k,))
		elif isinstance(v, dict):
			subIter = _iterDictNode(v, path+(k,))
		else:
			continue  # content does not contain a subtree
		for res in subIter:
			yield res
	yield path, node

def _iterListNode(node, path):
	"""does iterNode's work for list nodes.
	"""
	for subNode in node:
		if isinstance(subNode, dict):
			for res in _iterDictNode(subNode, path):
				yield res

def iterNodes(tree):
	"""traverses the concrete syntax tree in postorder, returning pairs of 
	paths and nodes.

	A node returned here is always a dictionary.  The path consists of the
	keys leading to the node in a tuple.
	"""
	if isinstance(tree, list):
		return _iterListNode(tree, ())
	elif isinstance(tree, dict):
		return _iterDictNode(tree, ())
	else:
		raise common.STCInternalError("Bad node in tree %s"%tree)


def addDefaults(tree):
	"""adds defaults for missing values for a concrete syntax tree.

	The tree is changed in place.  For details, see stcsdefaults.
	"""
	for path, node in iterNodes(tree):
		if path and path[-1] in stcsdefaults.defaultingFunctions:
			stcsdefaults.defaultingFunctions[path[-1]](node)
	return tree


def removeDefaults(tree):
	"""removes defaults from a concrete syntax tree.

	The tree is changed in place.  For details, see stcsdefaults.
	"""
	for path, node in iterNodes(tree):
		if path and path[-1] in stcsdefaults.undefaultingFunctions:
			stcsdefaults.undefaultingFunctions[path[-1]](node)
	return tree


def makeTree(parseResult):
	"""returns the pyparsing parseResult as a data structure consisting
	of simple python dicts and lists.

	The "tree" has two kinds of nodes: Dictionaries having lists as
	values, and lists containing (as a rule) literals or (for more deeply
	nested constructs, which are rare in STC-S) other dictionaries of
	this kind.

	A parse node becomes a dict node if it has named children.  The root
	always is a dict.

	Note that unnamed children of nodes becoming dicts will be lost in
	the result.
	"""
	if not len(parseResult):  # empty parse results become Nones
		res = None
	elif parseResult.keys():  # named children, generate a dict
		res = {}
		for k in parseResult.keys():
			v = parseResult[k]
			# discard empty branches
			if isinstance(v, ParseResults):
				v = makeTree(v)
			if v is not None:  # discard empty branches
				res[k] = v
	else:                     # no named children, generate a list
		if isinstance(parseResult[0], ParseResults):
			res = [makeTree(child) for child in parseResult]
		else:
			res = list(parseResult)
	return res


def _reFromKeys(iterable):
	"""returns a regular expression matching any of the strings in iterable.

	The trick is that the longest keys must come first.
	"""
	return "|".join(sorted(iterable, key=lambda x:-len(x)))


def _makeSymDict(locals, exportAll):
	"""returns a dictionary of pyparsing symbols defined in the locals.
	
	locals would be the value locals() as a rule.
	"""
	syms = dict((n, v) for n, v in locals.iteritems()
			if hasattr(v, "setName"))
	if not exportAll:
		syms = dict((n, v) for n, v in syms.iteritems()
			if not n.startswith("_"))
	return syms


def _stringifyBlank(s, p, t):
	"""a parse action joining items in parse results with blanks.
	"""
	return " ".join(t)

def _stringify(s, p, t):
	"""a parse action joining items in parse results.
	"""
	return "".join(t)

def _makeSingle(s, p, t):
	"""a parse action that returns the first item of the tokens.

	You typically want this when you know there's only one token, e.g.,
	on Disjunctions or such
	"""
	return t[0]


def _getSTCSGrammar(numberLiteral, timeLiteral, _exportAll=False,
		_addGeoReferences=False):
	"""returns a dictionary of symbols for a grammar parsing STC-S into
	a concrete syntax tree.

	numberLiteral and timeLiteral are pyparsing symbols for numbers and
	datetimes, respectively.

	_addGeoReferences lets you write quoted references to vectors
	(like Circle "center" 20.).
	"""
	with utils.pyparsingWhitechars("\n\t\r "):
	
		number = numberLiteral
		del numberLiteral

# units
		_unitOpener = Suppress( CaselessKeyword("unit") )
		_spaceUnitWord = Regex(_reFromKeys(spatialUnits))
		_timeUnitWord = Regex(_reFromKeys(temporalUnits))
		spaceUnit = _unitOpener - OneOrMore( _spaceUnitWord ).addParseAction(
			_stringifyBlank)("unit")
		timeUnit = _unitOpener - _timeUnitWord("unit")
		spectralUnit = _unitOpener - Regex(_reFromKeys(spectralUnits))("unit")
		redshiftUnit = _unitOpener - ( 
			(_spaceUnitWord + "/" + _timeUnitWord).addParseAction(_stringify) 
			| CaselessKeyword("nil") )("unit")
		velocityUnit = _unitOpener - (OneOrMore( 
			(_spaceUnitWord + "/" + _timeUnitWord).addParseAction(_stringify) 
			).addParseAction(_stringifyBlank))("unit")

# basic productions common to most STC-S subphrases
		astroYear = Regex("[BJ][0-9]+([.][0-9]*)?")
		fillfactor = (Suppress( CaselessKeyword("fillfactor") 
			) + number("fillfactor"))
		noEqFrame = (CaselessKeyword("J2000") 
			| CaselessKeyword("B1950") 
			| CaselessKeyword("ICRS") 
			| CaselessKeyword("GALACTIC") 
			| CaselessKeyword("GALACTIC_I") 
			| CaselessKeyword("GALACTIC_II") 
			| CaselessKeyword("SUPER_GALACTIC") 
			| CaselessKeyword("GEO_C") 
			| CaselessKeyword("GEO_D") 
			| CaselessKeyword("HPR") 
			| CaselessKeyword("HGS") 
			| CaselessKeyword("HGC") 
			| CaselessKeyword("HPC") 
			| CaselessKeyword("UNKNOWNFrame"))("frame")
		eqFrameName = (CaselessKeyword("FK5") 
			| CaselessKeyword("FK4") 
			| CaselessKeyword("ECLIPTIC"))("frame")
		eqFrame = eqFrameName + Optional( astroYear("equinox") )
		frame = eqFrame | noEqFrame
		plEphemeris = CaselessKeyword("JPL-DE200") | CaselessKeyword("JPL-DE405")
		refpos = ((Regex(_reFromKeys(common.stcRefPositions)))("refpos")
			+ Optional( plEphemeris("plEphemeris") ))
		flavor = (Regex(_reFromKeys(stcsFlavors)))("flavor")

# properties of coordinates
		error = Suppress( CaselessKeyword("Error") ) + OneOrMore( number )
		resolution = Suppress( CaselessKeyword("Resolution") 
			) + OneOrMore( number )
		size = Suppress( CaselessKeyword("Size") ) + OneOrMore(number)
		pixSize = Suppress( CaselessKeyword("PixSize") ) + OneOrMore(number)
		cooProps = (Optional( error("error") ) 
			+ Optional( resolution("resolution") ) 
			+ Optional( size("size") ) 
			+ Optional( pixSize("pixSize") ))

# properties of most spatial specs
		_coos = ZeroOrMore( number )("coos")
		_pos = Optional( ZeroOrMore( number )("pos") )
		if _addGeoReferences: # include references to vectors, for getColrefSymbols
			complexColRef = Regex('[[][A-Za-z_][A-Za-z_0-9]*[]]').addParseAction(
				lambda s,p,toks: common.GeometryColRef(toks[0][1:-1]))
			_coos = complexColRef("coos") | _coos
			_pos = complexColRef("pos") | _pos
		positionSpec = Suppress( CaselessKeyword("Position") ) + _pos
		epochSpec = Suppress( CaselessKeyword("Epoch") ) - astroYear
		_spatialProps = Optional( spaceUnit ) + cooProps
		velocitySpec = (CaselessKeyword("Velocity")("type")
			 + OneOrMore( number )("pos"))
		velocityInterval = (
			Optional(
				CaselessKeyword("VelocityInterval")("type") 
				+ Optional( fillfactor ) 
				+ _coos )
			+ Optional( velocitySpec ) 
			+ Optional( velocityUnit ) 
			+ cooProps).addParseAction(makeTree)
		_spatialTail = (_spatialProps + 
			Optional( velocityInterval)("velocity"))
		_regionTail = Optional( positionSpec ) + _spatialTail
		_commonSpaceItems = ( frame + Optional( refpos ) + 
			Optional( flavor ) + Optional( 
				epochSpec("epoch").addParseAction(_stringify) ))
		_commonRegionItems = Optional( fillfactor ) + _commonSpaceItems

# times and time intervals
		timescale = (Regex("|".join(common.stcTimeScales)))("timescale")
		timephrase = Suppress( CaselessKeyword("Time") ) + timeLiteral
		_commonTimeItems = Optional( timeUnit ) + cooProps
		_intervalOpener = ( Optional( fillfactor ) + 
			Optional( timescale("timescale") ) +
			Optional( refpos ) )
		_intervalCloser = Optional( timephrase("pos") ) + _commonTimeItems

		timeInterval =  (CaselessKeyword("TimeInterval")("type") + 
			_intervalOpener + ZeroOrMore( timeLiteral )("coos") + 
			_intervalCloser)
		startTime = (CaselessKeyword("StartTime")("type") + _intervalOpener + 
			timeLiteral.setResultsName("coos", True) + _intervalCloser)
		stopTime = (CaselessKeyword("StopTime")("type") + _intervalOpener + 
			timeLiteral.setResultsName("coos", True) + _intervalCloser)
		time = (CaselessKeyword("Time")("type")  + Optional( timescale("timescale") ) + 
			Optional( refpos ) + Optional(
				timeLiteral.setResultsName("pos", True) ) + _commonTimeItems)
		timeSubPhrase = (timeInterval 
			| startTime 
			| stopTime 
			| time).addParseAction(makeTree)

# atomic "geometries"; I do not bother to specify their actual
# arguments since, without knowing the frame, they may be basically
# anthing.   Also, I want to allow geometry column references.
		_atomicGeometryKey = ( CaselessKeyword("AllSky").setName("sub-geometry")
			| CaselessKeyword("Circle") 
			| CaselessKeyword("Ellipse") 
			| CaselessKeyword("Box") 
			| CaselessKeyword("Polygon") 
			| CaselessKeyword("Convex") 
			| CaselessKeyword("PositionInterval") )
		atomicGeometry = ( _atomicGeometryKey("type") 
			+ _commonRegionItems 
			+ _coos 
			+ _regionTail )

# compound "geometries"
		_compoundGeoExpression = Forward()
		_compoundGeoOperand  = (( _atomicGeometryKey("subtype") + _coos )
			| _compoundGeoExpression ).addParseAction(lambda s,p,t: dict(t))

		_compoundGeoOperatorUnary = CaselessKeyword("Not")
		_compoundGeoOperandsUnary =  ( Suppress( '(' ) 
			+ _compoundGeoOperand + Suppress( ')' ) )
		_compoundGeoExprUnary = ( _compoundGeoOperatorUnary("subtype")
			+ _compoundGeoOperandsUnary("children") )

		_compoundGeoOperatorBinary = CaselessKeyword("Difference")
		_compoundGeoOperandsBinary =  ( Suppress( '(' ) 
			+ _compoundGeoOperand + _compoundGeoOperand + Suppress( ')' ) )
		_compoundGeoExprBinary = ( _compoundGeoOperatorBinary("subtype")
			+ _compoundGeoOperandsBinary("children") )

		_compoundGeoOperatorNary = ( CaselessKeyword("Union") 
			| CaselessKeyword("Intersection") )
		_compoundGeoOperandsNary =  ( Suppress( '(' ) 
			+ _compoundGeoOperand + _compoundGeoOperand 
			+ ZeroOrMore( _compoundGeoOperand ) + Suppress( ')' ) )
		_compoundGeoExprNary = ( _compoundGeoOperatorNary("subtype")
			+ _compoundGeoOperandsNary("children") )

		_compoundGeoExpression << ( _compoundGeoExprUnary
			| _compoundGeoExprBinary
			| _compoundGeoExprNary )
		compoundGeoPhrase = ( _compoundGeoOperatorUnary("type") 
				+ _commonRegionItems 
				+ _compoundGeoOperandsUnary("children") + _regionTail 
			| _compoundGeoOperatorBinary("type") 
				+ _commonRegionItems 
				+ _compoundGeoOperandsBinary("children") + _regionTail 
			| _compoundGeoOperatorNary("type") 
				+ _commonRegionItems 
				- _compoundGeoOperandsNary("children") + _regionTail )

# space subphrase
		positionInterval = ( CaselessKeyword("PositionInterval")("type") 
			+ _commonRegionItems 
			+ _coos 
			+ _regionTail )
		position = ( CaselessKeyword("Position")("type") 
			+ _commonSpaceItems 
			+ _pos 
			+ _spatialTail )
		spaceSubPhrase = ( positionInterval 
			| position 
			| atomicGeometry 
			| compoundGeoPhrase ).addParseAction(makeTree)

# spectral subphrase
		spectralSpec = (Suppress( CaselessKeyword("Spectral") ) 
			+ number)("pos")
		_spectralTail = Optional( spectralUnit ) + cooProps
		spectralInterval = (CaselessKeyword("SpectralInterval")("type") 
			+ Optional( fillfactor ) 
			+ Optional( refpos ) 
			+ _coos 
			+ Optional( spectralSpec ) 
			+ _spectralTail)
		spectral = (CaselessKeyword("Spectral")("type") 
			+ Optional( refpos ) 
			+ _pos 
			+ _spectralTail)
		spectralSubPhrase = (spectralInterval | spectral ).addParseAction(
			makeTree)

# redshift subphrase
		redshiftType = Regex("VELOCITY|REDSHIFT")("redshiftType")
		redshiftSpec = (Suppress( CaselessKeyword("Redshift") ) + number)("pos")
		dopplerdef = Regex("OPTICAL|RADIO|RELATIVISTIC")("dopplerdef")
		_redshiftTail = Optional( redshiftUnit ) + cooProps
		redshiftInterval = (CaselessKeyword("RedshiftInterval")("type") 
			+ Optional( fillfactor ) 
			+ Optional( refpos ) 
			+ Optional( redshiftType ) 
			+ Optional( dopplerdef ) 
			+ _coos 
			+ Optional( redshiftSpec ) 
			+ _redshiftTail)
		redshift = (CaselessKeyword("Redshift")("type") 
			+ Optional( refpos ) 
			+ Optional( redshiftType ) 
			+ Optional( dopplerdef ) 
			+ _pos 
			+ _redshiftTail)
		redshiftSubPhrase = (redshiftInterval | redshift).addParseAction(
			makeTree)

# system subphrase (extension, see docs)
		# ids match Name from XML spec; we're not doing char refs and similar here
		xmlName = Word(alphas+"_:", alphanums+'.-_:').addParseAction(_stringify)
		systemDefinition = (Suppress( CaselessKeyword("System") ) 
			+ xmlName("libSystem"))
			

# top level
		stcsPhrase = ( #noflake: stcsPhrase is returned through locals()
			Optional( timeSubPhrase )("time") + 
			Optional( spaceSubPhrase )("space") +
			Optional( spectralSubPhrase )("spectral") +
			Optional( redshiftSubPhrase )("redshift") +
			Optional( systemDefinition ) ) + StringEnd()

		return _makeSymDict(locals(), _exportAll)


def getSymbols(_exportAll=False, _colrefLiteral=None,
		_addGeoReferences=False):
	"""returns an STC-S grammar with terminal values.
	"""
	with utils.pyparsingWhitechars("\n\t\r "):
		_exactNumericRE = r"[+-]?\d+(\.(\d+)?)?|[+-]?\.\d+"
		exactNumericLiteral = Regex(_exactNumericRE)
		numberLiteral = Regex(r"(?i)(%s)(E[+-]?\d+)?"%_exactNumericRE
			).addParseAction(lambda s,p,toks: float(toks[0]))

		jdLiteral = (Suppress( Literal("JD") ) + exactNumericLiteral
			).addParseAction(lambda s,p,toks: times.jdnToDateTime(float(toks[0])))
		mjdLiteral = (Suppress( Literal("MJD") ) + exactNumericLiteral
			).addParseAction(lambda s,p,toks: times.mjdToDateTime(float(toks[0])))
		isoTimeLiteral = Regex(r"\d\d\d\d-?\d\d-?\d\d(T\d\d:?\d\d:?\d\d(\.\d*)?Z?)?"
			).addParseAction(lambda s,p,toks: times.parseISODT(toks[0]))
		timeLiteral = (isoTimeLiteral | jdLiteral | mjdLiteral)

		if _colrefLiteral:
			numberLiteral = _colrefLiteral ^ numberLiteral
			timeLiteral = _colrefLiteral ^ timeLiteral

	res = _getSTCSGrammar(numberLiteral, timeLiteral, _exportAll,
		_addGeoReferences=_addGeoReferences)
	res.update(_makeSymDict(locals(), _exportAll))
	return res


def getColrefSymbols():
	"""returns an STC-S grammar with column references as values.

	The column references used here have the form "<colref>" to cut down
	on ambiguities.  We only accept simple identifiers (i.e., not quoted in
	the SQL sense), though.
	"""
	def makeColRef(s, p, toks):
		return common.ColRef(toks[0][1:-1])
	with utils.pyparsingWhitechars("\n\t\r "):
		atomicColRef = Regex('"[A-Za-z_][A-Za-z_0-9]*"').addParseAction(
			makeColRef)
	return getSymbols(_colrefLiteral=atomicColRef, _addGeoReferences=True)


def enableDebug(syms, debugNames=None):
	if not debugNames:
		debugNames = syms
	for name in debugNames:
		ob = syms[name]
		ob.setDebug(True)
		ob.setName(name)


getGrammar = utils.CachedGetter(getSymbols)
getColrefGrammar = utils.CachedGetter(getColrefSymbols)


def getCST(literal, grammarFactory=None):
	"""returns a CST for an STC-S expression.

	grammarFactory is a function returning the grammar, in this case
	either getGrammar (which gets used if the argument is left out) or 
	getColrefGrammar.
	"""
	# special case: the empty input yields an empty CST
	if not literal.strip():
		return {}

	if grammarFactory is None:
		grammarFactory = getGrammar
	try:
		tree = makeTree(utils.pyparseString(
			grammarFactory()["stcsPhrase"], literal))
	except (ParseException, ParseSyntaxException), ex:
		raise common.STCSParseError(
			"Invalid STCS expression (%s at %s)"%(ex.msg, ex.loc),
			expr=literal, pos=ex.loc)
	addDefaults(tree)
	return tree


if __name__=="__main__":
	import pprint
	syms = getColrefSymbols()
#	print getCST("PositionInterval ICRS 1 2 3 4")
	enableDebug(syms)
	pprint.pprint(makeTree(syms["stcsPhrase"].parseString(
		"Position ICRS Epoch J2000.0 20 21"
		, parseAll=True)))
