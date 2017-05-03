"""
Generation of VODataService 1.1 tablesets from resources, plus 1.0 hacks.

Fudge note: sprinkled in below are lots of lower()s for column names and the
like.  These were added for the convenience of TAP clients that may
want to use these names quoted.  Quoted identifiers match regular identifiers
only if case-normalized (i.e., all-lower in DaCHS).
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import itertools

from gavo import base
from gavo import svcs
from gavo.registry.model import VS


def getSchemaForRD(rd):
	"""returns a VS.schema instance for an rd.

	No tables are added.  You need to pick and choose them yourself.
	"""
	return VS.schema[
		VS.name[rd.schema.lower()],
		VS.title[base.getMetaText(rd, "title")],
		VS.description[base.getMetaText(rd, "description")],
	]


def getForeignKeyForForeignKey(fk, namesInSet):
	"""returns a VS.foreignKey for a rscdef.ForeignKey.

	If the target table's name is not in nameInSet, the foreign key
	is not created.
	"""
# XXX TODO: we don't need to expand any more as soon as we've done away with
# the table attribute of foreignKey
	targetName = fk.parent.expand(fk.destTableName).lower()
	if targetName not in namesInSet:
		return None

	return VS.foreignKey[
		VS.targetTable[targetName], [
			VS.fkColumn[
				VS.fromColumn[fromColName.lower()],
				VS.targetColumn[toColName.lower()]]
			for fromColName,toColName in zip(fk.source, fk.dest)]]


def getTableColumnFromColumn(column, typeElement):
	"""returns a VS.column instance for an rscdef.Column instance.

	typeElement is a factory for types that has to accept an internal (SQL)
	type as child and generate whatever is necessary from that.
	VS.voTableDataType is an example for such a factory.
	"""
	flags = []
	if column.isIndexed():
		flags.append("indexed")
	if column.isPrimary():
		flags.append("primary")
	elif not column.required:
		flags.append("nullable")
	return VS.column[
		VS.name[column.name.lower()],
		VS.description[column.description],
		VS.unit[column.unit],
		VS.ucd[column.ucd],
		VS.utype[column.utype],
		typeElement[column.type],
		[VS.flag[f] for f in flags]]


def getEffectiveTableName(tableDef):
	"""returns the "effective name" of tableDef.

	This is mainly for fudging the names of output tables since, 
	by default, they're ugly (and meaningless on top of that).
	"""
	if isinstance(tableDef, svcs.OutputTableDef):
		return "output"
	else:
		return tableDef.getQName().lower()


def getTableForTableDef(tableDef, namesInSet):
	"""returns a VS.table instance for a rscdef.TableDef.

	namesInSet is a set of lowercased qualified table names; we need this
	to figure out which foreign keys to create.
	"""
	name = getEffectiveTableName(tableDef)

	# Fake type=output on the basis of the table name.  We'll have
	# to do something sensible here if this "type" thing ever becomes
	# more meaningful.
	type = None
	if name=="output":
		type = "output"

	res = VS.table(type=type)[
		VS.name[name],
		VS.title[base.getMetaText(tableDef, "title", propagate=False)],
		VS.description[base.getMetaText(tableDef, "description", propagate=True)],
		VS.utype[base.getMetaText(tableDef, "utype")], [
			getTableColumnFromColumn(col, VS.voTableDataType)
				for col in tableDef], [
			getForeignKeyForForeignKey(fk, namesInSet)
				for fk in tableDef.foreignKeys]]
	return res


def getTablesetForSchemaCollection(schemas, rootElement=VS.tableset):
	"""returns a vs:tableset element from a sequence of (rd, tables) pairs.
	
	In each pair, rd is used to define a VODataService schema, and tables is 
	a sequence of TableDefs that define the tables within that schema.
	"""
	# we don't want to report foreign keys into tables not part of the
	# service's tableset (this is for consistency with TAP_SCHEMA,
	# mainly).  Hence, we collect the table names given.
	namesInSet = set(getEffectiveTableName(td).lower()
		for td in itertools.chain(*(tables for rd, tables in schemas)))

	res = rootElement()
	for rd, tables in schemas:
		res[VS.schema[
			VS.name[rd.schema],
			VS.title[base.getMetaText(rd, "title")],
			VS.description[base.getMetaText(rd, "description")],
			[getTableForTableDef(td, namesInSet)
				for td in tables]]]
	return res


def getTablesetForService(service, rootElement=VS.tableset):
	"""returns a VS.tableset for a dbCore-based service.

	This is for VOSI queries.  It uses the service's getTableset
	method to find out the service's table set.
	"""
	tables = service.getTableSet()
	if not tables:
		return rootElement[
			VS.schema[
				VS.name["default"]]]

	# it's possible that multiple RDs define the same schema (don't do
	# that, it's going to cause all kinds of pain).  To avoid
	# generating bad tablesets in that case, we have the separate
	# account of schema names; the schema meta is random when
	# more than one RD exists for the schema.
	bySchema, rdForSchema = {}, {}
	for t in tables:
		bySchema.setdefault(t.rd.schema, []).append(t)
		rdForSchema[t.rd.schema] = t.rd

	schemas = []
	for schemaName, tables in sorted(bySchema.iteritems()):
		schemas.append((rdForSchema[schemaName], tables))
	
	return getTablesetForSchemaCollection(schemas, rootElement)
