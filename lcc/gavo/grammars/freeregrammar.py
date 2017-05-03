"""
A grammar based on repeated application of REs
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import re

from gavo import base
from gavo.grammars import common
from gavo.grammars import regrammar


_onlyWhitespaceLeft = re.compile(r"\s*$")

class RowIterator(common.FileRowIterator):
	chunkSize = 8192

	def _iterRecords(self):
		curPos, buffer = 0, ""
		recPat = self.grammar.rowProduction
		while True:
			mat = recPat.match(buffer, curPos)
			if not mat:  # no match, fetch new stuff.
				newStuff = self.inputFile.read(self.chunkSize)
				if not newStuff:  # file exhausted
					break
				buffer = buffer[curPos:]+newStuff
				curPos = 0
				continue
			res = mat.group()
			yield res
			curPos = mat.end()
			self.curLine += res.count("\n")
		buffer = buffer[curPos:]
		if not _onlyWhitespaceLeft.match(buffer):
			raise common.ParseError("Junk at end of file", self.getLocator(),
				buffer)

	def _iterRows(self):
		for rawRec in self._iterRecords():
			try:
				res = self.grammar.parseRE.match(rawRec).groupdict()
				if self.grammar.stripTokens:
					res = dict((k, v.strip()) for k, v in res.iteritems())
				yield res
			except AttributeError:
				raise base.ui.logOldExc(
					common.ParseError("Malformed input, parseRE did not match.",
						self.getLocator(), rawRec))

	def getLocator(self):
		return "%s, line %d"%(self.sourceToken, self.curLine)


class FreeREGrammar(common.Grammar):
	"""A grammar allowing "free" regular expressions to parse a document.

	Basically, you give a rowProduction to match individual records in the
	document.  All matches of rowProduction will then be matched with
	parseRE, which in turn must have named groups.  The dictionary from
	named groups to their matches makes up the input row.

	For writing the parseRE, we recommend writing an element, using a
	CDATA construct, and taking advantage of python's "verbose" regular
	expressions.  Here's an example::

		<parseRE><![CDATA[(?xsm)^name::(?P<name>.*)
			^query::(?P<query>.*)
			^description::(?P<description>.*)\.\.
		]]></parseRE>
	"""
	name_ = "freeREGrammar"

	_rowProduction = regrammar.REAttribute("rowProduction", 
		default=re.compile(r"(?m)^.+$\n"), description="RE matching a complete"
		" record.")
	_parseRE = regrammar.REAttribute("parseRE", default=base.Undefined,
		description="RE containing named groups matching a record")
	_stripTokens = base.BooleanAttribute("stripTokens", default=False,
		description="Strip whitespace from result tokens?")
	rowIterator = RowIterator
