"""
Coding and decoding from tabledata.
"""

#c Copyright 2008-2016, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import re #noflake: used by generated code

from gavo.utils import parseDefaultDatetime, parseDefaultDate #noflake: used by generated code
from gavo.votable import coding
from gavo.votable import common
from gavo.votable.model import VOTable

try:
	from gavo import stc  #noflake: used by generated code
except ImportError:
	# see modelgroups
	pass


# literals for TDENC booleans
TDENCBOOL = {
	't': True,
	'1': True,
	'true': True,
	'f': False,
	'0': False,
	'false': False,
	'?': None,
	'': None,
}


def tokenizeComplexArr(val):
	"""iterates over suitable number literal pairs from val.
	"""
	last = None
	if val is None:
		return
	for item in val.split():
		if not item:
			continue
		if last is None:
			last = item
		else:
			yield "%s %s"%(last, item)
			last = None
	if last:
		yield last


def tokenizeBitArr(val):
	"""iterates over 0 or 1 tokens in val, discarding everything else.
	"""
	if val is None:
		return
	for item in val:
		if item in "01":
			yield item


def tokenizeNormalArr(val):
	"""iterates over all whitespace-separated tokens in val
	"""
	if val is None:
		return
	for item in val.split():
		if item:
			yield item


def _addNullvalueCode(field, src, validator):
	"""adds code to catch nullvalues if required by field.
	"""
	nullvalue = coding.getNullvalue(field, validator)
	if nullvalue is not None:
		src = [
			'if val=="%s":'%nullvalue,
			'  row.append(None)',
			'else:']+coding.indentList(src, "  ")
	return src


def _makeFloatDecoder(field):
	src = [
		'if not val or val=="NaN":',
		'  row.append(None)',
		'else:',
		'  row.append(float(val))',]
	return _addNullvalueCode(field, src, float)


def _makeComplexDecoder(field):
	src = [
		'if not val:',
		'  row.append(None)',
		'else:',
		'  try:',
		'    r, i = val.split()',
		'  except ValueError:',
		'    r, i = float(val), 0',
		'  if r!=r or i!=i:',
		'    row.append(None)',
		'  else:'
		'    row.append(complex(float(r), float(i)))',]
	return _addNullvalueCode(field, src, common.validateTDComplex)


def _makeIntDecoder(field, maxInt):
	src = [
		'if not val:',
		'  row.append(None)',
		'elif val.startswith("0x"):',
		'  unsigned = int(val[2:], 16)',
		# Python hex parsing is unsigned, fix manually based on maxInt
		'  if unsigned>=%d:'%maxInt,
		'    row.append(unsigned-%d)'%((maxInt+1)*2),
		'  else:',
		'    row.append(unsigned)',
		'else:',
		'  row.append(int(val))']
	return _addNullvalueCode(field, src, common.validateVOTInt)


def _makeXtypeDecoder(field):
	"""returns a decoder for fields with non-empty xtypes.

	All of these come in strings and are NULL if empty.

	This function may return None for "ignore the xtype".
	"""
	src = [
		"if not val:",
		"  val = None",
		"else:"]

	if field.xtype=="interval":
		return None

	if field.xtype=="adql:POINT":
		src.extend([
			"  val = stc.parseSimpleSTCS(val)"])

	elif field.xtype=="adql:REGION":
		src.extend([
			"  val = stc.simpleSTCSToPolygon(val)"])

	elif field.xtype=="adql:TIMESTAMP":
		src.extend([
			"  val = parseDefaultDatetime(val)"])

	# GAVO-specific extension for consistency in our type systems
	elif field.xtype=="dachs:DATE":
		src.extend([
			"  val = parseDefaultDate(val)"])

	else:
		# unknown xtype, just don't touch it (issue a warning?)
		src.extend([
			"  pass"])

	src.append("row.append(val)")
	return src


def _makeCharDecoder(field, emptyIsNull=True, fallbackEncoding="iso-8859-1"):
	"""parseString enables return of empty string (as opposed to None).
	"""
# Elementtree makes sure we're only seeing unicode strings here
# However, char corresponds to byte strings, so we have to 
# encode things before shipping out.  In theory, there should only
# be ASCII in tabledata.  In practice, people do dump all kinds of
# things in there.
	src = []
	if emptyIsNull:
		src.extend([
			'if not val:',
			'  val = None',])
	else:
		src.extend([
			'if val is None:',
			'  val = ""'])	

	nullvalue = coding.getNullvalue(field, str, "")
	decoder = ""
	if fallbackEncoding:
		decoder = '.encode("%s", "ignore")'%fallbackEncoding

	if nullvalue:
		src.extend([
			'if val==%s:'%repr(nullvalue),
			'  row.append(None)',
			'else:',
			'  row.append(val and val%s)'%decoder])
	else:
		src.append('row.append(val and val%s)'%decoder)
	return src


def _makeUnicodeDecoder(field, emptyIsNull=True):
	return _makeCharDecoder(field, emptyIsNull, fallbackEncoding=None)


def _makeBooleanDecoder(field):
	return ['row.append(TDENCBOOL[val.strip().lower()])']


def _makeBitDecoder(field):
	return ['row.append(int(val))']


_decoders = {
	'boolean': _makeBooleanDecoder,
	'bit': _makeBitDecoder,
	'unsignedByte': lambda v: _makeIntDecoder(v, 256),
	'char': _makeCharDecoder,
	'unicodeChar': _makeUnicodeDecoder,  # heavy lifting done by the xml parser
	'short': lambda v: _makeIntDecoder(v, 32767),
	'int': lambda v: _makeIntDecoder(v, 2147483647),
	'long': lambda v: _makeIntDecoder(v, 9223372036854775807L),
	'float': _makeFloatDecoder,
	'double': _makeFloatDecoder,
	'floatComplex': _makeComplexDecoder,
	'doubleComplex': _makeComplexDecoder,
}

def _getArrayDecoderLines(field):
	"""returns lines that decode arrays of literals.

	Unfortunately, the spec is plain nuts, so we need to pull some tricks here.

	As per VOTable 1.3, we translate empty strings to Nones; we use the
	liberty that empty and NULL arrays are not distinguished to return
	empty strings as empty strings, though.
	"""
	type = field.datatype

	if field.xtype:
		res = _makeXtypeDecoder(field)
		if res is not None:
			return res

	if type=='char':
		return _makeCharDecoder(field, emptyIsNull=True)
	elif type=='unicodeChar':
		return _makeUnicodeDecoder(field, emptyIsNull=True)

	src = [ # OMG.  I'm still hellbent on not calling functions here.
		'arrayLiteral = val',
		'fullRow, row = row, []',
		]
	if type=='floatComplex' or type=='doubleComplex':
		src.append("for val in tokenizeComplexArr(arrayLiteral):")
	elif type=='bit':
		src.append("for val in tokenizeBitArr(arrayLiteral):")
	else:
		src.append("for val in tokenizeNormalArr(arrayLiteral):")
	src.extend(coding.indentList(_decoders[type](field), "  "))
	src.append("fullRow.append(tuple(row))")
	src.append("row = fullRow")

	return [
		"if val=='':",
		"  row.append(None)",
		"else:"]+coding.indentList(src, "  ")


def getLinesFor(field):
	"""returns a sequence of python source lines to decode TABLEDATA-encoded
	values for field.
	"""
	if field.isScalar():
		return _decoders[field.datatype](field)
	else:
		return _getArrayDecoderLines(field)


def getRowDecoderSource(tableDefinition):
	"""returns the source for a function deserializing rows of tableDefition
	in TABLEDATA.

	tableDefinition is a VOTable.TABLE instance.
	"""
	source = ["def codec(rawRow):", "  row = []"]
	for index, field in enumerate(
			tableDefinition.iterChildrenOfType(VOTable.FIELD)):
		source.extend([
			"  try:",
			"    val = rawRow[%d]"%index,]+
			coding.indentList(getLinesFor(field), "    ")+[
			"  except:",
			"    raise common.BadVOTableLiteral('%s', val)"%field.datatype])
	source.append("  return row")
	return "\n".join(source)

	return source


def getGlobals(tableDefinition):
	return globals()
