"""
A parser for ADQL.

The grammar follows the official BNF grammar quite closely, except where
pyparsing makes a different approach desirable; the names should mostly
match except for the obious underscore to camel case map.

The grammar given in the spec has some nasty rules when you're parsing
without backtracking and by recursive descent (which is what pyparsing
does).  I need some reformulations.  The more interesting of those 
include:

TableReference
--------------

Trouble is  that table_reference is left-recursive in the following rules::

  <table_reference> ::=
	 <table_name> [ <correlation_specification> ]
   | <derived_table> <correlation_specification>
   | <joined_table>

  <joined_table> ::=
	  <qualified_join>
	| <left_paren> <joined_table> <right_paren>

  <qualified_join> ::=
	  <table_reference> [ NATURAL ] [ <join_type> ] JOIN
	  <table_reference> [ <join_specification> ]

We fix this by adding rules::

	<sub_join> ::= '(' <joinedTable> ')'
  <join_opener> ::=
	 <table_name> [ <correlation_specification> ]
   | <derived_table> <correlation_specification>
	 | <sub_join>

and then writing::

  <qualified_join> ::=
	  <join_opener> [ NATURAL ] [ <join_type> ] JOIN
	  <table_reference> [ <join_specification> ]



statement
---------

I can't have StringEnd appended to querySpecification since it's used
in subqueries, but I need to have it to keep pyparsing from just matching
parts of the input.  Thus, the top-level production is for "statement".


trig_function, math_function, system_defined_function
-----------------------------------------------------

I think it's a bit funny to have the arity of functions in the syntax, but
there you go.  Anyway, I don't want to have the function names in separate
symbols since they are expensive but go for a Regex (trig1ArgFunctionName).
The only exception is ATAN since it has a different arity from the rest of the
lot.

Similarly, for math_function I group symbols by arity.

The system defined functions are also regrouped to keep the number of
symbols reasonable.

column_reference and below
--------------------------

Here the lack of backtracking hurts badly, since once, say, schema name
is matched with a dot that's it, even if the dot should really have separated
schema and table.

Hence, we don't assign semantic labels in the grammar but leave that to
whatever interprets the tokens.

The important rules here are::

	<column_name> ::= <identifier>
	<correlation_name> ::= <identifier>
	<catalog_name> ::= <identifier>
	<unqualified_schema name> ::= <identifier>
	<schema_name> ::= [ <catalog_name> <period> ] <unqualified_schema name>
	<table_name> ::= [ <schema_name> <period> ] <identifier>
	<qualifier> ::= <table_name> | <correlation_name>
	<column_reference> ::= [ <qualifier> <period> ] <column_name>

By substitution, one has::

	<schema_name> ::= [ <identifier> <period> ] <identifier>

hence::

	<table_name> ::= [[ <identifier> <period> ] <identifier> <period> ] 
		<identifier>

hence::

	<qualifier> ::= [[ <identifier> <period> ] <identifier> <period> ] 
		<identifier>

(which matches both table_name and correlation_name) and thus::

	<column_reference> ::= [[[ <identifier> <period> ] <identifier> <period> ] 
		<identifier> <period> ] <identifier>

We need the table_name, qualifier, and column_reference productions.


generalLiterals in unsigngedLiterals
------------------------------------

One point I'm deviating from the published grammar is that I disallow
generalLiterals in unsignedLiterals.  Allowing them would let pyparsing
match a string literal as a numericValueLiteral, which messes up
string expressions.  I'm not sure why generalLiterals are allowed
in there anyway.  If this bites at some point, we'll face a major rewrite
of the grammar (or we need to dump pyparsing).

To make the whole thing work, I added the generalLiteral to the 
characterPrimary production.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from __future__ import with_statement

from gavo.imp.pyparsing import (
	Word, Literal, Optional, alphas, CaselessKeyword,
	ZeroOrMore, OneOrMore, StringEnd,
	Forward, nums, 
	CaselessLiteral, ParseException, Regex, sglQuotedString, alphanums,
	ParserElement, White, 
	ParseExpression)

from gavo.imp.pyparsing import ParseSyntaxException #noflake: exported name
from gavo import utils
from gavo import stc

__docformat__ = "restructuredtext en"


# all SQL and ADQL reserved words are expected in uppercase by this and
# other modules.
adqlReservedWords = set([ "ABS", "ACOS", "AREA", "ASIN", "ATAN", "ATAN2",
	"CEILING", "CENTROID", "CIRCLE", "CONTAINS", "COS", "DEGREES", "DISTANCE",
	"EXP", "FLOOR", "INTERSECTS", "LATITUDE", "LOG", "LOG10", "COORD1",
	"COORD2", "COORDSYS", "BOX",
	"MOD", "PI", "POINT", "POLYGON", "POWER", "RADIANS", "REGION",
	"RAND", "ROUND", "SIN", "SQUARE", "SQRT", "TOP", "TAN", "TRUNCATE",])

sqlReservedWords = set([
	"ABSOLUTE", "ACTION", "ADD", "ALL", "ALLOCATE", "ALTER", "AND", "ANY",
	"ARE", "AS", "ASC", "ASSERTION", "AT", "AUTHORIZATION", "AVG", "BEGIN",
	"BETWEEN", "BIT", "BIT_LENGTH", "BOTH", "BY", "CASCADE", "CASCADED",
	"CASE", "CAST", "CATALOG", "CHAR", "CHARACTER", "CHAR_LENGTH",
	"CHARACTER_LENGTH", "CHECK", "CLOSE", "COALESCE", "COLLATE",
	"COLLATION", "COLUMN", "COMMIT", "CONNECT", "CONNECTION", "CONSTRAINT",
	"CONSTRAINTS", "CONTINUE", "CONVERT", "CORRESPONDING", "COUNT",
	"CREATE", "CROSS", "CURRENT", "CURRENT_DATE", "CURRENT_TIME",
	"CURRENT_TIMESTAMP", "CURRENT_USER", "CURSOR", "DATE", "DAY",
	"DEALLOCATE", "DECIMAL", "DECLARE", "DEFAULT", "DEFERRABLE", "DEFERRED",
	"DELETE", "DESC", "DESCRIBE", "DESCRIPTOR", "DIAGNOSTICS", "DISCONNECT",
	"DISTINCT", "DOMAIN", "DOUBLE", "DROP", "ELSE", "END", "END-EXEC",
	"ESCAPE", "EXCEPT", "EXCEPTION", "EXEC", "EXECUTE", "EXISTS",
	"EXTERNAL", "EXTRACT", "FALSE", "FETCH", "FIRST", "FLOAT", "FOR",
	"FOREIGN", "FOUND", "FROM", "FULL", "GET", "GLOBAL", "GO", "GOTO",
	"GRANT", "GROUP", "HAVING", "HOUR", "IDENTITY", "IMMEDIATE", "IN",
	"INDICATOR", "INITIALLY", "INNER", "INPUT", "INSENSITIVE", "INSERT",
	"INT", "INTEGER", "INTERSECT", "INTERVAL", "INTO", "IS", "ISOLATION",
	"JOIN", "KEY", "LANGUAGE", "LAST", "LEADING", "LEFT", "LEVEL", "LIKE",
	"LOCAL", "LOWER", "MATCH", "MAX", "MIN", "MINUTE", "MODULE", "MONTH",
	"NAMES", "NATIONAL", "NATURAL", "NCHAR", "NEXT", "NO", "NOT", "NULL",
	"NULLIF", "NUMERIC", "OCTET_LENGTH", "OF", "ON", "ONLY", "OPEN",
	"OPTION", "OR", "ORDER", "OUTER", "OUTPUT", "OVERLAPS", "PAD",
	"PARTIAL", "POSITION", "PRECISION", "PREPARE", "PRESERVE", "PRIMARY",
	"PRIOR", "PRIVILEGES", "PROCEDURE", "PUBLIC", "READ", "REAL",
	"REFERENCES", "RELATIVE", "RESTRICT", "REVOKE", "RIGHT", "ROLLBACK",
	"ROWS", "SCHEMA", "SCROLL", "SECOND", "SECTION", "SELECT", "SESSION",
	"SESSION_USER", "SET", "SIZE", "SMALLINT", "SOME", "SPACE", "SQL",
	"SQLCODE", "SQLERROR", "SQLSTATE", "SUBSTRING", "SUM", "SYSTEM_USER",
	"TABLE", "TEMPORARY", "THEN", "TIME", "TIMESTAMP", "TIMEZONE_HOUR",
	"TIMEZONE_MINUTE", "TO", "TRAILING", "TRANSACTION", "TRANSLATE",
	"TRANSLATION", "TRIM", "TRUE", "UNION", "UNIQUE", "UNKNOWN", "UPDATE",
	"UPPER", "USAGE", "USER", "USING", "VALUE", "VALUES", "VARCHAR",
	"VARYING", "VIEW", "WHEN", "WHENEVER", "WHERE", "WITH", "WORK", "WRITE",
	"YEAR", "ZONE"])

allReservedWords = adqlReservedWords | sqlReservedWords


# A regular expression for prefixes of user defined functions
userFunctionPrefix = "(gavo|ivo)"


def _makeQuotedName(s, p, t):
# Parse action for delimitedIdentifer.  No longer necessary when we can
# rely on working pyparsing QuotedString
	return utils.QuotedName(str(t[0])[1:-1].replace('""', '"'))


def Args(pyparseSymbol):
	"""wraps pyparseSymbol such that matches get added to an adqlArgs list
	on the parent node.
	"""
	return pyparseSymbol.setResultsName("args", listAllMatches=True)


def _joinChildren(s, p, toks):
	return " ".join(toks)


class RegularIdentifier(Word):
	"""regular identifiers are all C-style identifiers except reserved
	words.

	Filtering these in the parse action doesn't always work properly for
	all versions of pyparsing, thus this special class.

	reservedWords are assumed to be in upper case, but matching 
	case-insensitively.
	"""
	def __init__(self, reservedWords):
		self.reservedWords = reservedWords
		super(RegularIdentifier, self).__init__(alphas+"_", alphanums+"_")

	def parseImpl(self, instring, loc, doActions=True):
		locNew, match = super(RegularIdentifier, self).parseImpl(instring,
			loc, doActions)
		if match.upper() in self.reservedWords:
			raise ParseException(instring, loc, "Reserved word not allowed here")
		return locNew, match


class LongestMatch(ParseExpression):
	"""pyparsing's Or, except that ParseFatalExceptions are still propagated.
	"""
	def __init__(self, exprs, savelist=False):
		super(LongestMatch, self).__init__(exprs, savelist)
		self.mayReturnEmpty = False
		for e in self.exprs:
			if e.mayReturnEmpty:
				self.mayReturnEmpty = True
				break

	def parseImpl(self, instring, loc, doActions=True):
		maxExcLoc = -1
		maxMatchLoc = -1
		maxException = None
		for e in self.exprs:
			try:
				loc2 = e._parse(instring, loc, doActions=False)[0]
			except ParseException, err:
				if err.loc>maxExcLoc:
					maxException = err
					maxExcLoc = err.loc
			except IndexError:
				if len(instring)>maxExcLoc:
					maxException = ParseException(
						instring, len(instring), e.errmsg, self)
					maxExcLoc = len(instring)
			else:
				if loc2>maxMatchLoc:
					maxMatchLoc = loc2
					maxMatchExp = e

		if maxMatchLoc<0:
			if maxException is not None:
				raise maxException
			else:
				raise ParseException(instring, loc, 
					"no defined alternatives to match", self)

		return maxMatchExp._parse(instring, loc, doActions)

	def __str__( self ):
		if hasattr(self,"name"):
			return self.name

		if self.strRepr is None:
			self.strRepr = "{" + " ^ ".join( [ str(e) for e in self.exprs ] ) + "}"

		return self.strRepr

	def checkRecursion( self, parseElementList ):
		subRecCheckList = parseElementList[:] + [ self ]
		for e in self.exprs:
			e.checkRecursion( subRecCheckList )


def getADQLGrammarCopy():
	"""returns a pair symbols, selectSymbol for a grammar parsing ADQL.

	You should only use this if you actually require a fresh copy
	of the ADQL grammar.  Otherwise, use getADQLGrammar or a wrapper
	function defined by a client module.
	"""
	with utils.pyparsingWhitechars("\n\t\r "):
# Be careful when using setResultsName here.  The handlers are bound
# at a later point, and names cause copies of the pyparsing objects,
# so that elements named in rules will not be bound later.  Rather
# name elements on their construction.
		sqlComment = Regex("--[^\n\r]*")
		whitespace = Word(" \t\n")   # need that as a hack now and then to keep
		                             # numbers and identifiers from sticking

		unsignedInteger = Word(nums)
		unsignedInteger.setName("unsigned integer")
		_exactNumericRE = r"\d+(\.(\d+)?)?|\.\d+"
		exactNumericLiteral = Regex(_exactNumericRE)
		approximateNumericLiteral = Regex(r"(?i)(%s)E[+-]?\d+"%_exactNumericRE)
		unsignedNumericLiteral = ( approximateNumericLiteral | exactNumericLiteral )
		characterStringLiteral = sglQuotedString + ZeroOrMore( sglQuotedString )
		generalLiteral = characterStringLiteral.copy()
		unsignedLiteral = unsignedNumericLiteral # !!! DEVIATION | generalLiteral
		sign = Literal("+") | "-"
		signedInteger = Optional( sign ) + unsignedInteger 
		signedInteger.setName("signed integer")
		multOperator = Literal("*") | Literal("/")
		addOperator =  Literal("+") | Literal("-")
		notKeyword = CaselessKeyword("NOT")
		nullLiteral = CaselessKeyword("NULL")

		regularIdentifier = RegularIdentifier(allReservedWords)
		regularIdentifier.setName("identifier")
# There's a bug with QuotedString in some versions of pyparsing.
# So, don't use this:
#	delimitedIdentifier = QuotedString(quoteChar='"', escQuote='"',
#		unquoteResults=True).addParseAction(
#			lambda s,p,t: utils.QuotedName(str(t)))
# but rather
		delimitedIdentifier = Regex('("[^"]*")+').addParseAction(
			_makeQuotedName)
		identifier = regularIdentifier | delimitedIdentifier

# Operators
		compOp = Regex("=|!=|<=|>=|<|>")
		compOp.setName("comparison operator")

# Column names and such
		columnName = identifier.copy()
		correlationName = identifier.copy()
		qualifier = (identifier 
			+ Optional( "." + identifier )
			+ Optional( "." + identifier ))
		tableName = qualifier("tableName")
		columnReference = (identifier 
			+ Optional( "." + identifier )
			+ Optional( "." + identifier )
			+ Optional( "." + identifier ))
		asClause = ( CaselessKeyword("AS") | whitespace ) + columnName("alias")

		valueExpression = Forward()

# set functions
		setFunctionType = Regex("(?i)AVG|MAX|MIN|SUM|COUNT")
		setQuantifier = Regex("(?i)DISTINCT|ALL")
		generalSetFunction = (setFunctionType("fName") 
			+ '(' + Optional( setQuantifier ) + Args(valueExpression) + ')')
		countAll = (CaselessLiteral("COUNT")("fName") 
			+ '(' + Args(Literal('*')) + ')')
		setFunctionSpecification = (countAll | generalSetFunction)

# value expressions
		valueExpressionPrimary = ( unsignedLiteral |
			columnReference | setFunctionSpecification |
			'(' + valueExpression + ')')

# string literal stuff
		characterPrimary = Forward() 
		characterFactor = characterPrimary
		characterValueExpression = ( characterFactor + 
			ZeroOrMore( "||" + characterFactor ))
		stringValueExpression = characterValueExpression

# numeric expressions/terms
		numericValueExpression = Forward()
		numericValueFunction = Forward()
		numericExpressionPrimary = ( #noflake: name exported through locals()
			unsignedLiteral | columnReference
			| setFunctionSpecification | '(' + valueExpression + ')')
		numericPrimary = numericValueFunction | valueExpressionPrimary 
		factor = Optional( sign ) + numericPrimary
		term = (factor + ZeroOrMore( multOperator + factor ))
		numericValueExpression << (term + ZeroOrMore( addOperator + term ))

# geometry types and expressions
		tapCoordLiteral = Regex("(?i)'(?P<sys>%s)'"%"|".join(stc.TAP_SYSTEMS)
				).addParseAction(lambda s,p,t: t["sys"].upper())
		tapCoordLiteral.setName("coordinate system literal (ICRS, GALACTIC,...)")
		coordSys = (tapCoordLiteral
			| nullLiteral.copy().addParseAction(lambda s,p,t: "UNKNOWN")
			).setResultsName("coordSys")
		coordinates = (Args(numericValueExpression) 
			+ ',' + Args(numericValueExpression))
		box = (CaselessKeyword("BOX")("fName") 
			- '(' - coordSys + ','
			+ coordinates +  ','
			+ coordinates + ')')
		point = (CaselessKeyword("POINT")("fName") 
			- '(' - coordSys - ',' 
			+ coordinates + ')')
		circle = (CaselessKeyword("CIRCLE")("fName") 
			- '(' - coordSys + ',' 
			+ coordinates + ',' 
			+ Args(numericValueExpression) + ')')
		polygon = (CaselessKeyword("POLYGON")("fName") 
			- '(' - coordSys + ',' 
			+ coordinates 
			+ OneOrMore( ',' + coordinates ) + ')')
		region = (CaselessKeyword("REGION")("fName") 
			+ '(' 
			+ Args(stringValueExpression) + ')')
		geometryExpression = box | point | circle | polygon | region
		geometryValue = columnReference.copy()
		coordValue = point | columnReference
		centroid = (CaselessKeyword("CENTROID")("fName") 
			+ '(' + Args(geometryExpression) + ')')
		geometryValueExpression = geometryExpression | geometryValue | centroid

# geometry functions
		distanceFunction = (CaselessKeyword("DISTANCE")("fName") 
			+ '(' + Args(coordValue) + ',' + Args(coordValue) + ')')
		pointFunction = (Regex("(?i)COORD[12]|COORDSYS")("fName") + '(' +
			Args(coordValue) + ')')
		area = (CaselessKeyword("AREA")("fName") 
			+ '(' + Args(geometryValueExpression) + ')')
		nonPredicateGeometryFunction = (distanceFunction | pointFunction | area)
		predicateGeoFunctionName = Regex("(?i)CONTAINS|INTERSECTS")
		predicateGeometryFunction = (predicateGeoFunctionName("fName") 
			+ '(' + Args(geometryValueExpression) 
			+ ',' + Args(geometryValueExpression) + ')')
		numericGeometryFunction = (predicateGeometryFunction | 
			nonPredicateGeometryFunction)

# numeric, system, user defined functions
		trig1ArgFunctionName = Regex("(?i)ACOS|ASIN|ATAN|COS|COT|SIN|TAN")
		# trig1ArgFunction is what causes a parse failure on common numeric
		# value expressions.  We take the liberty of misnaming it for better
		# error messages in most cases.
		trig1ArgFunctionName.setName("numeric expression")
		trigFunction = (
				trig1ArgFunctionName("fName") + '('
					+ Args(numericValueExpression) + ')' 
			|	CaselessKeyword("ATAN2")("fName") + '(' + 
				Args(numericValueExpression) + ',' 
					+ Args(numericValueExpression) + ')')
		math0ArgFunctionName = Regex("(?i)PI")
		optIntFunctionName = Regex("(?i)RAND")
		math1ArgFunctionName = Regex("(?i)ABS|CEILING|DEGREES|EXP|FLOOR|LOG10|"
			"LOG|RADIANS|SQUARE|SQRT")
		optPrecArgFunctionName = Regex("(?i)ROUND|TRUNCATE")
		math2ArgFunctionName = Regex("(?i)POWER|MOD")
		mathFunction = (
				math0ArgFunctionName("fName") + '(' + ')' 
			|	optIntFunctionName("fName") + '(' 
				+ Optional( Args(unsignedInteger) ) + ')' 
			|	math1ArgFunctionName("fName") + '(' 
				+ Args(numericValueExpression) + ')' 
			| optPrecArgFunctionName("fName") + '(' 
				+ Args(numericValueExpression) +
				Optional( ',' + Args(signedInteger) ) + ')' 
			|	math2ArgFunctionName("fName") + '(' 
				+ Args(numericValueExpression) 
				+ ',' + Args(numericValueExpression) + ')')
		userDefinedFunctionParam = valueExpression
		userDefinedFunctionName = Regex("(?i)"+userFunctionPrefix+"_[A-Za-z_]+")
		userDefinedFunctionName.setName("Name of locally defined function")
		userDefinedFunction = ( userDefinedFunctionName("fName") + '(' +
			Args(userDefinedFunctionParam) 
			+ ZeroOrMore( "," + Args(userDefinedFunctionParam) ) 
				+ ')')
		numericValueFunction << (trigFunction 
			| mathFunction 
			| userDefinedFunction 
			| numericGeometryFunction)

		characterPrimary << (generalLiteral | valueExpressionPrimary | 
			userDefinedFunction)

# toplevel value expression
		valueExpression << LongestMatch([
			numericValueExpression,
			stringValueExpression,
			geometryValueExpression])
		derivedColumn = valueExpression("expr") + Optional( asClause )

# parts of select clauses
		setQuantifier = (CaselessKeyword( "DISTINCT" ) 
			| CaselessKeyword( "ALL" ))("setQuantifier")
		setLimit = CaselessKeyword( "TOP" ) - unsignedInteger("setLimit")
		qualifiedStar = qualifier + "." + "*"
		selectSublist = (qualifiedStar | derivedColumn
			).setResultsName("fieldSel", listAllMatches=True)
		selectList = (Literal("*")("starSel")
			| selectSublist + ZeroOrMore( "," - selectSublist ))
		selectList.setName("select list")

# boolean terms
		subquery = Forward()
		searchCondition = Forward()
		comparisonPredicate = valueExpression + compOp + valueExpression
		betweenPredicate = (valueExpression + Optional( notKeyword ) + 
			CaselessKeyword("BETWEEN") - valueExpression + 
			CaselessKeyword("AND") - valueExpression)
		inValueList = valueExpression + ZeroOrMore( ',' + valueExpression )
		inPredicateValue = subquery | ( "(" + inValueList + ")" )
		inPredicate = (valueExpression + Optional( notKeyword ) + 
			CaselessKeyword("IN") + inPredicateValue)
		existsPredicate = CaselessKeyword("EXISTS") - subquery
		likePredicate = (characterValueExpression + Optional( notKeyword ) + 
			CaselessKeyword("LIKE") + characterValueExpression)
		nullPredicate = (columnReference + CaselessKeyword("IS") +
			Optional( notKeyword ) - nullLiteral)
		predicate = (comparisonPredicate | betweenPredicate | inPredicate | 
			likePredicate | nullPredicate | existsPredicate)
		booleanPrimaryOpener = Literal('(')  # for error messages
		booleanPrimaryOpener.setName("boolean expression")
		booleanPrimary = booleanPrimaryOpener + searchCondition + ')' | predicate
		booleanFactor = Optional( notKeyword ) + booleanPrimary
		booleanTerm = ( booleanFactor + 
			ZeroOrMore( CaselessKeyword("AND") - booleanFactor ))

# WHERE clauses and such
		searchCondition << ( booleanTerm + 
			ZeroOrMore( CaselessKeyword("OR") - booleanTerm ))
		searchCondition.setName("search condition")
		whereClause = (CaselessKeyword("WHERE") - searchCondition)("whereClause")

# Referencing tables
		queryExpression = Forward()
		correlationSpecification = (( CaselessKeyword("AS") | whitespace
			) + correlationName("alias"))
		subqueryOpener = Literal('(')
		subqueryOpener.setName("subquery")  # for error reporting
		subquery << (subqueryOpener + queryExpression + ')')
		derivedTable = subquery.copy() + correlationSpecification
		possiblyAliasedTable = tableName + Optional(correlationSpecification)
		joinedTable = Forward()
		subJoin = '(' + joinedTable + ')'
		joinOperand = (possiblyAliasedTable 
			| derivedTable
			| subJoin)
		tableReference = (joinedTable 
			| possiblyAliasedTable 
			| derivedTable)

# JOINs
		columnNameList = columnName + ZeroOrMore( "," + columnName)
		namedColumnsJoin = (CaselessKeyword("USING") + '(' +
			columnNameList("columnNames") + ')')
		joinCondition = CaselessKeyword("ON") - searchCondition
		joinSpecification = joinCondition | namedColumnsJoin
		outerJoinType = (CaselessKeyword("LEFT") 
			| CaselessKeyword("RIGHT") 
			| CaselessKeyword("FULL"))
		joinType = (CaselessKeyword("INNER") 
			| (outerJoinType + CaselessKeyword("OUTER"))
			| CaselessKeyword("CROSS"))  # local extension
		joinOperator = (Optional( CaselessKeyword("NATURAL") )
				+ Optional( joinType )
				+ CaselessKeyword( "JOIN" )
			) | Literal( ',' )
		joinedTable << (joinOperand
			+ ZeroOrMore( joinOperator
				+ joinOperand
				+ Optional( joinSpecification ) ))

# Detritus in table expressions
		groupByClause = (CaselessKeyword( "GROUP" ) + CaselessKeyword( "BY" ) 
			+ columnReference 
			+ ZeroOrMore( ',' + columnReference ))("groupby")
		havingClause = (CaselessKeyword( "HAVING" ) 
			+ searchCondition)("having")
		orderingSpecification = (CaselessKeyword( "ASC") 
			| CaselessKeyword("DESC"))
		sortKey = columnName | unsignedInteger
		sortSpecification = sortKey + Optional( orderingSpecification )
		orderByClause = (CaselessKeyword("ORDER") 
			+ CaselessKeyword("BY") + sortSpecification 
			+ ZeroOrMore( ',' + sortSpecification ))("orderBy")

# FROM fragments and such
		fromClause = ( CaselessKeyword("FROM") 
			+ tableReference )("fromClause")
		tableExpression = (fromClause + Optional( whereClause ) 
			+ Optional( groupByClause )  + Optional( havingClause ) 
			+ Optional( orderByClause ))

# toplevel select clause
		querySpecification = Forward()
		queryExpression << ( querySpecification |  joinedTable )
		querySpecification << ( CaselessKeyword("SELECT") 
			+ Optional( setQuantifier )
			+ Optional( setLimit ) 
			+ selectList + tableExpression )
		statement = querySpecification + Optional( White() ) + StringEnd()

# comment
		statement.ignore(sqlComment)
		return dict((k, v) for k, v in locals().iteritems()
			if isinstance(v, ParserElement)), statement


_grammarCache = None

def enableDebug(syms, debugNames=None):
	if not debugNames:
		debugNames = syms
	for name in debugNames:
		ob = syms[name]
		if not ob.debug:
			ob.setDebug(True)
			ob.setName(name)
	syms["sqlComment"].setDebug(False)

def enableTree(syms):
	def makeAction(name):
		def action(s, pos, toks):
			return [name, toks]
		return action
	for name in syms:
		ob = syms[name]
		if not ob.debug:
			ob.setDebug(True)
			ob.setName(name)
			ob.addParseAction(makeAction(name))


def getADQLGrammar():
	"""returns a pair of (symbols, root) for an ADQL grammar.

	This probably is mainly useful for testing.  At least you should not set
	names or parseActions on whatever you are returned unless you are
	testing.
	"""
	global _grammarCache
	if not _grammarCache:
		_grammarCache = getADQLGrammarCopy()
	return _grammarCache

if __name__=="__main__":
	def printCs(s, pos, toks):
		print "---------------Tokens:", toks
	import pprint, sys
	syms, grammar = getADQLGrammar()
	enableTree(syms)
	res = syms["querySpecification"].parseString(
		"select 'ivo://' ||  '%' as pat from crazy"
		, parseAll=True)
	pprint.pprint(res.asList(), stream=sys.stderr)
