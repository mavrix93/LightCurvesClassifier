"""
A (quite trivial) grammar that iterates over lists of dicts.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from gavo import base
from gavo.grammars.common import Grammar, RowIterator


class ListIterator(RowIterator):
	def __init__(self, *args, **kwargs):
		RowIterator.__init__(self, *args, **kwargs)
		self.recNo = 0
		if self.grammar.asPars:
			self.sourceRow = self.sourceToken[0]

	def _iterRows(self):
		if self.grammar.asPars:
			return
		self.recNo = 1
		for rec in self.sourceToken:
			res = rec.copy()
			yield res
			self.recNo += 1

	def getLocator(self):
		return "List, index=%d"%self.recNo


class DictlistGrammar(Grammar):
	"""A grammar that "parses" from lists of dicts.

	Actually, it will just return the dicts as they are passed.  This is
	mostly useful internally, though it might come in handy in custom code.
	"""
	name_ = "dictlistGrammar"
	rowIterator = ListIterator

	_asPars = base.BooleanAttribute("asPars", default=False, description=
		"Just return the first item of the list as parameters row and exit?")
