"""
A grammar that just splits the source into input lines and then
lets you name character ranges.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from __future__ import with_statement


from gavo import base
from gavo import utils
from gavo.grammars.common import Grammar, FileRowIterator, FileRowAttributes
from gavo.imp import pyparsing


class SplitLineIterator(FileRowIterator):
	def __init__(self, grammar, sourceToken, **kwargs):
		FileRowIterator.__init__(self, grammar, sourceToken, **kwargs)
		for i in range(self.grammar.topIgnoredLines):
			self.inputFile.readline()
		self.lineNo = self.grammar.topIgnoredLines

	def _iterRows(self):
		while True:
			self.lineNo += 1
			inputLine = self.inputFile.readline()
			if not inputLine:
				break

			if (self.grammar.commentIntroducer is not base.NotGiven
					and inputLine.startswith(self.grammar.commentIntroducer)):
				continue

			res = self._parse(inputLine)
			yield res
			self.recNo += 1

		self.inputFile.close()
		self.grammar = None
	
	def _parse(self, inputLine):
		res = {}
		try:
			for key, slice in self.grammar.colRanges.iteritems():
				res[key] = inputLine[slice].strip()
		except IndexError:
			raise base.ui.logOldExc(base.SourceParseError("Short line", inputLine, 
				self.getLocator(), self.sourceToken))
		return res

	def getLocator(self):
		return "line %d"%self.lineNo


class ColRangeAttribute(base.UnicodeAttribute):
	"""A range of indices.

	Ranges can be specified as either <int1>-<int2>, just <int>
	(which is equivalent to <int>-<int>), or as half-open ranges 
	(<int>- or -<int>) Ranges are, contrary to
	python slices, inclusive on both sides, and start counting
	from one.
	"""
	def parse(self, value):
		if isinstance(value, slice):
			#	we're already parsed
			return value

		try:
			if "-" in value:
				startLit, endLit = value.split("-")
				start, end = None, None
				if startLit.strip():
					start = int(startLit)-1
				if endLit.strip():
					end = int(endLit)
				return slice(start, end)
			else:
				col = int(value)
				return slice(col-1, col)
		except ValueError:
			raise base.ui.logOldExc(
				base.LiteralParseError("colRanges", value, hint="A column range,"
				" (either int1-int2 or just an int) is expected here."))


class ColumnGrammar(Grammar, FileRowAttributes):
	"""A grammar that builds rowdicts out of character index ranges.

	This works by using the colRanges attribute like <col key="mag">12-16</col>,
	which will take the characters 12 through 16 inclusive from each input
	line to build the input column mag.

	As a shortcut, you can also use the colDefs attribute; it contains
	a string with of the form {<key>:<range>}, i.e.,
	a whitespace-separated list of colon-separated items of key and range
	as accepted by cols, e.g.::
		
		<colDefs>
			a: 3-4
			_u: 7
		</colDefs>
	"""
	name_ = "columnGrammar"

	_til = base.IntAttribute("topIgnoredLines", default=0, description=
		"Skip this many lines at the top of each source file.",
		copyable=True)
	_cols = base.DictAttribute("colRanges", description="Mapping of"
		" source keys to column ranges.", itemAttD=ColRangeAttribute("col"),
		copyable=True)
	_colDefs = base.ActionAttribute("colDefs", description="Shortcut"
		" way of defining cols", methodName="_parseColDefs")
	_commentIntroducer = base.UnicodeAttribute("commentIntroducer",
		default=base.NotGiven, description="A character sequence"
		" that, when found at the beginning of a line makes this line"
		" ignored", copyable=True)

	def _getColDefGrammar(self):
		with utils.pyparsingWhitechars("\n\t\r "):
			intLiteral = pyparsing.Word(pyparsing.nums)
			# need to manually swallow whitespace after literals
			blindWhite = pyparsing.Suppress(pyparsing.Optional(pyparsing.White()))
			dash = blindWhite + pyparsing.Literal("-") + blindWhite

			range = pyparsing.Combine(
				dash + blindWhite + intLiteral
				| intLiteral + pyparsing.Optional(dash + pyparsing.Optional(intLiteral)))
			range.setName("Column range")

			identifier = pyparsing.Regex(utils.identifierPattern.pattern[:-1])
			identifier.setName("Column key")

			clause = (identifier + pyparsing.Literal(":") + blindWhite + range
				).addParseAction(lambda s,p,t: (t[0], t[2]))
			colDefs = pyparsing.ZeroOrMore(clause)+pyparsing.StringEnd()
			# range.setDebug(True);identifier.setDebug(True);clause.setDebug(True)
			return colDefs

	def _parseColDefs(self, ctx):
		# the handler for colDefs -- parse shortcut colDefs
		try:
			for key, range in utils.pyparseString(self._getColDefGrammar(), 
					self.colDefs):
				self.colRanges[key] = self._cols.itemAttD.parse(range)
		except pyparsing.ParseException, ex:
			raise base.LiteralParseError("colDefs", self.colDefs,
				hint="colDefs is a whitespace-separated list of key:range pairs."
				" Your literal doesn't look like this, and here's what the"
				" parser had to complain: %s"%ex)

		
	rowIterator = SplitLineIterator
