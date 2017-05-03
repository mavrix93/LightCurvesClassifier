"""
Classes and methods to support vizier-type specifications on fields.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from __future__ import with_statement

import datetime
import re

from gavo.imp.pyparsing import (Word, Literal, Optional, Forward,
	ZeroOrMore, Suppress, ParseException, StringEnd, Regex,
	OneOrMore, CharsNotIn)

from gavo import base
from gavo import stc
from gavo import utils
from gavo.base import literals
from gavo.base import sqlmunge
from gavo.base import typesystems


class ParseNode(object):
	"""is a parse node, consisting of an operator and children.

	The parse trees returned by the various parse functions are built from
	these.

	This is an abstract class; concrete derivations need to define
	a set _standardOperators containing the normal binary operators
	for their types and a dictionary _sqlEmitters containing functions
	returning SQL fragments, or override asSQL.
	"""
	def __init__(self, children, operator):
		self.children = children
		self.operator = operator
	
	def __str__(self):
		return "(%s %s)"%(self.operator, " ".join([str(c) for c in self.children]))

	def __repr__(self):
		return "(%r %r)"%(self.operator, " ".join([str(c) for c in self.children]))

	def _insertChild(self, index, field, sqlPars):
		"""inserts children[index] into sqlPars with a unique key and returns
		the key.

		children[index] must be atomic (i.e., no ParseNode).
		"""
		item = self.children[index]
		if item is None:
			return None
		assert not isinstance(item, ParseNode)
		if field.scaling:
			item *= field.scaling
		return base.getSQLKey(field.name, item, sqlPars)

	def asSQL(self, field, sqlPars):
		if self.operator in self._standardOperators:
			return "%s %s %%(%s)s"%(field.name, self.operator, 
				self._insertChild(0, field, sqlPars))
		else:
			return self._sqlEmitters[self.operator](self, field, sqlPars)


class NumericNode(ParseNode):
	"""is a node containing numeric operands (floats or dates).
	"""
	def _emitBinop(self, field, sqlPars):
		return base.joinOperatorExpr(self.operator,
			[c.asSQL(field, sqlPars) for c in self.children])
		
	def _emitUnop(self, field, sqlPars):
		operand = self.children[0].asSQL(field, sqlPars)
		if operand:
			return "%s (%s)"%(self.operator, operand)

	def _emitEnum(self, field, sqlPars):
		return "%s IN (%s)"%(field.name, ", ".join([
					"%%(%s)s"%self._insertChild(i, field, sqlPars) 
				for i in range(len(self.children))]))

	_standardOperators = set(["=", ">=", ">", "<=", "<"])
	_sqlEmitters = {
		'..': lambda self, field, sqlPars: "%s BETWEEN %%(%s)s AND %%(%s)s"%(
			field.name, self._insertChild(0, field, sqlPars), 
			self._insertChild(1, field, sqlPars)),
		'AND': _emitBinop,
		'OR': _emitBinop,
		'NOT': _emitUnop,
		',': _emitEnum,
	}


class StringNode(ParseNode):
	def asSQL(self, field, sqlPars):
		if self.operator=="[":
			return "[%s]"%self.children[0]
		if self.operator in self._nullOperators:
			return self._nullOperators[self.operator]
		else:
			return super(StringNode, self).asSQL(field, sqlPars)

	_metaEscapes = {
		"|": r"\|",
		"*": r"\*",
		"+": r"\+",
		"(": r"\(",
		")": r"\)",
		"[": r"\[",
		"%": r"\%",
		"_": r"\_",
		"\\\\": "\\\\",
	}
	_escapeRE = re.compile("[%s]"%"".join(_metaEscapes.keys()))
	# The backslash in _metaEscapes is escaped to make _escapeRE work,
	# but of course I need to replace the unescaped version.
	_metaEscapes.update({"\\": "\\\\"})

	def _escapeSpecials(self, aString):
		"""returns aString with SQL RE metacharacters escaped.
		"""
		return self._escapeRE.sub(lambda mat: self._metaEscapes[mat.group()],
			aString)

	def _makePattern(self, field, sqlPars):
		parts = []
		for child in self.children:
			if isinstance(child, basestring):
				parts.append(self._escapeSpecials(child))
			else:
				parts.append(child.asSQL(field, sqlPars))
		return "^%s$"%("".join(parts))

	_patOps = {
		"~": "~*",
		"=": "~",
		"!~": "!~*",
		"!": "!~",
		"=~": "~*",
	}
	def _emitPatOp(self, field, sqlPars):
		pattern = self._makePattern(field, sqlPars)
		return "%s %s %%(%s)s"%(field.name, self._patOps[self.operator],
			base.getSQLKey(field.name, pattern, sqlPars))

	def _emitEnum(self, field, sqlPars):
		query = "%s IN (%s)"%(field.name, ", ".join([
					"%%(%s)s"%self._insertChild(i, field, sqlPars) 
				for i in range(len(self.children))]))
		if self.operator=="!=,":
			query = "NOT (%s)"%query
		return query

	_translatedOps = {
		"==": "=",
	}
	def _emitTranslatedOp(self, field, sqlPars):
		return "%s = %%(%s)s"%(field.name, 
			self._insertChild(0, field, sqlPars))

	_nullOperators = {"*": ".*", "?": "."}
	_standardOperators = set(["<", ">", "<=", ">=", "!="])
	_sqlEmitters = {
		"~": _emitPatOp,
		"=": _emitPatOp,
		"!~": _emitPatOp,
		"!": _emitPatOp,
		"=~": _emitPatOp,  # this happens to work because of pattern escaping
		"=,": _emitEnum,
		"=|": _emitEnum,
		"!=,": _emitEnum,
		"==": _emitTranslatedOp,
		}


def _getNodeFactory(op, nodeClass):
	def _(s, loc, toks):
		return nodeClass(toks, op)
	return _


def _makeNotNode(s, loc, toks):
	if len(toks)==1:
		return toks[0]
	elif len(toks)==2:
		return NumericNode(toks[1:], "NOT")
	else: # Can't happen :-)
		raise Exception("Busted by not")


def _makePmNode(s, loc, toks):
	return NumericNode([toks[0]-toks[1], toks[0]+toks[1]], "..")


def _makeDatePmNode(s, loc, toks):
	"""returns a +/- node for dates, i.e., toks[1] is a float in days.
	"""
	days = datetime.timedelta(days=toks[1])
	return NumericNode([toks[0]-days, toks[0]+days], "..")


def _getBinopFactory(op):
	def _(s, loc, toks):
		if len(toks)==1:
			return toks[0]
		else:
			return NumericNode(toks, op)
	return _


def _makeSimpleExprNode(s, loc, toks):
	if len(toks)==1:
		return NumericNode(toks[0:], "=")
	else:
		return NumericNode(toks[1:], toks[0])


def getComplexGrammar(baseLiteral, pmBuilder, errorLiteral=None):
	"""returns the root element of a grammar parsing numeric vizier-like 
	expressions.

	This is used for both dates and floats, use baseLiteral to match the
	operand terminal.  The trouble with dates is that the +/- operator
	has a simple float as the second operand, and that's why you can
	pass in an errorLiteral and and pmBuilder.
	"""
	if errorLiteral is None:
		errorLiteral = baseLiteral

	with utils.pyparsingWhitechars(" \t"):
		preOp = Literal("=") |  Literal(">=") | Literal(">"
			) | Literal("<=") | Literal("<")
		rangeOp = Literal("..")
		pmOp = Literal("+/-") | Literal("\xb1".decode("iso-8859-1"))
		orOp = Literal("|")
		andOp = Literal("&")
		notOp = Literal("!")
		commaOp = Literal(",")

		preopExpr = Optional(preOp) + baseLiteral
		rangeExpr = baseLiteral + Suppress(rangeOp) + baseLiteral
		valList = baseLiteral + OneOrMore( Suppress(commaOp) + baseLiteral)
		pmExpr = baseLiteral + Suppress(pmOp) + errorLiteral
		simpleExpr = rangeExpr | pmExpr | valList | preopExpr

		expr = Forward()

		notExpr = Optional(notOp) +  simpleExpr
		andExpr = notExpr + ZeroOrMore( Suppress(andOp) + notExpr )
		orExpr = andExpr + ZeroOrMore( Suppress(orOp) + expr)
		expr << orExpr
		exprInString = expr + StringEnd()

		rangeExpr.setName("rangeEx")
		rangeOp.setName("rangeOp")
		notExpr.setName("notEx")
		andExpr.setName("andEx")
		andOp.setName("&")
		orExpr.setName("orEx")
		expr.setName("expr")
		simpleExpr.setName("simpleEx")

		preopExpr.addParseAction(_makeSimpleExprNode)
		rangeExpr.addParseAction(_getNodeFactory("..", NumericNode))
		pmExpr.addParseAction(pmBuilder)
		valList.addParseAction(_getNodeFactory(",", NumericNode))
		notExpr.addParseAction(_makeNotNode)
		andExpr.addParseAction(_getBinopFactory("AND"))
		orExpr.addParseAction(_getBinopFactory("OR"))

		return exprInString


def parseFloat(s, pos, tok):
# This one is important: If something looks like an int, return it as an
# int -- otherwise, postgres won't use int-indices
	try:
		return int(tok[0])
	except ValueError:
		return float(tok[0])

floatLiteral = Regex(utils.floatRE).addParseAction(parseFloat)

# XXX TODO: be a bit more lenient in what you accept as a date
_DATE_REGEX = r"\d\d\d\d-\d\d-\d\d(T\d\d:\d\d:\d\d)?"
_DATE_LITERAL_DT = Regex(_DATE_REGEX).addParseAction(
			lambda s, pos, tok: literals.parseDefaultDatetime(tok[0]))
_DATE_LITERAL_MJD = Regex(_DATE_REGEX).addParseAction(
			lambda s, pos, tok: stc.dateTimeToMJD(
				literals.parseDefaultDatetime(tok[0])))



def parseNumericExpr(str, baseSymbol=getComplexGrammar(floatLiteral, 
		_makePmNode)):
	"""returns a parse tree for vizier-like expressions over floats.
	"""
	return utils.pyparseString(baseSymbol, str)[0]


def parseDateExpr(str, baseSymbol=getComplexGrammar(_DATE_LITERAL_DT,
		_makeDatePmNode, floatLiteral)):
	"""returns a parse tree for vizier-like expressions over ISO dates.

	Note that the semantic validity of the date (like, month<13) is not
	checked by the grammar.
	"""
	return utils.pyparseString(baseSymbol, str)[0]


def parseDateExprToMJD(str, baseSymbol=getComplexGrammar(_DATE_LITERAL_MJD,
		_makePmNode, floatLiteral)):
	"""returns a parse tree for vizier-like expression of ISO dates with
	parsed values in MJD.
	"""
	return utils.pyparseString(baseSymbol, str)[0]


def _makeOpNode(s, loc, toks):
	return StringNode(toks[1:], toks[0])


def getStringGrammar():
	"""returns a grammar for parsing vizier-like string expressions.
	"""
# XXX TODO: should we cut at =| (which is currently parsed as = |)?
	with utils.pyparsingWhitechars(" \t"):
		simpleOperator = Literal("==") | Literal("!=") | Literal(">=") |\
			Literal(">") | Literal("<=") | Literal("<") | Literal("=~") |\
			Literal("=,")
		simpleOperand = Regex(r"[^\s].*|")
		# XXX probably a bug in pyparsing: White shouldn't be necessary here
		White = Word(" \t")
		simpleExpr = simpleOperator + Optional( White ) + simpleOperand

		commaOperand = Regex("[^,]+")
		barOperand = Regex("[^|]+")
		commaEnum = Literal("=,") + commaOperand + ZeroOrMore(
			Suppress(",") + commaOperand)
		exclusionEnum = Literal("!=,") + commaOperand + ZeroOrMore(
			Suppress(",") + commaOperand)
		barEnum = Literal("=|") + barOperand + ZeroOrMore(
			Suppress("|") + barOperand)
		enumExpr = exclusionEnum | commaEnum | barEnum

		patLiterals = CharsNotIn("[*?")
		wildStar = Literal("*")
		wildQmark = Literal("?")
		setElems = CharsNotIn("]")
		setSpec = Suppress("[") + setElems + Suppress("]")
		pattern = OneOrMore(setSpec | wildStar | wildQmark | patLiterals)

		patternOperator = Literal("~") | Literal("=") | Literal("!~") |\
			Literal("!")
		patternExpr = patternOperator + Optional( White ) + pattern
		nakedExpr = Regex("[^=!~|><]") + Optional( simpleOperand )

		stringExpr = enumExpr | simpleExpr | patternExpr | nakedExpr
		
		doc = stringExpr + StringEnd()

		stringExpr.setName("StringExpr")
		enumExpr.setName("EnumExpr")
		simpleOperand.setName("Operand")
		simpleOperator.setName("Operator")
		nakedExpr.setName("SingleOperand")

		debug = False
		stringExpr.setDebug(debug)
		enumExpr.setDebug(debug)
		patLiterals.setDebug(debug)
		simpleOperand.setDebug(debug)
		simpleOperator.setDebug(debug)
		nakedExpr.setDebug(debug)

		simpleExpr.addParseAction(_makeOpNode)
		patternExpr.addParseAction(_makeOpNode)
		enumExpr.addParseAction(_makeOpNode)
		makeDefaultExpr = _getNodeFactory("==", StringNode)
		nakedExpr.addParseAction(lambda s,p,toks: makeDefaultExpr(s,p,
			["".join(toks)]))
		wildStar.addParseAction(_makeOpNode)
		wildQmark.addParseAction(_makeOpNode)
		setElems.addParseAction(_getNodeFactory("[", StringNode))

		return doc


def parseStringExpr(str, baseSymbol=getStringGrammar()):
	return utils.pyparseString(baseSymbol, str)[0]


def _makeFactory(parser):
	def factory(field, val, sqlPars):
		try:
			return parser(val).asSQL(field, sqlPars)
		except ParseException:
			raise base.ui.logOldExc(utils.ValidationError(
				"Invalid input for type %s (see help for valid type literals)"%
					field.type, field.name))
	return factory


sqlmunge.registerSQLFactory("vexpr-float",
	_makeFactory(parseNumericExpr))
sqlmunge.registerSQLFactory("vexpr-date",
	_makeFactory(parseDateExpr))
sqlmunge.registerSQLFactory("vexpr-mjd",
	_makeFactory(parseDateExprToMJD))
sqlmunge.registerSQLFactory("vexpr-string",
	_makeFactory(parseStringExpr))


class ToVexprConverter(typesystems.FromSQLConverter):
	typeSystem = "vizierexpr"
	simpleMap = {
		"smallint": "vexpr-float",
		"integer": "vexpr-float",
		"int": "vexpr-float",
		"bigint": "vexpr-float",
		"real": "vexpr-float",
		"float": "vexpr-float",
		"double precision": "vexpr-float",
		"double": "vexpr-float",
		"text": "vexpr-string",
		"unicode": "vexpr-string",
		"char": "vexpr-string",
		"date": "vexpr-date",
		"timestamp": "vexpr-date",
		"vexpr-date": "vexpr-date",
		"vexpr-float": "vexpr-float",
		"vexpr-string": "vexpr-string",
	}

	def mapComplex(self, sqlType, length):
		if sqlType=="char":
			return "vexpr-string"
		if sqlType=="varchar":
			return "vexpr-string"

getVexprFor = ToVexprConverter().convert


def makeConeSearchFor(inputKey):
	"""returns an //scs#makeSpointCD condDesc tailored for inputKey.
	"""
	from gavo.svcs import standardcores
	return base.parseFromString(standardcores.CondDesc, """
		<FEED source="//scs#makeSpointCD"
			tablehead=%s
			matchColumn=%s/>
		"""%(
			utils.escapeAttrVal(inputKey.tablehead),
			utils.escapeAttrVal(inputKey.name)))


def adaptInputKey(inputKey):
	"""returns ik changed to generate SQL for Vizier-like expressions.

	This is used for buildFrom on CondDescs and renderers having
	parameterStyle form.
	"""
	# manually check for things that need to change the whole condDesc.
	if inputKey.type=='spoint':
		raise base.Replace(makeConeSearchFor(inputKey))
	if inputKey.xtype=="mjd":
		return inputKey.change(type="vexpr-mjd", unit="")
	if inputKey.isEnumerated():
		return inputKey

	try:
		return inputKey.change(
			type=getVexprFor(inputKey.type),
			values=None)
	except base.ConversionError:  # No vexpr type, leave things
		pass
	return inputKey


def _test():
	import doctest, vizierexprs
	doctest.testmod(vizierexprs)


if __name__=="__main__":
	print repr(parseStringExpr("=="))
