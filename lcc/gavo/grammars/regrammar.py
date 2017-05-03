"""
A grammar splitting the input file into lines and lines into records
using REs.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import re

from gavo import base
from gavo.grammars.common import (
	Grammar, FileRowIterator, FileRowAttributes, REAttribute)


class REIterator(FileRowIterator):
	"""is an iterator based on regular expressions.
	"""
	chunkSize = 8192

	def _iterInRecords(self):
		for i in range(self.grammar.topIgnoredLines):
			self.inputFile.readline()
			self.curLine += 1

		curPos = 0
		splitPat = self.grammar.recordSep
		buffer = ""
		while True:
			mat = splitPat.search(buffer, curPos)
			if not mat:  # no match, fetch new stuff.
				newStuff = self.inputFile.read(self.chunkSize)
				if not newStuff:  # file exhausted
					break
				buffer = buffer[curPos:]+newStuff
				curPos = 0
				if self.grammar.commentPat:
					buffer = self.grammar.commentPat.sub("", buffer)
				continue
			res = buffer[curPos:mat.start()]
			yield res.strip()
			curPos = mat.end()
			self.curLine += res.count("\n")
		# yield stuff left if there's something left
		res = buffer[curPos:].strip()
		if res:
			yield res

	def _iterRows(self):
		for rawRec in self._iterInRecords():
			try:
				res = self._makeRec(rawRec)
			except base.SkipThis:
				continue
			yield res
		self.inputFile.close()
		self.grammar = None
	
	def _makeRec(self, inputLine):
		if self.grammar.recordCleaner:
			cleanMat = self.grammar.recordCleaner.match(inputLine)
			if not cleanMat:
				raise base.SourceParseError("'%s' does not match cleaner"%inputLine,
					source=str(self.sourceToken))
			inputLine = " ".join(cleanMat.groups())

		if not inputLine.strip():
			raise base.SkipThis("Empty line")

		fields = self.grammar.fieldSep.split(inputLine)
		if not self.grammar.lax and len(fields)!=len(self.grammar.names):
			raise base.SourceParseError("Only %d fields found, expected %d"%(
					len(fields), len(self.grammar.names)),
				source=self.sourceToken,
				location=self.getLocator(),
				hint="reGrammars need the same number of input fields in each line,"
				" and that number has to match the number of tokens in the names"
				" attribute")
		return dict(zip(self.grammar.names, fields))

	def getLocator(self):
		return "line %d"%self.curLine


class REGrammar(Grammar, FileRowAttributes):
	"""A grammar that builds rowdicts from records and fields specified
	via REs separating them.

	There is also a simple facility for "cleaning up" records.  This can be
	used to remove standard shell-like comments; use 
	``recordCleaner="(?:#.*)?(.*)"``.
	"""
	name_ = "reGrammar"

	rowIterator = REIterator

	_til = base.IntAttribute("topIgnoredLines", default=0, description=
		"Skip this many lines at the top of each source file.")
	_recordSep = REAttribute("recordSep", default=re.compile("\n"), 
		description="RE for separating two records in the source.")
	_fieldSep = REAttribute("fieldSep", default=re.compile(r"\s+"), 
		description="RE for separating two fields in a record.")
	_commentPat = REAttribute("commentPat", default=None,
		description="RE inter-record material to be ignored (note: make this"
		" match the entire comment, or you'll get random mess from partly-matched"
		" comments.  Use '(?m)^#.*$' for beginning-of-line hash-comments.")
	_recordCleaner = REAttribute("recordCleaner", default=None,
		description="A regular expression matched against each record."
			" The matched groups in this RE are joined by blanks and used"
			" as the new pattern.  This can be used for simple cleaning jobs;"
			" However, records not matching recordCleaner are rejected.")
	_names = base.StringListAttribute("names", description=
		"Names for the parsed fields, in matching sequence.  You can"
		r" use macros here, e.g., \\colNames{someTable}.", expand=True)
	_lax = base.BooleanAttribute("lax", description="allow more or less"
		" fields in source records than there are names", default=False)
