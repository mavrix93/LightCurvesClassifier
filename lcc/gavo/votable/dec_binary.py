"""
Coding and decoding from binary.
"""

#c Copyright 2008-2016, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import re #noflake: used by generated code
import struct #noflake: used by generated code

from gavo.votable import coding
from gavo.votable import common #noflake: used by generated code
from gavo.votable.model import VOTable


# literals for BINARY booleans
BINENCBOOL = {
	't': True,
	'T': True,
	'1': True,
	'f': False,
	'F': False,
	'0': False,
	'?': None,
}


def _addNullvalueCode(field, src, validator):
	"""adds code to catch nullvalues if required by field.

	validator must be a function returning a valid python literal for
	a nullvalue attribute or raise an exception.  This is security
	critical since whatever validator returns gets embedded into
	natively-run source code.
	"""
	nullvalue = coding.getNullvalue(field, validator)
	if nullvalue:
		src.extend([
			'if val==%s:'%validator(nullvalue),
			'  row.append(None)',
			'else:',
			'  row.append(val)',])
	else:
			src.append('row.append(val)')
	return src


def _makeFloatDecoder(field):
	numBytes, structCode = _typemap[field.datatype]
	return [
		'val = struct.unpack("!%s", inF.read(%d))[0]'%(structCode, numBytes),
		'if val!=val:',
		'  row.append(None)',
		'else:',
		'  row.append(val)']


def _makeComplexDecoder(field, numBytes, structCode):
	return [
		'_re, _im = struct.unpack(%s, inF.read(%d))'%(repr(structCode), numBytes),
		'if _re!=_re or _im!=_im:',
		'  row.append(None)',
		'else:',
		'  row.append(_re+1j*_im)']


def _makeIntDecoder(field):
	numBytes, structCode = _typemap[field.datatype]
	src = [
		'val = struct.unpack("!%s", inF.read(%d))[0]'%(structCode, numBytes)
	]
	return _addNullvalueCode(field, src, int)


def _makeBooleanDecoder(field):
	return [
		'row.append(BINENCBOOL[inF.read(1)])']


def _getArraysizeCode(field):
	src = []
	if field.hasVarLength():
		src.append('arraysize = struct.unpack("!i", inF.read(4))[0]')
	else:
		try:
			src.append("arraysize = %d"%field.getLength())
		except ValueError:
			src.append("arraysize = 1")
	return src


def _makeBitDecoder(field):
	# bits/bit arrays are just dumped bits we turn to integers
	# it's basically the same thing for arrays and single values.
	src = _getArraysizeCode(field)
	src.extend([
		'if arraysize==0:',
		'  res = []',
		'else:',
		'  numBytes = (arraysize+7)/8',
		'  topMask = (1<<(arraysize%8))-1',  # mask for payload in topmost byte
		'  if topMask==0: topMask = 0xff',
		'  bytes = struct.unpack("%dB"%numBytes, inF.read(numBytes))',
		'  res = bytes[0]&topMask',
		'  for b in bytes[1:]:',
		'    res = (res<<8)+b',
		'row.append(res)'])
	return src


def _makeString(field, customSrc):
	src = _getArraysizeCode(field)
	src.extend(customSrc)
	return _addNullvalueCode(field, src, repr)


def _makeCharDecoder(field):
	return _makeString(field, [
		'val = struct.unpack("%ds"%arraysize, inF.read(arraysize))[0]'])


def _makeUnicodeCharDecoder(field):
	# XXX BUG: Anything outside the BMP will kill this
	return _makeString(field, [
		'val = struct.unpack("%ds"%(2*arraysize), inF.read(2*arraysize)'
			')[0].decode("utf-16be")'])


_typemap = {
	"unsignedByte": (1, 'B'),
	"short": (2, 'h'),
	"int": (4, 'i'),
	"long": (8, 'q'),
	"float": (4, 'f'),
	"double": (8, 'd'),}


_decoders = {
	'boolean': _makeBooleanDecoder,
	'bit': _makeBitDecoder,
	'char': _makeCharDecoder,
	'unicodeChar': _makeUnicodeCharDecoder,

	'unsignedByte': _makeIntDecoder,
	'short': _makeIntDecoder,
	'int':  _makeIntDecoder,
	'long': _makeIntDecoder,

	'float': _makeFloatDecoder,
	'double': _makeFloatDecoder,
	'floatComplex': lambda v: _makeComplexDecoder(v, 8, '!ff'),
	'doubleComplex': lambda v: _makeComplexDecoder(v, 16, '!dd'),
}

def _makeShortcutCode(field, type):
	"""returns None or code to quickly decode field array.

	Fast decoding for whatever is mentioned in _typemap and no nullvalues
	are defined.
	"""
	if type not in _typemap:
		return None
	if coding.getNullvalue(field, str) is not None:
		return None
	numBytes, typecode = _typemap[type]
	src = _getArraysizeCode(field)
	src.append(
		'vals = struct.unpack("!%%d%s"%%arraysize, inF.read(arraysize*%d))'%(
			typecode, numBytes))
	if type=='float' or type=='double':
		src.append(
			'row.append([v!=v and None or v for v in vals])')
	else:
		src.append(
			'row.append(list(vals))')


def _getArrayDecoderLines(field):
	"""returns lines that decode arrays of literals.

	Unfortunately, the spec is plain nuts, so we need to pull some tricks here.
	"""
	type = field.datatype

	# Weird things
	if type=="bit":
		return _makeBitDecoder(field)
	elif type=='char':
		return _makeCharDecoder(field)
	elif type=='unicodeChar':
		return _makeUnicodeCharDecoder(field)
	
	# Fast array decoding for fields without null values
	src = _makeShortcutCode(field, type)
	if src is not None:
		return src

	# default processing
	src = [ # OMG.  I'm still hellbent on not calling functions here.
		'fullRow, row = row, []',
		]
	src.extend(_getArraysizeCode(field))
	src.extend([
		"for i in range(arraysize):"])
	src.extend(coding.indentList(_decoders[type](field), "  "))
	src.extend([
		"fullRow.append(tuple(row))",
		"row = fullRow"])
	return src


def getLinesFor(field):
	"""returns a sequence of python source lines to decode BINARY-encoded
	values for field.
	"""
	if field.isScalar():
		return _decoders[field.datatype](field)
	else:
		return _getArrayDecoderLines(field)


def getRowDecoderSource(tableDefinition):
	"""returns the source for a function deserializing a BINARY stream.

	tableDefinition is a VOTable.TABLE instance.  The function returned
	expects a file-like object.
	"""
	source = ["def codec(inF):", "  row = []"]
	for index, field in enumerate(
			tableDefinition.iterChildrenOfType(VOTable.FIELD)):
		source.extend([
			"  try:",]+
			coding.indentList(getLinesFor(field), "    ")+[
			"  except IOError:",  # EOF on empty row is ok.
			"    if inF.atEnd and row==[]:",
			"      return None",
			"    raise",
			"  except:",
			"    raise common.BadVOTableLiteral('%s', repr(inF.lastRes))"%(
				field.datatype)])
	source.append("  return row")
	return "\n".join(source)


def getGlobals(tableDefinition):
	return globals()
