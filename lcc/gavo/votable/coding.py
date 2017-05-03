"""
Common code for coding and decoding VOTable data.
"""

#c Copyright 2008-2016, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from __future__ import with_statement

from gavo import utils
from gavo.votable import common
from gavo.votable.model import VOTable


def getRowEncoderSource(tableDefinition, encoderModule):
	"""returns the source for a function encoding rows of tableDefition
	in the format implied encoderModule

	tableDefinition is a VOTable.TABLE instance, encoderModule
	is one of the enc_whatever modules (this function needs getLinesFor
	and getPostamble from them).
	"""

	source = [
		"def codec(tableRow):", 
		"  tokens = []",
		"  val = None"]

	source.extend(
		indentList(
			getattr(encoderModule, "getPreamble", lambda td: [])(
				tableDefinition), "  "))

	for index, field in enumerate(
			tableDefinition.iterChildrenOfType(VOTable.FIELD)):
		source.extend([
			"  try:",
			"    val = tableRow[%d]"%index])
		source.extend(indentList(encoderModule.getLinesFor(field), "    "))
		source.extend([
			"  except common.VOTableError:",
			"    raise",
			"  except Exception, ex:",
			"    raise common.BadVOTableData(unicode(ex), repr(val), '%s')"%
				field.getDesignation()])
	source.extend(indentList(
		encoderModule.getPostamble(tableDefinition), "  "))
	return "\n".join(source)


def buildCodec(source, env):
	"""returns a compiled function for source in env.

	Source is the result of one of the makeXXX functions in this module,
	env typically the result of a getGlobals() on the codec module.
	"""
	ns = {}
	ns.update(env)
	try:
		#open("codec.py", "w").write(source)
		exec source in ns
	except:
		utils.sendUIEvent("Error", 
			"Error when compling VOTable codec (source in dcInfo)")
		utils.sendUIEvent("Info", "The failing source code was:\n"+source)
		raise
	return ns["codec"]


def buildEncoder(tableDefinition, encoderModule):
	return buildCodec(
		getRowEncoderSource(tableDefinition, encoderModule),
		encoderModule.getGlobals(tableDefinition))


def buildDecoder(tableDefinition, decoderModule):
	return buildCodec(
		decoderModule.getRowDecoderSource(tableDefinition),
		decoderModule.getGlobals(tableDefinition))


def indentList(lines, indent):
	"""prepens indent to all elements in lines.
	"""
	return [indent+l for l in lines]


def getNullvalue(field, validator, default=None):
	"""returns None or the nullvalue defined for field.

	validator is a function that raises some exception if the nullvalue
	is inappropriate.  It should do so in particular on everything that
	contains quotes and such; the nullvalues are included in source code
	and thus might be used to inject code if not validated.
	"""
	nullvalue = None
	for values in field.iterChildrenOfType(VOTable.VALUES):
		if values.null is not None:
			nullvalue = values.null
	if nullvalue is None or nullvalue=='':
		return default
	else:
		validator(nullvalue)
	return nullvalue


def unravelArray(arraysize, seq):
	"""turns a flat sequence into an n-dim array as specfied by the votable
	arraysize spec arraysize.

	arraysize is <int>{"x"<int>}*?|*.

	No padding or cropping will take place.  This means that the last
	row(s) may have improper sizes if seq is incompatible with arraysize.
	"""
	parts = arraysize.split("x")
	if len(parts)<2:
		return seq
	del parts[-1]
	for step in map(int, parts):
		seq = [seq[i:i+step] for i in range(0, len(seq), step)]
	return seq


def trim(seq, arraysize, padder):
	"""returns seq with length arraysize.

	arraysize is an int; you should just use field.getLength() when
	trimming VOTable arraysizes since the arraysize attribute is rather
	complex.   Arraysize may be None for convenience; trim is a no-op then.
	
	If seq is shorter, padder*missing will be appended, if it is longer, seq will
	be shortened from the end.

	This is intended as a helper for array encoders.
	"""
	if arraysize is None:
		return seq
	if len(seq)<arraysize:
		seq = seq+padder*(arraysize-len(seq))
	elif len(seq)>arraysize:
		seq = seq[:arraysize]
	return list(common.iterflattened(seq))


def trimString(aString, length, padChar=" "):
	"""returns aString padded with blanks/cropped to length.
	"""
	l = len(aString)
	if l<length:
		return aString+padChar*(length-l)
	elif l>length:
		return aString[:length]
	else:
		return aString
