"""
A grammar reading from (fixed-record) binary files.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import re
import struct

from gavo import base
from gavo import utils
from gavo.grammars.common import Grammar, FileRowIterator
from gavo.imp import pyparsing
from gavo.utils import misctricks


class BinaryRowIterator(FileRowIterator):
	"""A row iterator reading from binary files.
	"""
	def _iterUnarmoredRecords(self):
		while True:
			data = self.inputFile.read(self.grammar.fieldDefs.recordLength)
			if data=="":
				return
			yield data

	def _iterInRecords(self):
		self.inputFile.read(self.grammar.skipBytes)
		if self.grammar.armor is None:
			return self._iterUnarmoredRecords()
		elif self.grammar.armor=="fortran":
			return misctricks.iterFortranRecs(self.inputFile)
		else:
			assert False

	def _iterRows(self):
		fmtStr = self.grammar.fieldDefs.structFormat
		fieldNames = self.grammar.fieldDefs.fieldNames
		try:
			for rawRec in self._iterInRecords():
				yield dict(zip(fieldNames, struct.unpack(fmtStr, rawRec)))
		except Exception, ex:
			raise base.ui.logOldExc(base.SourceParseError(str(ex), 
				location="byte %s"%self.inputFile.tell(),
				source=str(self.sourceToken)))


def _getFieldsGrammar():
	with utils.pyparsingWhitechars(" \n\t\r"):
		identifier = pyparsing.Regex(utils.identifierPattern.pattern[:-1]
			).setName("identifier")
		formatCode = pyparsing.Regex("\d+s|[bBhHiIqQfd]"
			).setName("fieldSpec")
		field = ( identifier("identifier")
			+ pyparsing.Suppress(pyparsing.Literal("("))
			+ formatCode("formatCode")
			+ pyparsing.Suppress(pyparsing.Literal(")"))).setParseAction(
				lambda s, p, t: dict(t))
		return pyparsing.OneOrMore(field)+pyparsing.StringEnd()

		
class BinaryRecordDef(base.Structure):
	"""A definition of a binary record.

	A binary records consists of a number of binary fields, each of which
	is defined by a name and a format code.  The format codes supported
	here are a subset of what python's struct module supports.  The
	widths given below are for big, little, and packed binfmts.
	For native (which is the default), it depends on your platform.

	* <number>s -- <number> characters making up a string
	* b,B -- signed and unsigned byte (8 bit)
	* h,H -- signed and unsigned short (16 bit)
	* i,I -- signed and unsigned int (32 bit)
	* q,Q -- signed and unsigned long (64 bit)
	* f,d -- float and double.

	The content of this element gives the record structure in the format
	<name>(<code>){<whitespace><name>(<code>)} where <name> is a c-style
	identifier.
	"""
	name_ = "binaryRecordDef"

	_fieldsGrammar = _getFieldsGrammar()

	_binfmt = base.EnumeratedUnicodeAttribute("binfmt",
		default="native", 
		validValues=["big", "little", "native", "packed"],
		description="Binary format of the input data; big and little stand"
			" for msb first and lsb first, and"
			" packed is like native except no alignment takes place.")

	_fields = base.DataContent(description="The enumeration of"
		" the record fields.")

	_binfmtToStructCode = {
		"native": "",
		"packed": "=",
		"big": ">",
		"little": "<"}

	def completeElement(self, ctx):
		try:
			parsedFields = utils.pyparseString(self._fieldsGrammar, self.content_)
		except pyparsing.ParseBaseException, ex:
			raise base.ui.logOldExc(base.LiteralParseError("binaryRecordDef", 
				re.sub("\s+", " ", self.content_),
				pos=str(ex.loc), hint="The parser said: '%s'"%str(ex)))
# XXX TODO: Position should probably be position during XML parse.
# Fix when we have source positions on parsed elements.
		self.structFormat = (self._binfmtToStructCode[self.binfmt]+
			str("".join(f["formatCode"] for f in parsedFields)))
		self.recordLength = struct.calcsize(self.structFormat)
		self.fieldNames = tuple(f["identifier"] for f in parsedFields)
		self._completeElementNext(BinaryRecordDef, ctx)


class BinaryGrammar(Grammar):
	"""A grammar that builds rowdicts from binary data.

	The grammar expects the input to be in fixed-length records. 
	the actual specification of the fields is done via a binaryRecordDef
	element.
	"""
	name_ = "binaryGrammar"
	rowIterator = BinaryRowIterator

	_til = base.IntAttribute("skipBytes", 
		default=0, 
		description="Number of bytes to skip before parsing records.")
	
	_fdefs = base.StructAttribute("fieldDefs",
		description="Definition of the record.",
		childFactory=BinaryRecordDef)

	_armoring = base.EnumeratedUnicodeAttribute("armor",
		default=None,
		validValues=["fortran"],
		description="Record armoring; by default it's None meaning the"
			" data was dumped to the file sequentially.  Set it to fortran"
			" for fortran unformatted files (4 byte length before and after"
			" the payload).")
