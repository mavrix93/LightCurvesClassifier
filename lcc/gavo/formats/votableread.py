"""
Parsing and translating VOTables to internal data structures.

This is glue code to the more generic votable library.  In general, you
should access this module through formats.votable.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import gzip

from gavo import base
from gavo import rsc
from gavo import rscdef
from gavo import utils
from gavo import votable
from gavo.base import valuemappers
from gavo.grammars import votablegrammar
from gavo.votable import V

MS = base.makeStruct

class QuotedNameMaker(object):
	"""A name maker for makeTableDefForVOTable implementing TAP's requirements.
	"""
	def __init__(self):
		self.index, self.seenNames = 0, set()

	def makeName(self, field):
		self.index += 1
		res = getattr(field, "name", None)
		if res is None:
			raise base.ValidationError("Field without name in upload.",
				"UPLOAD")
		if res in self.seenNames:
			raise base.ValidationError("Duplicate column name illegal in"
				" uploaded tables (%s)"%res, "UPLOAD")
		self.seenNames.add(res)
		return utils.QuotedName(res)


class AutoQuotedNameMaker(object):
	"""A name maker for makeTableDefForVOTable quoting names as necessary.
	"""
	def __init__(self, forRowmaker=False):
		self.seenNames = set()
	
	def makeName(self, field):
		name = getattr(field, "name", None)
		if name is None:
			raise base.ValidationError("Field without name in upload.",
				"UPLOAD")
		if valuemappers.needsQuoting(name):
			if name in self.seenNames:
				raise base.ValidationError("Duplicate column name illegal in"
					" uploaded tables (%s)"%name, "UPLOAD")
			self.seenNames.add(name)
			return utils.QuotedName(name)
		else:
			if name.lower() in self.seenNames:
				raise base.ValidationError("Duplicate column name illegal in"
					" uploaded tables (%s)"%name, "UPLOAD")
			self.seenNames.add(name.lower())
			return name


def addQ3CIndex(tableDef):
	"""if td as unique main positions (by UCD), add an index to the table
	definition.
	"""
	try:
		raField = tableDef.getColumnByUCDs("pos.eq.ra;meta.main", 
			"POS_EQ_RA_MAIN")
		decField = tableDef.getColumnByUCDs("pos.eq.dec;meta.main", 
			"POS_EQ_RA_MAIN")
		if (raField.type not in ["real", "double precision"] 
			or decField.type not in ["real", "double precision"]):
			raise ValueError("Don't index non-floats")
	except ValueError: # No unique positions
		return
	base.resolveId(None, "//scs#q3cindex").applyToFinished(tableDef)


def _getValuesFromField(votField):
	"""returns None or an rscdef.Values instance for whatever is given
	in votField.
	"""
	valArgs = {}
	for valSpec in votField.iterChildrenOfType(V.VALUES):

		if valSpec.null is not None:
			valArgs["nullLiteral"] = valSpec.null

		for minSpec in valSpec.iterChildrenOfType(V.MIN):
			valArgs["min"] = minSpec.value

		for maxSpec in valSpec.iterChildrenOfType(V.MAX):
			valArgs["max"] = maxSpec.value

		options = []
		for optSpec in valSpec.iterChildrenOfType(V.OPTION):
			# We don't support nested options in rscdef.
			consArgs = {"content_": optSpec.value}
			if optSpec.name:
				consArgs["title"] = optSpec.name
			options.append(base.makeStruct(rscdef.Option, **consArgs))
		if options:
			valArgs["options"] = options
	if valArgs:
		return base.makeStruct(rscdef.Values, **valArgs)


def _getColArgs(votInstance, name):
	"""returns constructor arguments for an RD column or param from
	a VOTable FIELD or PARAM.
	"""
	kwargs = {"name": name,
		"tablehead": name.capitalize(),
		"id": getattr(votInstance, "ID", None),
		"type": base.voTableToSQLType(
			votInstance.datatype, votInstance.arraysize, votInstance.xtype)}

	for attName in ["ucd", "unit", "xtype"]:
		if getattr(votInstance, attName, None) is not None:
			kwargs[attName] = getattr(votInstance, attName)

	if getattr(votInstance, "value", None) is not None:
		kwargs["content_"] = votInstance.value
	values = _getValuesFromField(votInstance)
	if values:
		kwargs["values"] = values
	
	for desc in votInstance.iterChildrenOfType(V.DESCRIPTION):
		kwargs["description"] = desc.text_

	return kwargs
	

def makeTableDefForVOTable(tableId, votTable, nameMaker=None, rd=None,
		**moreArgs):
	"""returns a TableDef for a Table element parsed from a VOTable.

	Pass additional constructor arguments for the table in moreArgs.
	stcColumns is a dictionary mapping IDs within the source VOTable
	to pairs of stc and utype.

	nameMaker is an optional argument; if given, it must be an object
	having a makeName(field) -> string or utils.QuotedName method.
	It must return unique objects from VOTable fields and to that
	reproducibly, i.e., for a given field the same name is returned.

	The default is valuemappers.VOTNameMaker, but
	you can also use InventinQuotedNameMaker, QuotedNameMaker, or
	AutoQuotedNameMaker from this module.

	If unique "main" positions are given, a spatial q3c index will be
	added.
	"""
	if nameMaker is None:
		nameMaker = valuemappers.VOTNameMaker()

	# make columns
	columns = []
	for f in votTable.iterChildrenOfType(V.FIELD):
		columns.append(MS(rscdef.Column,
			**_getColArgs(f, nameMaker.makeName(f))))

	# make params
	params = []
	for f in votTable.iterChildrenOfType(V.PARAM):
		try:
			params.append(MS(rscdef.Param, **_getColArgs(f, f.name)))
		except Exception, ex:  # never die because of failing params
			base.ui.notifyError("Unsupported PARAM ignored (%s)"%ex)

	# Create the table definition
	tableDef = MS(rscdef.TableDef, id=tableId, columns=columns,
		params=params, parent_=rd, **moreArgs)
	addQ3CIndex(tableDef)

	# Build STC info
	for colInfo, ast in votable.modelgroups.unmarshal_STC(votTable):
		for colId, utype in colInfo.iteritems():
			try:
				col = tableDef.getColumnById(colId)
				col.stcUtype = utype
				col.stc = ast
			except utils.NotFoundError: # ignore broken STC
				pass

	return tableDef


def makeDDForVOTable(tableId, vot, gunzip=False, rd=None, **moreArgs):
	"""returns a DD suitable for uploadVOTable.

	moreArgs are additional keywords for the construction of the target
	table.

	Only the first resource  will be turned into a DD.  Currently,
	only the first table is used.  This probably has to change.
	"""
	tableDefs = []
	for res in vot.iterChildrenOfType(V.RESOURCE):
		for table in res.iterChildrenOfType(V.TABLE):
			tableDefs.append(
				makeTableDefForVOTable(tableId, table, rd=rd, **moreArgs))
			break
		break
	if tableDefs:
		makes = [MS(rscdef.Make, table=tableDefs[0])]
	else:
		makes = []
	return MS(rscdef.DataDescriptor,
		grammar=MS(votablegrammar.VOTableGrammar, gunzip=gunzip),
		makes=makes)


_xtypeParsers = {
	'adql:POINT': "parseSimpleSTCS",
	'adql:REGION': "simpleSTCSToPolygon",
	'adql:TIMESTAMP': "parseDefaultDatetime",
}


def _getRowMaker(table):
	"""returns a function turning a VOTable tuple to a database row
	for table.

	This is mainly just building a row dictionary, except we also
	parse xtyped columns.
	"""
	from gavo.base.literals import parseDefaultDatetime #noflake: code gen
	from gavo.stc import parseSimpleSTCS, simpleSTCSToPolygon #noflake: code gen

	parts = []
	for colInd, col in enumerate(table.tableDef):
		if _xtypeParsers.get(col.xtype):
			valCode = "%s(row[%d])"%(_xtypeParsers[col.xtype], colInd)
		else:
			valCode = "row[%d]"%colInd
		parts.append("%s: %s"%(repr(col.key), valCode))

	return utils.compileFunction(
		"def makeRow(row):\n  return {%s}"%(", ".join(parts)), 
		"makeRow",
		locals())


def uploadVOTable(tableId, srcFile, connection, gunzip=False, 
		rd=None, **tableArgs):
	"""creates a temporary table with tableId containing the first
	table in the VOTable in srcFile.

	The function returns a DBTable instance for the new file.

	srcFile must be an open file object (or some similar object).
	"""
	if gunzip:
		srcFile = gzip.GzipFile(fileobj=srcFile, mode="r")
	try:
		tuples = votable.parse(srcFile).next()
	except StopIteration: # no table contained, not our problem
		return

	args = {"onDisk": True, "temporary": True}
	args.update(tableArgs)
	td = makeTableDefForVOTable(tableId, tuples.tableDefinition, 
		rd=rd, **args)

	table = rsc.TableForDef(td, connection=connection, create=True)
	makeRow = _getRowMaker(table)
	with table.getFeeder() as feeder:
		for tuple in tuples:
			feeder.add(makeRow(tuple))
	return table
