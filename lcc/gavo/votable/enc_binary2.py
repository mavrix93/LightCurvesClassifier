"""
BINARY2 VOTable encoding.

BINARY2 is like BINARY, except every record is preceded by a mask which
columns are NULL.

We do not determine any nullvalues any more here.

Sorry for gratuituously peeking into the guts of enc_binary here.  But well,
it's family.
"""

#c Copyright 2008-2016, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import datetime                 #noflake: used by generated code
import struct

from gavo import utils          #noflake: used by generated code
from gavo.utils import pgsphere #noflake: used by generated code
from gavo.votable import coding
from gavo.votable import common
from gavo.votable import enc_binary


floatNaN = struct.pack("!f", common.NaN)
doubleNaN = struct.pack("!d", common.NaN)



def _makeBitEncoder(field):
	return enc_binary._makeBitEncoder(field, allowNULL=True)


def _generateIntEncoderMaker(fmtCode):
	def makeIntEncoder(field):
		return [
			"if val is None:",
			"  val = 0",
			"tokens.append(struct.pack('%s', val))"%fmtCode]
	return makeIntEncoder


def _makeCharEncoder(field):
	return [
		"if val is None:",
		"  val = 0",
		"else:"
		"  val = ord(val)",
		"tokens.append(struct.pack('B', val))"]


def _makeUnicodeCharEncoder(field):
	return [
		"if val is None:",
		"  tokens.append('\\x00\\x00')",
		"else:",
		"	coded = val.encode('utf-16be')",
		"	tokens.append(struct.pack('%ds'%len(coded), coded))"]


def _makeUnsignedByteEncoder(field):
	return [
		"if isinstance(val, int):",
		"  tokens.append(struct.pack('B', val))",
		"elif val is None:",
		"  tokens.append('\xff')",
		"else:",
		"  tokens.append(struct.pack('c', val))"]


_encoders = {
		"boolean": enc_binary._makeBooleanEncoder,
		"bit": enc_binary._makeBitEncoder,
		"unsignedByte": _makeUnsignedByteEncoder,
		"short": _generateIntEncoderMaker('!h'),
		"int": _generateIntEncoderMaker('!i'),
		"long": _generateIntEncoderMaker('!q'),
		"char": _makeCharEncoder,
		"unicodeChar": _makeUnicodeCharEncoder,
		"double": enc_binary._generateFloatEncoderMaker("!d", "doubleNaN"),
		"float": enc_binary._generateFloatEncoderMaker("!f", "floatNaN"),
		"doubleComplex": enc_binary._generateComplexEncoderMaker(
			"!dd", "doubleNaN"),
		"floatComplex": enc_binary._generateComplexEncoderMaker("!ff", "floatNaN"),
}


def _makeCharArrayEncoder(field):
# special handling for character arrays, since we don't want to treat
# those as character arrays in python.
	if field.isMultiDim():
		# String arrays -- implement some other day
		raise NotImplementedError("Cannot do string arrays yet.  Could you"
			" help out?")

	if field.datatype=="unicodeChar":
		nullChar = "\\x00\\x00"
	else:
		nullChar = "\\x00"

	src = []

	if field.datatype=="char":
		src.extend([
			'if isinstance(val, unicode):',
			'  val = val.encode("ascii", "replace")'])

	if field.hasVarLength():
		src.extend(common.getXtypeCode(field))
		src.extend([
			"if not val:",
			"  tokens.append('\\0\\0\\0\\0')",
			"else:",
			"  tokens.append(struct.pack('!i', len(val)))",
		])
	else:
		src.extend([
			"if not val:",
			"  tokens.append('%s')"%(nullChar*field.getLength()),
			"else:",
			"  val = coding.trimString(val, %d, '\\0')"%field.getLength(),
		])
		
	if field.datatype=="unicodeChar":
		src.append("  val = val.encode('utf-16be')")
	src.append("  tokens.append(struct.pack('%ds'%len(val), val))")

	return src


def _getArrayEncoderLines(field):
	"""returns python lines to encode array values of field.
	"""
	type = field.datatype

	# bit array literals are integers, same as bits
	if type=="bit":
		return _makeBitEncoder(field)

	if type=="char" or type=="unicodeChar":
		return _makeCharArrayEncoder(field)


	# Everything else can use some common array shaping code since value comes in
	# some kind of sequence.
	padder = '[None]'
	src = [ # Painful name juggling to avoid having to call functions.
		"fullTokens = tokens",
		"tokens = []",
		"if val is None:",
		"  arr = []",
		"else:",
		"  arr = val",
		"for val in arr:"
	]+coding.indentList(_encoders[field.datatype](field), "  ")

	src.extend([
		"fullTokens.append(''.join(tokens))",
		"tokens = fullTokens"])
			
	return enc_binary._getArrayShapingCode(field, padder)+src
			

def getLinesFor(field):
	"""returns a sequence of python source lines to encode values described
	by field into tabledata.
	"""
	if field.isScalar():
		return _encoders[field.datatype](field)
	else:
		return _getArrayEncoderLines(field)


def getPreamble(tableDefinition):
	return [
		"tokens.append(nullFlags.serializeFromRow(tableRow))"]


def getPostamble(tableDefinition):
	return [
		"return ''.join(tokens)"]


def getGlobals(tableDefinition):
	vars = globals().copy()
	vars["nullFlags"] = common.NULLFlags(len(tableDefinition.getFields()))
	return vars
