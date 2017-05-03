"""
Code to support PQL syntax (as found in various DAL protocols).

PQL range-list syntax is

valSep ::= ","
rangeSep ::= "/"
qualSep ::= ";"
step ::= somethingMagicallyDefined
range ::= [literal] rangeSep literal | literal rangeSep
steppedRange ::= range [rangeSep step]
qualification ::= qualSep somethingMagicallyDefined
listItem ::= steppedRange | literal 
rangeList ::= listItem {valSep listItem} [qualification]

This defines a regular language, and we're going to slaughter it using
REs and ad hoccing.

Since the actually allowed grammar depends on the type of the parameter
(e.g., steps make no sense for strings, and have a special grammar for
dates), parsing is done by the specific PQLPar types (fromLiteral).  See
the PQLPar docstring for further info.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import datetime
import re
import urllib

from gavo import base
from gavo import stc
from gavo import utils
from gavo.base import literals
from gavo.base import sqlmunge
from gavo.base import typesystems
from gavo.utils import DEG, pgsphere


QUALIFIER_RE = re.compile("([^;]*)(;[^;]*)?$")
LIST_RE = re.compile("([^,]*),")
RANGE_RE = re.compile("([^/]*)(/[^/]*)?(/[^/]*)?$")


def _raiseNoSteps(val):
	raise ValueError("Step/stride specification not allowed here.")


def _parsePQLValue(val, valInd=0, vp=str):
	if not val or not val[valInd:]:
		return None
	else:
		return vp(urllib.unquote(val[valInd:]))


class PQLRange(object):
	"""a representation of a PQL range.

	PQLRanges have a value attribute that is non-None when there is
	only a single value.

	For ranges, there is start, stop and step, all of which may be
	None.

	The attributes contain whatever the parent's valParser (or stepParser)
	functions return.
	"""
	def __init__(self, value=None, start=None, stop=None, step=None):
		self.start, self.stop, self.step = start, stop, step
		self.value = value
		if (self.step is not None 
				and (self.start is None or self.stop is None)):
			raise ValueError("Open intervals cannot have steps")
		if (self.value is None 
				and (self.start is None and self.stop is None)):
			raise ValueError("Doubly open intervals are not allowed")

	def __eq__(self, other):
		return (isinstance(other, PQLRange)
			and self.value==other.value 
			and self.start==other.start 
			and self.stop==other.stop 
			and self.step==other.step)

	def __repr__(self):
		return "%s(%s, %s, %s, %s)"%(self.__class__.__name__,
			repr(self.value),
			repr(self.start),
			repr(self.stop),
			repr(self.step))

	def __str__(self):
		if self.value is not None:
			return urllib.quote(str(self.value))
		else:
			def e(v):
				if v is None:
					return ""
				else:
					return urllib.quote(str(v))
			return "/".join(e(v) for v in (self.start, self.stop, self.step))
			
	@classmethod
	def fromLiteral(cls, literal, destName, valParser, stepParser):
		"""creates a PQLRange from a PQL range literal.

		For the meaning of the arguments, see PQLPar.fromLiteral.
		"""
		if literal=="":
			return cls(value="")
		mat = RANGE_RE.match(literal)
		if not mat:
			raise base.LiteralParseError(destName, literal,
				hint="PQL ranges roughly have the form [start][/stop[/stop]]."
				" Literal slashes need to be escaped (as %2f).")
		vals = mat.groups()

		try:
			if vals[1] is None and vals[2] is None:
				return cls(value=_parsePQLValue(vals[0], vp=valParser))
			else:
				start, stop, step = vals
			return cls(
				start=_parsePQLValue(start, vp=valParser), 
				stop=_parsePQLValue(stop, 1, vp=valParser), 
				step=_parsePQLValue(step, 1, vp=stepParser))
		except ValueError, ex:
			raise base.LiteralParseError("range within %s"%destName, literal,
				hint=str(ex))

	def getValuesAsSet(self):
		"""returns a set containing all values matching the PQL condition if
		they form a discrete set or raises a ValueError if not.
		"""
		if self.value is not None:
			return set([self.value])
		elif (self.step is not None \
				and self.start is not None 
				and self.stop is not None):
			if (self.stop-self.start)/abs(self.step)+1e-10>2000:
				raise ValueError("Too many steps; will not check discretely")
			res, val = set(), self.start
			while val<=self.stop:
				res.add(val)
				val = val+self.step
			return res
		raise ValueError("No set representation for non-stepped or open ranges.")

	def getSQL(self, colName, sqlPars, cmpExpr=None):
		"""returns an SQL boolean expression for representing this constraint.

		cmpExpr, if given, will be an expression that is compared
		against.  It defaults to colName, but this is, of course, intended
		to allow stuff like LOWER(colName).
		"""
		if cmpExpr is None:
			cmpExpr = colName

		# Single Value
		if self.value is not None:
			return "%s = %%(%s)s"%(cmpExpr, 
				base.getSQLKey(colName, self.value, sqlPars))
		
		# Discrete Set
		try:
			return "%s IN %%(%s)s"%(cmpExpr, base.getSQLKey(colName, 
				self.getValuesAsSet(), sqlPars))
		except ValueError: # Not a discrete set
			pass

		# At least one half-open or non-stepped range
		if self.start is None and self.stop is not None:
			return "%s <= %%(%s)s"%(cmpExpr, 
				base.getSQLKey(colName, self.stop, sqlPars))
		elif self.start is not None and self.stop is None:
			return "%s >= %%(%s)s"%(cmpExpr, 
				base.getSQLKey(colName, self.start, sqlPars))
		else:
			assert self.start is not None and self.stop is not None
			return "%s BETWEEN %%(%s)s AND %%(%s)s "%(cmpExpr, 
				base.getSQLKey(colName, self.start, sqlPars),
				base.getSQLKey(colName, self.stop, sqlPars))

	def getSQLForInterval(self, lowerColName, upperColName, sqlPars):
		"""returns an SQL boolean expression for representing this constraint
		against an upper, lower interval in the DB table.

		This will silently discard any step specification.
		"""
		# Single Value
		if self.value is not None:
			return "%%(%s)s BETWEEN %s AND %s"%(
				base.getSQLKey("val", self.value, sqlPars),
				lowerColName, upperColName)
		else:
			constraints = []
			if self.stop is not None:
				constraints.append("%%(%s)s>%s"%(
					base.getSQLKey("val", self.stop, sqlPars),
					lowerColName))
			if self.start is not None:
				constraints.append("%%(%s)s<%s"%(
					base.getSQLKey("val", self.start, sqlPars),
					upperColName))
			return "(%s)"%" AND ".join(constraints)

	def covers(self, value):
		"""returns True if value is covered by this interval.

		value must be type-true, i.e. in whatever type value, start, and stop
		have.
		"""
		# try a single value
		if self.value is not None:
			return value==self.value

		# try a discrete set ("step" has been specified)
		try:
			return value in self.getValuesAsSet()
		except ValueError: # not a discrete set
			pass
	
		# interval, possibly half-open
		covers = True
		if self.start is not None:
			covers &= self.start<=value
		if self.stop is not None:
			covers &= self.stop>=value
		return covers

					
class PQLPar(object):
	"""a representation for PQL expressions.

	PQLPar objects have an attribute qualifier (None or a string),
	and an attribute ranges, a list of PQLRange objects.
	
	As a client, you will ususally construct PQLPar objects using the
	fromLiteral class method; it takes a PQL literal and a name to be 
	used for LiteralParseErrors it may raise.

	The plain PQLPar parses string ranges and does not allow steps.

	Inheriting classes must override the valParser and stepParser attributes.
	Both take a string and have to return a typed value or raise a
	ValueError if the string does not contain a proper literal.
	The default for valParser is str, the default for stepParser
	a function that always raises a ValueError.

	PQLPars usually support a covers(value) method that you can
	pass a value having the required type; it will return whether or
	not value would be picked up by the condition formulated in PQL.  
	Some advanced PQLPars do not support this method and will 
	raise a ValueError if called.

	Note: valParser and stepParser must not be *methods* of the
	class but plain functions; since they are function-like class attributes,
	you will usually have to wrap them in staticmethods
	"""
	nullvalue = None
	valParser = str
	stepParser = staticmethod(_raiseNoSteps)

	def __init__(self, ranges, qualifier=None, destName=None):
		self.qualifier = qualifier
		self.ranges = ranges
		self.destName = destName

	def __eq__(self, other):
		return (isinstance(other, PQLPar)
			and self.qualifier==other.qualifier
			and self.ranges==other.ranges)

	def __str__(self):
		res = ",".join(str(r) for r in self.ranges)
		if self.qualifier:
			res = res+";"+urllib.quote(self.qualifier)
		return res
	
	def __repr__(self):
		return "%s(%s)"%(self.__class__.__name__,
			repr(str(self)))

	@staticmethod
	def _parsePQLString(cls, val, destName):
		# this is the implementation of the fromLiteral class method(s)
		# It's static so the fromLiterals can upcall.
		if val is None:
			return None

		if val==cls.nullvalue:
			return None

		mat = QUALIFIER_RE.match(val)
		if not mat:
			raise base.LiteralParseError(destName, val, hint="Not more than one"
				" semicolon is allowed in PQL expressions")
		qualifier = _parsePQLValue(mat.group(2), 1)

		ranges = []
		listLiteral = mat.group(1)
		# harmless hack to avoid special-casing for one-element list
		rangeMat = re.match("", listLiteral)
		for rangeMat in LIST_RE.finditer(listLiteral):
			try:
				ranges.append(
					PQLRange.fromLiteral(rangeMat.group(1), destName, 
						cls.valParser, cls.stepParser))
			except base.LiteralParseError, ex:
				ex.pos = rangeMat.start()
				raise
		ranges.append(
			PQLRange.fromLiteral(listLiteral[rangeMat.end():], destName,
				cls.valParser, cls.stepParser))
		return cls(ranges, qualifier, destName)

	@classmethod
	def fromLiteral(cls, val, destName):
		"""returns a parsed representation of a literal in PQL range-list syntax.

		val is a string containing the PQL expression, destName is a name to
		be used for the LiteralParseErrors the function raises when there are
		syntax errors in val.
		"""
		return cls._parsePQLString(cls, val, destName)

	def getValuesAsSet(self):
		"""returns a set of all values mentioned within the PQL expression.

		This raises a ValueError if this is not possible (e.g., due to
		non-stepped intervals).
		"""
		res = set()
		for r in self.ranges:
			res.update(r.getValuesAsSet())
		return res

	def getSQL(self, colName, sqlPars, cmpExpr=None):
		"""returns an SQL condition expressing this PQL constraint for colName.

		The parameters necessary are added to sqlPars.

		cmpExpr can be used to override the cmpExpr argument to PQLRange.getSQL;
		this is not really intended for user code, though, but rather for
		subclasses of PQLPar
		"""
		if cmpExpr is None:
			cmpExpr = colName

		if len(self.ranges)==1: # Special case for SQL cosmetics
			return self.ranges[0].getSQL(colName, sqlPars, cmpExpr=cmpExpr)

		try:
			return "%s IN %%(%s)s"%(cmpExpr, base.getSQLKey(colName, 
				self.getValuesAsSet(), sqlPars))
		except ValueError:  # at least one open or non-stepped range
			return "(%s)"%" OR ".join(
				r.getSQL(colName, sqlPars, cmpExpr=cmpExpr) for r in self.ranges)

	def covers(self, value):
		"""returns true if value is within the ranges specified by the PQL 
		expression.

		value must be type-true, i.e., you are responsible for converting it
		into the type the range are in.
		"""
		for r in self.ranges:
			if r.covers(value):
				return True
		return False


class PQLIntPar(PQLPar):
	"""a PQL parameter containing an integer.

	steps in ranges are allowed.
	"""
	nullvalue = ""
	valParser = int
	stepParser = int


class PQLDatePar(PQLPar):
	"""a PQL parameter containing a date.

	steps in ranges are allowed.

	There's an additional complication here: in the database, dates can be
	represented in various forms.  To save the day, getSQL takes an
	additional optional parameter and transfroms the input values as
	appropriate before passing them to the database.
	"""
	nullvalue = ""
	valParser = staticmethod(literals.parseDefaultDatetime)

	@staticmethod
	def stepParser(val):
		return datetime.timedelta(days=float(val))

	def getSQL(self, colName, sqlPars, convert=None):
		"""returns an SQL condition expressing the PQL constraint for colName.

		In addition to the usual parameters, we here accept an additonal
		argument convert with possible values None (meaning timestamp, 
		which is the default) mjd, jd, and jy, which represents how the 
		datetimes are represented in the database.  
		"""
		converter = {
			None: utils.identity,
			"mjd": stc.dateTimeToMJD,
			"jd": stc.dateTimeToJdn,
			"jy": stc.dateTimeToJYear,}[convert]

		oldKeys = set(sqlPars.keys())
		res = PQLPar.getSQL(self, colName, sqlPars)

		# now update all keys we are responsible for
		if converter:
			for key in sqlPars:
				if key not in oldKeys:
					if sqlPars[key] is not None:
						sqlPars[key] = converter(sqlPars[key])
		return res


class PQLPositionPar(PQLPar):
	"""a PQL position parameter, as for SSA.

	Cones and intervals or real lists do not mix; we support STC-S 
	identifiers as qualifiers.

	The literals here are basically two-float lists.
	"""
	valParser = float
	nullvalue = ""

	@classmethod
	def fromLiteral(cls, val, destName):
		# Hack: allow encodeded commas; this has been seen in the
		# wild and would be the saner way to encode this.
		if val is not None:
			val = val.upper().replace("%2C", ",")
		return cls._parsePQLString(cls, val, destName)

	def getSQL(self, colName, sqlPars):
		raise NotImplementedError("Ranges for PQL POS not implemented yet.")
	
	def getConeSQL(self, colName, sqlPars, coneSize):
		if self.qualifier and self.qualifier!='ICRS':
			# XXX TODO: implement at least a couple of common frames
			raise base.ValidationError("Cannot match against coordinates"
				" given in %s frame"%self.qualifier, self.destName)

		sizeName = base.getSQLKey("size", coneSize*DEG, sqlPars)
		parts = []
		if len(self.ranges)%2:
			raise base.ValidationError("PQL position values must be lists of"
				" length divisible by 2.", self.destName)
		lastCoo = None
		for r in self.ranges:
			if r.value is None:
				raise base.ValidationError("Ranges are not allowed as cone centers",
					self.destName)
			if lastCoo is None:
				lastCoo = r.value
			else:
				parts.append("%s <-> %%(%s)s < %%(%s)s"%(colName,
					base.getSQLKey("pos", pgsphere.SPoint.fromDegrees(lastCoo, r.value), 
						sqlPars), sizeName))
				lastCoo = None
		return "(%s)"%" OR ".join(parts)

	def covers(self, value):
		raise ValueError("%s do not support PQL covers yet.  Complain."
			"  This is fairly easy to fix."%self.__class__.__name__)


class PQLFloatPar(PQLPar):
	"""a PQL float parameter.

	This has a special getSQLForInterval method for cases like SSA's
	BAND.
	"""
	valParser = float
	nullvalue = ""

	def getSQLForInterval(self, lowerColName, upperColName, sqlPars):
		"""returns an SQL phrase against an interval in a table.
		"""
		if len(self.ranges)==1: # Special case for SQL cosmetics
			return self.ranges[0].getSQLForInterval(
				lowerColName, upperColName, sqlPars)
		else:
			return "(%s)"%" OR ".join(
				r.getSQLForInterval(lowerColName, upperColName, sqlPars) 
					for r in self.ranges)


class PQLCaselessPar(PQLPar):
	"""a PQL string parameter that's compared with case folding.

	Don't count on case folding to work outside of ASCII.
	"""
	valParser = staticmethod(lambda val: val and val.lower())

	def getSQL(self, colName, sqlPars, cmpExpr=None):
		"""Overridden to change cmpExpr.
		"""
		return PQLPar.getSQL(self, colName, sqlPars, "LOWER(%s)"%colName)

	def covers(self, value):
		if value is None:
			return False
		return PQLPar.covers(self, value.lower())


class PQLShellPatternPar(PQLPar):
	"""a PQL shell pattern parameter.

	These are posix shell patterns, where no PQL metacharacters are evaluated
	at all.
	"""
	_reOperator = "~"

	@classmethod
	def fromLiteral(cls, val, destName):
		if val is None:
			return None
		val = getREForShPat(val)
		return cls([PQLRange(val)])
	
	def getSQL(self, colName, sqlPars):
		"""returns an RE-based query equivalent to the input shell pattern.
		"""
		return "ssa_targname %s %%(%s)s"%(self._reOperator,
			base.getSQLKey(colName, self.ranges[0].value, sqlPars))

	def covers(self, value):
		raise ValueError("%s do not support PQL covers yet.  Complain."
			"  This is easy to fix."%self.__class__.__name__)


class PQLNocaseShellPatternPar(PQLShellPatternPar):
	"""a shell-pattern matching parameter, ignoring case.
	"""
	_reOperator = "~*"


class PQLTextParIR(PQLPar):
	"""a PQL string parameter matching "google-like", "Information Retrieval".

	Basically, this matches the input and the database column as document
	vectors.  Correspondingly, ranges are disallowed.
	"""
	nullvalue = ""

	def getSQL(self, colName, sqlPars):
		try:
			docs = self.getValuesAsSet()
		except ValueError:
			# ranges were given; we don't support those with IR-searching
			raise base.LiteralParseError(colName, str(self), hint=
				"Ranges are not allowed with IR-matches (or did you want to"
				" to search for a slash?  In that case, please escape it)")

		keys = []
		for doc in docs:
			keys.append(base.getSQLKey(colName, doc, sqlPars))

		return "(%s)"%" OR ".join(
			"to_tsvector('english', %s) @@ plainto_tsquery('english', %%(%s)s)"%(
				colName,
				keyName)
			for keyName in keys)

	def covers(self, value):
		raise ValueError("%s do not support PQL covers."%self.__class__.__name__)


######## posix shell patterns hacking (find some better place?)
def _mungeEnumSequence(s, p, t):
	"""a pyparsing handler for transforming shell character enumerations to
	pcre character enumerations.

	(this is a helper for _getShPatGrammar)
	"""
	seq = "".join(t)
	# metacharacters in seq are troublesome: ! vs. ^, and we need to
	# defuse hyphens, brackets, and backslashes
	negate = seq.startswith("!")
	if negate:
		seq = seq[1:]
	seq = seq.replace("]", "\\]"
		).replace("\\", "\\\\"
		).replace("-", "\\-")

	if negate:
		return "[^%s]"%seq
	else:
		return "[%s]"%seq


@utils.memoized
def _getShPatGrammar():
	"""returns a grammar to translate posix shell patterns to posix regular
	expressions.

	This is different from fnmatch.translate in that it handles escaping
	correctly.
	"""
	from gavo.imp.pyparsing import (
		Literal, Regex, CharsNotIn, ZeroOrMore, QuotedString)

	with utils.pyparsingWhitechars(""):
		enumChars = QuotedString(quoteChar="[", endQuoteChar="]", escChar="\\"
			).addParseAction(_mungeEnumSequence)
		noEnum = Literal("[").addParseAction(lambda s, p, t: "\\[")
		star = Literal("*").addParseAction(lambda s, p, t: ".*")
		questionmark = Literal("?").addParseAction(lambda s, p, t: ".")
		escSeq = Regex(r"\\(.)").addParseAction(lambda s, p, t: re.escape(t[0][1]))
		normalStuff = CharsNotIn(r"*?[\\").addParseAction(lambda s, p, t:
			re.escape("".join(t)))
		shPat = ZeroOrMore(escSeq | enumChars | noEnum
			| star | questionmark | normalStuff)
	return shPat


def getREForShPat(shPat):
	r"""returns a POSIX RE for a POSIX shell pattern.

	>>> getREForShPat(r"ZU?\*[!A-Z]*")
	'ZU.\\*[^A\\-Z].*'
	>>> getREForShPat("no[*")
	'no\\[.*'
	"""
	return "".join(utils.pyparseString(_getShPatGrammar(), shPat, parseAll=True))

######### end posix shell patterns

def _makeFactory(parType):
	def factory(field, val, sqlPars):
		try:
			return parType.fromLiteral(val, field.name).getSQL(field.name, sqlPars)
		except ValueError:
			raise base.ui.logOldExc(utils.ValidationError(
				"Invalid input for type %s"
				" (valid PQL literals are described in the help)"%field.type, 
				field.name))
	return factory


sqlmunge.registerSQLFactory("pql-int", _makeFactory(PQLIntPar))
sqlmunge.registerSQLFactory("pql-float", _makeFactory(PQLFloatPar))
sqlmunge.registerSQLFactory("pql-string", _makeFactory(PQLPar))
sqlmunge.registerSQLFactory("pql-date", _makeFactory(PQLDatePar))


class ToPQLTypeConverter(typesystems.FromSQLConverter):
	typeSystem = "pqlexpr"
	simpleMap = {
		"smallint": "pql-int",
		"integer": "pql-int",
		"int": "pql-int",
		"bigint": "pql-int",
		"real": "pql-float",
		"float": "pql-float",
		"double precision": "pql-float",
		"double": "pql-float",
		"text": "pql-string",
		"char": "pql-string",
		"date": "pql-date",
		"timestamp": "pql-date",
		"pql-date": "pql-date",
		"pql-float": "pql-float",
		"pql-string": "pql-string",
	}

	def mapComplex(self, sqlType, length):
		if sqlType=="char":
			return "pql-string"
		if sqlType=="varchar":
			return "pql-string"


getPQLTypeFor = ToPQLTypeConverter().convert


def adaptInputKey(inputKey):
	"""returns inputKey changed to generate SQL for PQL-like expressions.

	This is used for buildFrom on CondDescs and renderers having
	parameterStyle pql.
	"""
	try:
		return inputKey.change(
			type=getPQLTypeFor(inputKey.type),
			values=None)
	except base.ConversionError:  # No vexpr type, leave things
		pass
	return inputKey


# Make the whole thing available to procDefs and such
import sys
from gavo import rscdef
rscdef.addProcDefObject("pql", sys.modules[__name__])


def _test():
	import pql, doctest
	doctest.testmod(pql)

if __name__=="__main__":
	_test()
