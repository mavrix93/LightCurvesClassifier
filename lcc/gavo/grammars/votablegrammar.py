"""
A grammar taking its rows from a VOTable.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


# XXX TODO: return PARAMs as the docrow

import gzip
import itertools

from gavo import base
from gavo import votable
from gavo.base import valuemappers
from gavo.grammars import common


class VOTableRowIterator(common.RowIterator):
	"""An iterator returning rows of the first table within a VOTable.
	"""
	def __init__(self, grammar, sourceToken, **kwargs):
		common.RowIterator.__init__(self, grammar, sourceToken, **kwargs)
		if self.grammar.gunzip:
			inF = gzip.open(sourceToken)
		else:
			inF = open(sourceToken)
		self.rowSource = votable.parse(inF).next()

	def _iterRows(self):
		nameMaker = valuemappers.VOTNameMaker()
		fieldNames = [nameMaker.makeName(f) 
			for f in self.rowSource.tableDefinition.
					iterChildrenOfType(votable.V.FIELD)]
		for row in self.rowSource:
			yield dict(itertools.izip(fieldNames, row))
		self.grammar = None

	def getLocator(self):
		return "VOTable file %s"%self.sourceToken


class VOTableGrammar(common.Grammar):
	"""A grammar parsing from VOTables.

	Currently, the PARAM fields are ignored, only the data rows are
	returned.

	voTableGrammars result in typed records, i.e., values normally come
	in the types they are supposed to have.
	"""
	name_ = "voTableGrammar"
	_gunzip = base.BooleanAttribute("gunzip", description="Unzip sources"
		" while reading?", default=False)

	rowIterator = VOTableRowIterator
