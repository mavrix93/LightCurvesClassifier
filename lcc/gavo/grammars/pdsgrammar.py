"""
A grammar wrapping pypds to parse files in the format of the planetary
data system (PDS).
"""

from gavo import base
from gavo.grammars.common import Grammar, RowIterator, MapKeys


class PDSRowIterator(RowIterator):
	"""an iterator for headers of PDS files.

	Each iterator just yields a single dictionary.
	"""
	def _iterRows(self):
		try:
			from pds.core.parser import Parser
			from pds.core.common import open_pds
		except ImportError:
			raise base.ReportableError("PDSGrammar needs the external PyPDS python"
				" package.  You can obtain it from"
				" git://github.com/RyanBalfanz/PyPDS.git or from the python"
				" package index.")
		yield Parser().parse(open_pds(self.sourceToken))


class PDSGrammar(Grammar):
	"""A grammar that returns labels of PDS documentes as rowdicts

	PDS is the file format of the Planetary Data System; the labels
	are quite like, but not quite like FITS headers.

	Extra care needs to be taken here since the values in the rawdicts
	can be complex objects (e.g., other labels).  It's likely that you
	will need constructs like ``@IMAGE["KEY"].

	Current versions of PyPDS also don't parse the values.  This is
	particularly insiduous because general strings are marked with " in PDS.
	When mapping those, you'll probably want a @KEY.strip('"').

	You'll need PyPDS to use this; there's no Debian package for that yet,
	so you'll have to do a source install from
	git://github.com/RyanBalfanz/PyPDS.git
	"""
	name_ = "pdsGrammar"

	_mapKeys = base.StructAttribute("mapKeys", childFactory=MapKeys,
		default=None, copyable=True, description="Prescription for how to"
		" map labels keys to grammar dictionary keys")

	rowIterator = PDSRowIterator

	def onElementComplete(self):
		if self.mapKeys is None:
			self.mapKeys = base.makeStruct(MapKeys)
		self._onElementCompleteNext(PDSGrammar)
