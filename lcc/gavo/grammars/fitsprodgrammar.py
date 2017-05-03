"""
A grammar to parse from primary FITS headers.

This grammar will return exactly one row per source.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import gzip
import re

from gavo import base
from gavo.grammars.common import Grammar, RowIterator, MapKeys
from gavo.utils import fitstools


class FITSProdIterator(RowIterator):
	def _iterRows(self):
		if self.grammar.qnd:
			return self._parseFast()
		else:
			return self._parseSlow()
	
	def _hackBotchedCard(self, card, res):
		"""tries to make *anything* from a card pyfits doesn't want to parse.

		In reality, I'm just trying to cope with oversized keywords.
		"""
		mat = re.match(r"([^\s=]*)\s*=\s*([^/]+)", card._cardimage)
		if mat:
			res[mat.group(1)] = mat.group(2).strip()
		else: # Card beyond recognition, ignore
			pass

	def _buildDictFromHeader(self, header):
		res = {}
		for card in header.ascard:
			try:
				res[card.key.replace("-", "_")] = card.value
			except ValueError:
				self._hackBotchedCard(card, res)
		res["header_"] = header
		if self.grammar.hdusField:
			res[self.grammar.hdusField] = fitstools.openFits(self.sourceToken)
		return self.grammar.mapKeys.doMap(res)
	
	def _parseFast(self):
		fName = self.sourceToken
		if fName.endswith(".gz"):
			f = gzip.open(fName)
		else:
			f = open(fName)
		header = fitstools.readPrimaryHeaderQuick(f, 
			maxHeaderBlocks=self.grammar.maxHeaderBlocks)
		f.close()
		yield self._buildDictFromHeader(header)

	def _parseSlow(self):
		fName = self.sourceToken
		hdus = fitstools.openFits(fName)
		header = hdus[int(self.grammar.hdu)].header
		hdus.close()
		yield self._buildDictFromHeader(header)
	
	def getLocator(self):
		return self.sourceToken


class FITSProdGrammar(Grammar):
	r"""A grammar that returns FITS-headers as dictionaries.

	This is the grammar you want when one FITS file corresponds to one
	row in the destination table.

	The keywords of the grammar record are the cards in the primary
	header (or some other hdu using the same-named attribute).  "-" in
	keywords is replaced with an underscore for easier @-referencing.
	You can use a mapKeys element to effect further name cosmetics.

	The original header is preserved as the value of the header\_ key.  This
	is mainly intended for use WCS use, as in ``pywcs.WCS(@header_)``.

	If you have more complex structures in your FITS files, you can get access
	to the pyfits HDU using the hdusField attribute.  With
	``hdusField="_H"``, you could say things like ``@_H[1].data[10][0]``
	to get the first data item in the tenth row in the second HDU.
	"""
	name_ = "fitsProdGrammar"

	_qnd = base.BooleanAttribute("qnd", default=True, description=
		"Use a hack to read the FITS header more quickly.  This only"
		" works for the primary HDU")
	_hduIndex = base.IntAttribute("hdu", default=0,
		description="Take the header from this HDU")
	_mapKeys = base.StructAttribute("mapKeys", childFactory=MapKeys,
		default=None, copyable=True, description="Prescription for how to"
		" map header keys to grammar dictionary keys")
	_hdusAttr = base.UnicodeAttribute("hdusField", default=None,
		description="If set, the complete pyfits HDU list for the FITS"
		" file is returned in this grammar field.", copyable="True")
	_maxHeaderBlocks = base.IntAttribute("maxHeaderBlocks",
		default=40, copyable=True, description="Stop looking for"
		" FITS END cards and raise an error after this many blocks."
		" You may need to raise this for people dumping obscene amounts"
		" of data or history into headers.")

	rowIterator = FITSProdIterator

	def onElementComplete(self):
		if self.mapKeys is None:
			self.mapKeys = base.makeStruct(MapKeys)
		self._onElementCompleteNext(FITSProdGrammar)
