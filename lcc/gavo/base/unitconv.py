"""
A python module to parse VOUnit strings and compute conversion factors.

We believe this implements the full VOUnit specification.

To use this, you must have the gavo utils package  installed.  For
details, see http://soft.g-vo.org.  The changes required to make this
work without gavo.utils are minute, though.  If you want that, talk to
the authors.

Unit tests for this are at

http://svn.ari.uni-heidelberg.de/svn/gavo/python/trunk/tests/unitconvtest.py
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from __future__ import with_statement

import math


from gavo import utils
from gavo.imp import pyparsing


class IncompatibleUnits(utils.Error):
	pass

class BadUnit(utils.Error):
	pass


# We can't yet restructure the tree, so we don't do SI-base-casting for
# compound units.  Also, we don't change anything when a change of exponent
# would be necessary
PLAIN_UNITS = units = {
	"a": (3600*24*365.25, "s"), # This is the SI/julian year!
	"A": (1, "A"),				# *Ampere* not Angstrom 
	"adu": (1, "adu"),
	u"\xc5": (1e-10, "m"),
	"Angstrom": (1e-10, "m"),
	"angstrom": (1e-10, "m"),
	"AU": (1.49598e11, "m"), 
	"arcmin": (math.pi/180./60., "rad"), 
	"arcsec": (math.pi/180./3600., "rad"), 
	"barn": (1, "barn"),  # 1e-28 m2
	"beam": (1, "beam"), 
	"bit": (1, "bit"), 
	"bin": (1, "bin"), 
	"byte": (1, "byte"),  # I don't think we ever want to unify bit and byte
	"C": (1, "C"),        # A.s
	"cd": (1, "cd"), 
	"ct": (1, "ct"), 
	"count": (1, "ct"), 
	"chan": (1, "chan"), 
	"D": (1e-19/3., "D"), # C.m
	"d": (3600*24, "s"), 
	"deg": (math.pi/180., "rad"), 
	"erg": (1e-7, "J"), 
	"eV": (1.602177e-19, "J"), 
	"F": (1, "F"),        # C/V
	"g": (1e-3, "kg"), 
	"G": (1e-4, "T"), 
	"h": (3600., "s"), 
	"H": (1, "H"),        # Wb/A
	"Hz": (1, "Hz"),      # s-1
	"J": (1, "J"), 				# kg m^2/s^2
	"Jy": (1, "Jy"),			# 1e-26 W/m2/Hz
	"K": (1, "K"), 
	"lm": (1, "lm"), 
	"lx": (1, "lx"), 
	"lyr": (2627980686828.0, "m"), 
	"m": (1, "m"), 
	"mag": (1, "mag"),    # correlate that with, erm, lux?
	"mas": (math.pi/180./3.6e6, "rad"), 
	"min": (60, "s"), 
	"mol": (1, "mol"), 
	"N": (1, "N"),        # kg.m/s2
	"Ohm": (1, "Ohm"),    # V/A
	"Pa": (1, "Pa"),      # N/m^2
	"pc": (3.0857e16, "m"), 
	"ph": (1, "ph"), 
	"photon": (1, "ph"), 
	"pix": (1, "pix"), 
	"pixel": (1, "pix"), 
	"R": (1, "R"),        # Rayleigh
	"rad": (1, "rad"), 
	"Ry": (2.17989e-18, "J"), 
	"s": (1, "s"), 
	"S": (1, "S"),        # A/V
	"solLum": (3.826e26, "W"),
	"solMass": (1.989e30, "kg"),
	"solRad": (6.9559e8, "m"), 
	"sr": (1, "sr"), 
	"T": (1, "T"),        # V.s/m2
	"u": (1.66053886e-27, "kg"),
	"V": (1, "V"), 
	"voxel": (1, "voxel"),
	"W": (1, "W"),        # kg.m2/s3 or A.V -- that's going to be a tough one
	"Wb": (1, "Wb"), 
	"yr": (3600*24*365.25, "s"), # This is the SI/julian year!
}

# These are the keys from PLAIN_UNITS that cannot take SI prefixes
NON_PREFIXABLE = frozenset([
	"AU", "au", "D", "Ry", "arcmin", "beam", "bin", "chan", "d", "h", "mas",
	"min", "ph", "photon", "pix", "pixel", "solLum", "solMass", "solRad",
	"voxel"])


PREFIXES = prefixes = {"d": 1e-1, "c": 1e-2, "m":1e-3, "u":1e-6, 
	"n":1e-9, "p":1e-12, "f":1e-15, "a":1e-18, "z":1e-21, "y":1e-24,
	"da": 10., "h":1e2, "k":1e3, "M":1e6, "G":1e9, "T":1e12, "P":1e15, 
	"E":1e18, "Z":1e21, "Y":1e24, "": 1}


# these map VOUnit Table 5 "magic" units to UnitNode constructor arguments
AMBIGUOUS_STRINGS = {
	'Pa': ('Pa', ''),
	'ha': ('yr', 'h'),
	'cd': ('cd', ''),
	'dB': ('Bel', 'd'),
	'B': ('Byte', ''),
	'au': ('AU', ''),
	'dadu': ('adu', 'd'),
}


def formatScaleFactor(aFloat):
	"""returns a reasonable decorative but python-readable representation
	of aFloat.

	Floats looking good as simple decimals (modulus between 0.01 and 1000)
	are returned without exponent.
	"""
	if 0.01<=abs(aFloat)<=1000:
		return ("%f"%aFloat).rstrip("0")

	exponent = int(math.log10(aFloat))
	mantissa = ("%f"%(aFloat/10**exponent)).rstrip("0")
	return "%se%+d"%(mantissa, exponent)


class _Node(object):
	"""the abstract base for a node in a Unit tree.

	All these must implement fromToks methods that can be called
	as pyparsing callbacks.
	"""
	@classmethod 
	def fromToks(cls, s, p, toks):
		raise NotImplementedError("%s objects have no implementation of"
			" fromToks (i.e., they are broken)."%cls.__name__)


class UnitNode(_Node):
	"""a terminal node containing a unit, possibly with a prefix

	This is normally constructed through the fromToks constructor.

	Check out the unit, prefix, and isUnknown attributes.  The prefix
	can be turned to a factor using the PREFIXES dictionary.  An empty
	prefix (factor 1) is represented by an empty string.
	"""
	def __init__(self, unit, prefix=""):
		self.unit = unit
		self.isUnknown = self.unit not in PLAIN_UNITS
		self.prefix = prefix

	@classmethod
	def fromToks(cls, s, p, toks):
		assert len(toks)==1
		unitString = toks[0]
	
		if unitString in AMBIGUOUS_STRINGS:
			return cls(*AMBIGUOUS_STRINGS[unitString])

		elif unitString in PLAIN_UNITS:
			return cls(unitString)

		elif len(unitString)>2 and unitString[:2]=="da":
			return cls(unitString[2:], "da")

		elif len(unitString)>1 and unitString[0] in PREFIXES:
			if unitString[1:] in NON_PREFIXABLE:
				raise BadUnit("No Prefixes allowed on %s"%unitString[1:])
			return cls(unitString[1:], unitString[0])

		else:
			return cls(unitString, '')

	def __str__(self):
		return "%s%s"%(self.prefix, self.unit)

	def __repr__(self):
		if self.isUnknown:
			return "U?(%s ; %s)"%(self.prefix, repr(self.unit))
		else:
			return "U(%s ; %s)"%(self.prefix, repr(self.unit))

	def getSI(self):
		"""returns a pair of factor and basic unit.

		Basic units are what's in the defining pairs in the PLAIN_UNITS dict.
		"""
		if self.isUnknown:
			# these don't hurt if they're on both sides of an equation
			return PREFIXES[self.prefix], {self.unit: 1}
			return 
		factor, basic = PLAIN_UNITS[self.unit]
		return PREFIXES[self.prefix]*factor, {basic: 1}


class FunctionApplication(_Node):
	"""A function applied to a term.
	"""
	_pythonFunc = {
		"ln": math.log,
		"log": math.log10,
		"exp": math.exp,
		"sqrt": math.sqrt,
	}

	def __init__(self, funcName, term):
		self.funcName = funcName
		self.term = term
		self.isUnknown = (self.funcName not in self._pythonFunc
			) or self.term.isUnknown

	@classmethod
	def fromToks(cls, s, p, toks):
		assert len(toks)==2
		return cls(toks[0], toks[1])

	def __str__(self):
		return "%s(%s)"%(self.funcName, self.term)

	def __repr__(self):
		return "A(%s ; %s)"%(repr(self.funcName), repr(self.term))
	
	def getSI(self):
		factor, powers = self.term.getSI()
		if self.funcName=="sqrt":
			powers = dict((key, value/2.) 
				for key, value in powers.iteritems())
		else:
			powers = dict(((self.funcName, key), value) 
				for key, value in powers.iteritems())
		return self._pythonFunc[self.funcName](factor), powers


class QuotedUnitNode(_Node):
	"""a quoted ("defined unknown") unit.
	"""
	def __init__(self, unit):
		self.unit = unit
		self.isUnknown = True

	@classmethod
	def fromToks(cls, s, p, toks):
		return cls(toks[1])

	def __str__(self):
		return "'%s'"%(self.unit)

	def __repr__(self):
		return "U?('%s')"%(repr(self.unit))

	def getSI(self):
		# These units stand for themselves.  They don't really hurt if
		# they're in both terms of a conversion
		return 1, {self.unit: 1}


class Factor(_Node):
	"""A UnitNode with a power.
	"""
	def __init__(self, unit, power):
		self.unit, self.power = unit, power
		self.isUnknown = self.unit.isUnknown
	
	@classmethod
	def fromToks(cls, s, p, toks):
		if len(toks)==2:
			return cls(toks[0], toks[1])
		elif len(toks)==1:
			return cls(toks[0], 1)
		else:
			raise Exception("This cannot happen")

	def __str__(self):
		powerLit = repr(self.power).rstrip("0").rstrip(".")
		if "." in powerLit:
			# see if we can come up with a nice fraction
			for denom in range(2, 8):
				if abs(int(self.power*denom)-self.power*denom)<1e-13:
					powerLit = "(%d/%d)"%(round(self.power*denom), denom)
					break

		if powerLit=="1":
			powerLit = ""
		else:
			powerLit = "**"+powerLit

		return "%s%s"%(self.unit, powerLit)

	def __repr__(self):
		return "F(%s ; %s)"%(repr(self.unit), repr(self.power))
	
	def getSI(self):
		factor, powers = self.unit.getSI()
		powers[powers.keys()[0]] = self.power
		return factor**self.power, powers


class Term(_Node):
	"""A Node containing two factors and an operator.

	The operator here is either . (product) or / (division).
	"""
	def __init__(self, op1, operator, op2):
		self.op1, self.operator, self.op2 = op1, operator, op2
		self.isUnknown = self.op1.isUnknown or self.op2.isUnknown
	
	@classmethod
	def fromToks(cls, s, p, toks):
		if len(toks)==1:
			# avoid to many internal nodes: a 1-operand expression is the operand
			return toks[0]
		return cls(toks[0], toks[1], toks[2])

	def __str__(self):
		op1Lit, op2Lit = str(self.op1), str(self.op2)
		if self.operator=='/' and isinstance(self.op2, Term):
			op2Lit = "(%s)"%op2Lit
		return "%s%s%s"%(op1Lit, self.operator, op2Lit)

	def __repr__(self):
		return "T(%s ; %s ; %s)"%(repr(self.op1), 
			repr(self.operator), repr(self.op2))

	def getSI(self):
		factor1, powers1 = self.op1.getSI()
		factor2, powers2 = self.op2.getSI()
		newPowers = powers1
		if self.operator==".":
			for si, power in powers2.iteritems():
				newPowers[si] = newPowers.get(si, 0)+power
			return factor1*factor2, newPowers
		elif self.operator=="/":
			for si, power in powers2.iteritems():
				newPowers[si] = newPowers.get(si, 0)-power
			return factor1/factor2, newPowers
		else:
			raise Exception("This can't happen")


class Expression(_Node):
	"""The root node of an expression tree. 
	
	This contains a term and optionally a scale factor.
	"""
	def __init__(self, term, scaleFactor):
		self.term, self.scaleFactor = term, scaleFactor
		self.isUnknown = self.term.isUnknown

	@classmethod
	def fromToks(cls, s, p, toks):
		if len(toks)==2:
			return cls(toks[1], float(toks[0]))

		elif len(toks)==1:
			return cls(toks[0], 1)

		else:
			raise Exception("This can't happen")

	def __str__(self):
		if self.scaleFactor==1:
			return str(self.term)
		else:
			return "%s %s"%(formatScaleFactor(self.scaleFactor), self.term)

	def __repr__(self):
		return "R(%s ; %s)"%(repr(self.scaleFactor), repr(self.term))

	def getSI(self):
		"""returns a pair of a numeric factor and a dict mapping SI units to
		their powers.
		"""
		factor, siPowers = self.term.getSI()
		return factor*self.scaleFactor, siPowers


def _buildTerm(s, pos, toks):
	"""a parseAction for terms, making trees out of parse lists 
	left-associatively.
	"""
	toks = list(toks)
	curOperand = toks.pop(0)
	while len(toks)>1:
		curOperand = Term.fromToks(s, pos, [curOperand, toks[0], toks[1]])
		del toks[:2]
	return curOperand


def evalAll(s, p, toks):
	"""a parse action evaluating the whole match as a python expression.

	Obviously, this should only be added to carefully screened nonterminals.
	"""
	return eval("".join(str(tok) for tok in toks))


class getUnitGrammar(utils.CachedResource):
	"""the grammar to parse VOUnits.

	After initialization, the class has a "symbols" dictionary containing
	the individual nonterminals.
	"""
	@classmethod
	def impl(cls):
		from gavo.imp.pyparsing import (Word, Literal, Regex, 
			Optional, ZeroOrMore, alphas,
			Suppress, Forward, White)

		with utils.pyparsingWhitechars(''):
			unit_atom = Word(alphas).addParseAction(UnitNode.fromToks)
			unit_atom.setName("atomic unit")
			quoted_unit_atom = ("'" + Word(alphas) + "'"
				).addParseAction(QuotedUnitNode.fromToks)
			quoted_unit_atom.setName("quoted atomic unit")

			OPEN_P = Literal('(')
			CLOSE_P = Literal(')')
			SIGN = Literal('+') | Literal('-')
			FUNCTION_NAME = Word(alphas)
			UNSIGNED_INTEGER = Word("01234567890")
			SIGNED_INTEGER = SIGN + UNSIGNED_INTEGER
			FLOAT = Regex(r"[+-]?([0-9]+(\.[0-9]*)?)")
			VOFLOAT = Regex(r"0.[0-9]+([eE][+-]?[0-9]+)?"
				"|[1-9][0-9]*(\.[0-9]+)?([eE][+-]?[0-9]+)?")

			integer = SIGNED_INTEGER | UNSIGNED_INTEGER
			power_operator = Literal('**')
			multiplication_operator = Literal(".")
			division_operator = Literal("/")
			numeric_power = (integer 
				| OPEN_P + integer + CLOSE_P 
				| OPEN_P + FLOAT + CLOSE_P 
				| OPEN_P + integer + '/'
					+ UNSIGNED_INTEGER.addParseAction(lambda s, p, t: t[0]+".") 
					+ CLOSE_P)
			numeric_power.setParseAction(evalAll)

			pow_10 = Literal("10") + power_operator + numeric_power
			scale_factor = (pow_10 | VOFLOAT).setParseAction(evalAll)

			any_unit_atom = unit_atom | quoted_unit_atom 
			factor = (any_unit_atom 
				+ Optional( Suppress(power_operator) + numeric_power )
				).addParseAction(Factor.fromToks)

			complete_expression = Forward()
			function_application = (FUNCTION_NAME +
					Suppress(OPEN_P) + complete_expression + Suppress(CLOSE_P))
			function_application.addParseAction(FunctionApplication.fromToks)

			unit_expression = (
				Suppress(OPEN_P) + complete_expression + Suppress(CLOSE_P)
				| ( factor 
					^ function_application ))

			product_of_units = (unit_expression 
					+ ZeroOrMore(multiplication_operator + unit_expression)
				).setParseAction(_buildTerm)

			complete_expression << (
				product_of_units + Optional(division_operator + unit_expression) )
			complete_expression.setParseAction(Term.fromToks)

			input = (Optional(scale_factor) 
				+ Optional(Suppress(White()))
				+ complete_expression
				).setParseAction(Expression.fromToks)

			cls.symbols = locals()
			return input

	@classmethod
	def enableDebuggingOutput(cls):
		"""(not user-servicable)
		"""
		from gavo.imp.pyparsing import ParserElement
		for name, sym in cls.symbols.iteritems():
			if isinstance(sym, ParserElement):
				sym.setDebug(True)
				sym.setName(name)


def parseUnit(unitStr, unitGrammar=getUnitGrammar()):
	try:
		return utils.pyparseString(unitGrammar, unitStr, parseAll=True)[0]
	except pyparsing.ParseException, msg:
		raise utils.logOldExc(
			BadUnit("%s at col. %d"%(repr(unitStr), msg.column)))


def computeConversionFactor(unitStr1, unitStr2):
	"""returns the factor needed to get from quantities given in unitStr1
	to unitStr2.

	Both must be given in VOUnits form.

	This function may raise a BadUnit if one of the strings are
	malformed, or an IncompatibleUnit exception if the units don't have
	the same SI base.

	If the function is successful, unitStr1 = result*unitStr2
	"""
	if unitStr1==unitStr2:
		return 1
	factor1, powers1 = parseUnit(unitStr1).getSI()
	factor2, powers2 = parseUnit(unitStr2).getSI()
	if powers1!=powers2:
		raise IncompatibleUnits("%s and %s do not have the same SI base"%(
			unitStr1, unitStr2))
	
	# tuples as keys in powers come from non-polynomial function
	# applications; in such cases, multiplication is not good enough
	# for conversions, and thus we give up.
	for u in powers1.iterkeys():
		if isinstance(u, tuple):
			raise IncompatibleUnits("%s has a non-polynomial function. No"
				" conversion by multiplication possible"%(unitStr1))
	for u in powers2.iterkeys():
		if isinstance(u, tuple):
			raise IncompatibleUnits("%s has a non-polynomial function. No"
				" conversion by multiplication possible"%(unitStr2))

	return factor1/factor2


def computeColumnConversions(newColumns, oldColumns):
	"""returns a dict of conversion factors between newColumns and oldColumns.
	
	Both arguments are iterables of columns.

	For every column in newColumn, the function sees if the units of
	newColumn and oldColumn match.  If they don't, compute a conversion
	factor to be multiplied to oldColumns values to make them newColumns
	values and add it to the result dict.

	The function raises a DataError if a column in newColumns has no
	match in oldColumns.
	"""
	res = {}
	for newCol in newColumns:
		if not newCol.name in oldColumns:
			raise utils.DataError(
				"Request for column %s from %s cannot be satisfied in %s"%(
					newCol.name, oldColumns, newColumns))
		oldCol = oldColumns.getColumnByName(newCol.name)
		try:
			if newCol.unit!=oldCol.unit:
				res[newCol.name] = computeConversionFactor(oldCol.unit, newCol.unit)
		except BadUnit:  # we ignore bad units, assume they'll be handled by
			# valuemappers.
			pass
	return res


if __name__=="__main__":
	getUnitGrammar.enableDebuggingOutput()
	g = getUnitGrammar()
	res = g.parseString("log(Hz)", parseAll=True)[0]
	print res
