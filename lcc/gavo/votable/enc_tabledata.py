"""
Encoding to tabledata.
"""

#c Copyright 2008-2016, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import datetime #noflake: used in generated code

from gavo import utils #noflake: used in generated code
from gavo.utils import stanxml
from gavo.utils import pgsphere #noflake: used in generated code
from gavo.votable import coding
from gavo.votable import common


def _getArrayShapingCode(field, padder):
	"""returns common code for almost all array serialization.

	Field must describe an array (as opposed to a single value).

	padder must be python-source for whatever is used to pad
	arrays that are too short.
	"""
	base = [
		"if val is None: val = []"]
	if field.hasVarLength():
		return base
	else:
		return base+["val = coding.trim(val, %s, %s)"%(
			field.getLength(), padder)]


def _addNullvalueCode(field, src, validator, defaultNullValue=None):
	"""adds code handle null values where not default representation exists.
	"""
	nullvalue = coding.getNullvalue(field, validator)
	if nullvalue is None:
		if defaultNullValue is None:
			action = ("  raise common.BadVOTableData('None passed for field"
				" that has no NULL value', None, '%s', hint='Integers in VOTable"
			" have no natural serializations for missing values.  You need to"
			" define one using values null to allow for NULL in integer columns')"
			)%field.getDesignation()
		else:
			action = ("  tokens.append(%r)"%stanxml.escapePCDATA(defaultNullValue))
	else:
		action = "  tokens.append(%r)"%stanxml.escapePCDATA(nullvalue)
	return [
			'if val is None:',
			action,
			'else:']+coding.indentList(src, "  ")


def _makeFloatEncoder(field):
	return [
		"if val is None or val!=val:",  # NaN is a null value, too
		"  tokens.append('NaN')",
		"else:",
		"  tokens.append(repr(float(val)))"]


def _makeComplexEncoder(field):
	return [
		"if val is None:",
		"  tokens.append('NaN NaN')",
		"else:",
		"  try:",
		"    tokens.append('%s %s'%(repr(val.real), repr(val.imag)))",
		"  except AttributeError:",
		"    tokens.append(repr(val))",]


def _makeBooleanEncoder(field):
	return [
		"if val is None:",
		"  tokens.append('?')",
		"elif val:",
		"  tokens.append('1')",
		"else:",
		"  tokens.append('0')",]


def _makeUByteEncoder(field):
	return _addNullvalueCode(field, [
		"if isinstance(val, int):",
		'  tokens.append(str(val))',
		"else:",
		'  tokens.append(str(ord(val[:1])))',], 
		common.validateVOTInt, "")


def _makeIntEncoder(field):
	return _addNullvalueCode(field, [
		"tokens.append(str(val))"],
		common.validateVOTInt)


def _makeCharEncoder(field):
	src = []
	
	if field.isMultiDim():
		l = field.getShape()[0]  # length of the individual strings
		src.extend([
			"tokens.append(stanxml.escapePCDATA(''.join("
			" coding.trimString(s, %d) for s in common.iterflattened(val))))"%l])
	
	else:
		# TODO: string conditioning must be done for array elements, too
		# -- this whole thing isn't structured right.
		if field.datatype=="char":
			src.extend(common.getXtypeCode(field))
			src.extend([
				'if isinstance(val, unicode):',
				'  val = val.encode("ascii", "replace")',
				'elif isinstance(val, list):', # that's really a bug upstream
				'  val = "".join(val)'])

		src.extend([
			"tokens.append(stanxml.escapePCDATA(val))"])

	return _addNullvalueCode(field, src, lambda _: True, "")


_encoders = {
	'boolean': _makeBooleanEncoder,
	'bit': _makeIntEncoder,
	'unsignedByte': _makeUByteEncoder,
	'short': _makeIntEncoder,
	'int': _makeIntEncoder,
	'long': _makeIntEncoder,
	'char': _makeCharEncoder,
	'unicodeChar': _makeCharEncoder,
	'float': _makeFloatEncoder,
	'double': _makeFloatEncoder,
	'floatComplex': _makeComplexEncoder,
	'doubleComplex': _makeComplexEncoder,
}


def _getArrayEncoderLinesNotNULL(field):
	"""returns python lines to encode array values of field.

	Again, the specs are a bit nuts, so we end up special casing almost 
	everything.

	For fixed-length arrays we enforce the given length by
	cropping or adding nulls (except, currently, for bit and char arrays).
	"""
	type = field.datatype
	# bit array literals are integers, real special handling
	if type=="bit":  
		return ['tokens.append(utils.toBinary(val))']
	# char array literals are strings, real special handling
	if type=='char' or type=='unicodeChar':
		return _makeCharEncoder(field)

	src = _getArrayShapingCode(field, '[None]')
	src.extend([ # Painful name juggling to avoid functions
		'fullTokens = tokens',
		'tokens = []',
		'arr = val'])

	src.extend(['for val in common.iterflattened(arr):']+coding.indentList(
		_encoders[type](field), "  "))
	src.append("fullTokens.append(' '.join(tokens))")
	src.append("tokens = fullTokens")
	return src


def _getArrayEncoderLines(field):
	"""returns python lines to encode array values of field.

	This will encode NULL array as empty strings.
	"""
	return [
		"if val is None:",
		"  tokens.append('')",
		"else:",]+coding.indentList(_getArrayEncoderLinesNotNULL(field), " ")


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
		"return '<TR>%s</TR>'%(''.join('<TD>%s</TD>'%v for v in tokens))"]


def getGlobals(tableDefinition):
	return globals()
