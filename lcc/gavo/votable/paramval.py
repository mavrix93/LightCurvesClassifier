"""
Serialisation of python values to VOTable PARAM values.

This has two aspects:

- Guessing proper VOTable type descriptors for python values
  (use guessParamAttrsForValue)
- Serialising the python values to strings suitable for the PARAM.
  (use serializeToParam)
"""

#c Copyright 2008-2016, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import datetime

from gavo import utils
from gavo.utils import pgsphere
from gavo.utils import serializers
from gavo.votable import coding
from gavo.votable import enc_tabledata
from gavo.votable import dec_tabledata
from gavo.votable.model import VOTable as V


_SEQUENCE_TYPES = (tuple, list)
_ATOMIC_TYPES = [
	(long, {"datatype": "long"}),
	(int, {"datatype": "int"}),
	(str, {"datatype": "char", "arraysize": "*"}),
	(basestring, {"datatype": "unicodeChar", "arraysize": "*"}),
	(float, {"datatype": "double"}),
	(type(None), {"datatype": "double"}),
	(complex, {"datatype": "doubleComplex"}),
	(datetime.datetime, {"datatype": "char", 
		"arraysize": "20",
		"xtype": "adql:TIMESTAMP"}),
	(datetime.date, {"datatype": "char", 
		"arraysize": "20",
		"xtype": "dachs:DATE"}),
	(pgsphere.SPoint, {"datatype": "char", 
		"arraysize": "*",
		"xtype": "adql:POINT"}),]


def _combineArraysize(arraysize, attrs):
	"""makes an arraysize attribute for a value with attrs.

	This will in particular check that any existing arraysize in
	attrs does not end with a star (as variable length is only allowed
	in the slowest coordinate).

	attrs is changed in place.
	"""
	if "arraysize" in attrs:
		if attrs["arraysize"].endswith("*"):
			raise ValueError("Arrays of variable-length arrays are not allowed.")
		attrs["arraysize"] = "%sx%s"%(attrs["arraysize"], arraysize)
	else:
		attrs["arraysize"] = arraysize
	

def _guessParamAttrsForSequence(pythonVal):
	"""helps guessParamAttrsForValue when the value is a sequence.
	"""
	arraysize = str(len(pythonVal))
	if len(pythonVal)==0:
		return {
			"datatype": "char",
			"arraysize": "0"}

	elementVal = pythonVal[0]

	if isinstance(elementVal, basestring):
		# special case as this may become common
		attrs = {
			"arraysize": "%sx%s"%(
				max(len(s) for s in pythonVal), arraysize),
			"datatype": "char"}
	
	elif isinstance(elementVal, _SEQUENCE_TYPES):
		attrs = _guessParamAttrsForSequence(elementVal)
		_combineArraysize(arraysize, attrs)
	
	else:
		attrs = _guessParamAttrsForAtom(elementVal)
		_combineArraysize(arraysize, attrs)

	return attrs


def _guessParamAttrsForAtom(pythonVal):
	"""helps guessParamAttrsForValue when the value is atomic.

	(where "atomic" includes string, and other things that actually
	have non-1 arraysize).
	"""
	for type, attrs in _ATOMIC_TYPES:
		if isinstance(pythonVal, type):
			return attrs.copy()

	raise utils.NotFoundError(repr(pythonVal),
		"VOTable type code for", "paramval.py predefined types")


def guessParamAttrsForValue(pythonVal):
	"""returns a dict of proposed attributes for a PARAM to keep pythonVal.

	There is, of course, quite a bit of heuristics involved.  For instance,
	we assume sequences are homogeneous.
	"""
	if isinstance(pythonVal, _SEQUENCE_TYPES):
		return _guessParamAttrsForSequence(pythonVal)

	else:
		return _guessParamAttrsForAtom(pythonVal)


def _setNULLValue(param, val):
	"""sets the null literal of param to val.
	"""
	valEls = list(param.iterChildrenWithName("VALUES"))
	if valEls:
		valEls[0](null=val)
	else:
		param[V.VALUES(null=val)]


def _serializeNULL(param):
	"""changes the VOTable PARAM param so it evaluates to NULL.
	"""
	if param.datatype in ["float", "double"]:
		element = "NaN "
	elif param.datatype in ["unsignedByte", "short", "int", "long"]:
		element = "99 "
		_setNULLValue(param, element)
	elif param.datatype in ["char", "unicodeChar"]:
		element = "x"
		_setNULLValue(param, element)
	else:
		raise ValueError("No recipe for %s null values"%param.datatype)

	if param.isScalar():
		param.value = element.strip()
	elif param.hasVarLength():
		param.value = ""
	else:
		param.value = (element*param.getLength()).strip()


class PrimitiveAnnotatedColumn(dict):
	"""A stand-in for serializers.AnnotatedColumn.

	We don't want to use the full thing as it's too fat here, and
	getVOTSerializer doesn't have the original param anyway (as
	it shouldn't, as that would break memoization).
	"""

	class original(object):
		stc = None
		xtype = None

	def __init__(self, datatype, arraysize, xtype):
		dict.__init__(self, {
			"nullvalue": "",
			"name": "anonymous",
			"dbtype": None,
			"displayHint": {},
			"note": None,
			"ucd": None,
			"utype": None,
			"unit": None,
			"description": None,
			"id": None,
			"datatype": datatype, 
			"arraysize": arraysize, 
			"xtype": xtype})


@utils.memoized
def getVOTSerializer(datatype, arraysize, xtype):
	"""returns a function serializing for values of params with the
	attributes given.
	"""
	lines = "\n".join([
		"def codec(val):"]+
		coding.indentList([
			"val = mapper(val)",
			"tokens = []"]+
			enc_tabledata.getLinesFor(V.PARAM(**locals()))+[
			"return tokens[0]"], "  "))

	mapper = serializers.defaultMFRegistry.getMapper(PrimitiveAnnotatedColumn(
		datatype, arraysize, xtype))
	env = enc_tabledata.getGlobals(None).copy()
	env["mapper"] = mapper

	return coding.buildCodec(lines, env)


def serializeToParam(param, val):
	"""changes the VOTable PARAM param such that val is represented.

	This may involve adding a null value.
	"""
	if val is None:
		_serializeNULL(param)
	else:
		param.value = getVOTSerializer(
			param.datatype, param.arraysize, param.xtype)(val)


@utils.memoized
def getVOTParser(datatype, arraysize, xtype):
	"""returns a function deserializing values in a param with datatype,
	arraysize, and xtype.
	"""
	p = V.PARAM(name="anonymous", datatype=datatype, arraysize=arraysize,
		xtype=xtype)

	lines = "\n".join([
		"def codec(val):"]
		+coding.indentList([
			"row = []"]
			+dec_tabledata.getLinesFor(p)
			+[
			"return row[0]"], "  "))

	return coding.buildCodec(lines, dec_tabledata.getGlobals(None))
