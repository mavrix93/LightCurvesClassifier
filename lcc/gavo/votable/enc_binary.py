"""
Binary VOTable encoding.
"""

#c Copyright 2008-2016, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import datetime #noflake: used in generated code
import struct

from gavo import utils           #noflake: used by generated code
from gavo.utils import pgsphere  #noflake: used by generated code
from gavo.votable import coding
from gavo.votable import common


floatNaN = struct.pack("!f", common.NaN)
doubleNaN = struct.pack("!d", common.NaN)


def _getArrayShapingCode(field, padder):
	"""returns common code for almost all array serialization.

	Field must describe an array (as opposed to a single value).

	padder must be python-source for whatever is used to pad
	arrays that are too short.
	"""
	base = [
		"if val is None: val = []"]
	if field.hasVarLength():
		return base+["tokens.append(struct.pack('!i', len(val)))"]
	else:
		return base+["val = coding.trim(list(val), %s, %s)"%(
			field.getLength(), padder)]


def _addNullvalueCode(field, nullvalue, src):
	"""adds code to let null values kick in a necessary.
 
	nullvalue here has to be a ready-made *python* literal.  Take care
	when passing in user supplied values here.
	"""
	if nullvalue is None:
		action = ("  raise common.BadVOTableData('None passed for field"
			" that has no NULL value', None, '%s', hint='Integers in VOTable"
			" have no natural serializations for missing values.  You need to"
			" define one using values null to allow for NULL in integer columns')"
			)%field.getDesignation()
	else:
		action = "  tokens.append(%s)"%nullvalue
	return [
		"if val is None:",
		action,
		"else:"
		]+coding.indentList(src, "  ")


def _makeBooleanEncoder(field):
	return [
		"if val is None:",
		"  tokens.append('?')",
		"elif val:",
		"  tokens.append('1')",
		"else:",
		"  tokens.append('0')",
	]


def _makeBitEncoder(field, allowNULL=False):
	# bits and bit arrays are just (possibly long) integers
	# length may be None for var length.
	length = field.getLength()
	if allowNULL:
		src = [
			"if val is None:"
			"  tokens.append('\\0\\0\\0\\0')",]
	else:
		src = [
			"if val is None:",
			"  raise common.BadVOTableData('Bits have no NULL value', None,",
			"    '%s')"%field.getDesignation(),]

	src.extend([
		"else:",
		"  tmp = []",
		"  curByte, rest = val%256, val//256",
		"  while curByte:",
		"    tmp.append(chr(curByte))",
		"    curByte, rest = rest%256, rest//256",
		"  if not tmp:",   # make sure we leave somthing even for 0
		"    tmp.append(chr(0))",
		"  tmp.reverse()",])

	if length!=1:  # this not just a single bit
		if length is None:  # variable length: dump number of bits
			src.extend([
				"  tokens.append(struct.pack('!i', len(tmp)*8))"])
		else:  # crop/expand as necesary
			numBytes = int(length)//8+(not not int(length)%8)
			src.extend([
				"  if len(tmp)<%d: tmp = [chr(0)]*(%d-len(tmp))+tmp"%(
					numBytes, numBytes),
				"  if len(tmp)>%d: tmp = tmp[-%d:]"%(numBytes, numBytes)])
	
	src.extend([
		"  tokens.append(struct.pack('%ds'%len(tmp), ''.join(tmp)))"])
	return src


def _generateFloatEncoderMaker(fmtCode, nullName):
	def makeFloatEncoder(field):
		return [
			"if val is None:",
			"  tokens.append(%s)"%nullName,
			"else:",
			"  tokens.append(struct.pack('%s', val))"%fmtCode]
	return makeFloatEncoder


def _generateComplexEncoderMaker(fmtCode, singleNull):
	def makeComplexEncoder(field):
		return [
			"if val is None:",
			"  tokens.append(%s+%s)"%(singleNull, singleNull),
			"else:",
			"  tokens.append(struct.pack('%s', val.real, val.imag))"%fmtCode]
	return makeComplexEncoder


def _generateIntEncoderMaker(fmtCode):
	def makeIntEncoder(field):
		nullvalue = coding.getNullvalue(field, int)
		if nullvalue is not None:
			nullvalue = repr(struct.pack(fmtCode, int(nullvalue)))
		return _addNullvalueCode(field, nullvalue,[
			"tokens.append(struct.pack('%s', val))"%fmtCode])
	return makeIntEncoder


def _makeUnsignedByteEncoder(field):
# allow these to come from strings, too (db type bytea)
	nullvalue = coding.getNullvalue(field, int)
	if nullvalue is not None:
		nullvalue = repr(struct.pack("B", int(nullvalue)))
	return _addNullvalueCode(field, nullvalue,[
		"if isinstance(val, int):",
		"  tokens.append(struct.pack('B', val))",
		"else:",
		"  tokens.append(struct.pack('c', val[:1]))"])


def _makeCharEncoder(field):
	nullvalue = coding.getNullvalue(field, lambda _: True)
	if nullvalue is not None:
		nullvalue = repr(struct.pack("c", str(nullvalue)))

	return _addNullvalueCode(field, nullvalue, [
		"tokens.append(struct.pack('c', str(val)))"])

def _makeUnicodeCharEncoder(field):
	nullvalue = coding.getNullvalue(field, lambda _: True)
	if nullvalue is not None:
		coded = nullvalue.encode("utf-16be")
		nullvalue = repr(struct.pack("%ds"%len(coded), coded))
	return _addNullvalueCode(field, nullvalue, [
		"coded = val.encode('utf-16be')",
		"tokens.append(struct.pack('%ds'%len(coded), coded))"])


def _makeCharArrayEncoder(field):
# special handling for character arrays, since we don't want to treat
# those as character arrays in python.
	if field.isMultiDim():
		# String arrays -- implement some other day
		raise NotImplementedError("Cannot do string arrays yet.  Could you"
			" help out?")

	nullvalue = coding.getNullvalue(field, lambda _: True, default="")
	src = []

	if field.datatype=="char":
		src.extend([
			'if isinstance(val, unicode):',
			'  val = val.encode("ascii", "replace")'])

	if field.hasVarLength():
		src.extend(common.getXtypeCode(field))
		src.append("tokens.append(struct.pack('!i', len(val)))")
		if nullvalue is None:
			nullvalue = repr('\0\0\0\0')
		else:
			# The str in the next line allows nullvalue to be unicode (containing
			# ascii, of course)
			nullvalue = repr(struct.pack("!i%ds"%len(nullvalue), 
				len(nullvalue), str(nullvalue)))
	else:
		src.append("val = coding.trimString(val, %d)"%field.getLength())
		if nullvalue is not None:
			nullvalue = repr(struct.pack("%ds"%field.getLength(),
				str(coding.trimString(nullvalue, field.getLength()))))
		# no predefined nullvalue for constant-length strings

	if field.datatype=="unicodeChar":
		src.append("val = val.encode('utf-16be')")

	src.append("tokens.append(struct.pack('%ds'%len(val), val))")
	return _addNullvalueCode(field, nullvalue, src)


_encoders = {
		"boolean": _makeBooleanEncoder,
		"bit": _makeBitEncoder,
		"unsignedByte": _makeUnsignedByteEncoder,
		"short": _generateIntEncoderMaker('!h'),
		"int": _generateIntEncoderMaker('!i'),
		"long": _generateIntEncoderMaker('!q'),
		"char": _makeCharEncoder,
		"unicodeChar": _makeUnicodeCharEncoder,
		"double": _generateFloatEncoderMaker("!d", "doubleNaN"),
		"float": _generateFloatEncoderMaker("!f", "floatNaN"),
		"doubleComplex": _generateComplexEncoderMaker("!dd", "doubleNaN"),
		"floatComplex": _generateComplexEncoderMaker("!ff", "floatNaN"),
}

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
			
	return _getArrayShapingCode(field, padder)+src
			

def getLinesFor(field):
	"""returns a sequence of python source lines to encode values described
	by field into tabledata.
	"""
	if field.isScalar():
		return _encoders[field.datatype](field)
	else:
		return _getArrayEncoderLines(field)


def getPostamble(tableDefinition):
	return [
		"return ''.join(tokens)"]


def getGlobals(tableDefinition):
	return globals()
