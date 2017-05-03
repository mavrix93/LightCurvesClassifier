"""
BINARY2 VOTable decoding

BINARY2 is like BINARY, except every record is preceded by a mask which
columns are NULL.

Sorry for gratuituously peeking into the guts of dec_binary here.  But well,
it's family.
"""

#c Copyright 2008-2016, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from gavo.votable import coding
from gavo.votable import common
from gavo.votable import dec_binary
from gavo.votable.model import VOTable


def getRowDecoderSource(tableDefinition):
	"""returns the source for a function deserializing a BINARY stream.

	tableDefinition is a VOTable.TABLE instance.  The function returned
	expects a file-like object.
	"""
	source = [
		"def codec(inF):", 
		"  row = []",
		"  nullMap = nullFlags.getFromFile(inF)", ]

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
				field.datatype),
			])

	source.extend([
		"  for index, isNull in enumerate(nullMap):",
		"    if isNull:",
		"      row[index] = None",
		"  return row"])
	return "\n".join(source)


def getGlobals(tableDefinition):
	vars = dict((n, getattr(dec_binary, n)) for n in dir(dec_binary))
	vars["nullFlags"] = common.NULLFlags(len(tableDefinition.getFields()))
	return vars


getLinesFor = dec_binary.getLinesFor
