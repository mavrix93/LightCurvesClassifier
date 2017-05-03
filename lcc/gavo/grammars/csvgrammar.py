"""
A grammar using python's csv module to parse files.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from __future__ import with_statement

import csv

from gavo import base
from gavo.grammars.common import Grammar, FileRowIterator, FileRowAttributes


class CSVIterator(FileRowIterator):
	def __init__(self, grammar, sourceToken, **kwargs):
		FileRowIterator.__init__(self, grammar, sourceToken, **kwargs)
		consArgs = {
			"delimiter": str(self.grammar.delimiter),
			"fieldnames": self.grammar.names,
			"skipinitialspace": self.grammar.strip,
		}
		self.csvSource = csv.DictReader(self.inputFile, **consArgs)
			
	def _iterRows(self):
		return self.csvSource

	def getLocator(self):
		return "line %s"%self.csvSource.line_num


class CSVGrammar(Grammar, FileRowAttributes):
	"""A grammar that uses python's csv module to parse files.

	Note that these grammars by default interpret the first line of
	the input file as the column names.  When your files don't follow
	that convention, you *must* give names (as in ``names='raj2000,
	dej2000, magV'``), or you'll lose the first line and have silly
	column names.

	CSVGrammars currently do not support non-ASCII inputs.
	Contact the authors if you need that.
	"""
	name_ = "csvGrammar"

	_delimiter = base.UnicodeAttribute("delimiter", 
		description="CSV delimiter", default=",", copyable=True)

	_names = base.StringListAttribute("names", default=None,
		description="Names for the parsed fields, in sequence of the"
		" comma separated values.  The default is to read the field names"
		" from the first line of the csv file.  You can use macros here,"
		r" e.g., \\colNames{someTable}.", expand=True,
		copyable=True)

	_strip = base.BooleanAttribute("strip", default=False,
		description="If True, whitespace immediately following a delimiter"
		" is ignored.", copyable=True)

	rowIterator = CSVIterator
