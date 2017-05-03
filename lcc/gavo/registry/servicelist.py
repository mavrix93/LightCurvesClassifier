"""
The (DC-internal) service list: querying, adding records, etc.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from gavo import base
from gavo import utils
from gavo import rsc
from gavo import rscdef
from gavo import svcs
from gavo.registry import common


def getSetsForResource(restup):
	"""returns the list of set names the resource described by restup belongs to.
	"""
	tableDef = common.getServicesRD().getById("sets")
	table = rsc.TableForDef(tableDef)
	destTableDef = base.makeStruct(rscdef.TableDef,
		columns=[tableDef.getColumnByName("setName")])
	return set(str(r["setName"])
		for r in table.iterQuery(destTableDef, 
			"sourceRD=%(sourceRD)s AND resId=%(resId)s", restup))


def getSets():
	"""returns a sequence of dicts giving setName and and a list of
	services belonging to that set.
	"""
	tableDef = common.getServicesRD().getById("sets")
	table = rsc.TableForDef(tableDef)
	setMembers = {}
	for rec in table:
		setMembers.setdefault(rec["setName"], []).append(
			(rec["sourceRD"], rec["resId"]))
	return [{"setName": key, "services": value} 
		for key, value in setMembers.iteritems()]


def queryServicesList(whereClause="", pars={}, tableName="resources_join"):
	"""returns a list of services based on selection criteria in
	whereClause.

	The table queried is the resources_join view, and you'll get back all
	fields defined there.
	"""
	td = common.getServicesRD().getById(tableName)
	otd = svcs.OutputTableDef.fromTableDef(td, None)
	table = rsc.TableForDef(td)
	return [r for r in table.iterQuery(otd, whereClause, pars)]


def querySubjectsList(setName=None):
	"""returns a list of local services chunked by subjects.

	This is mainly for the root page (see web.root).  Query the
	cache using the __system__/services key to clear the cache on services
	"""
	setName = setName or 'local'
	svcsForSubjs = {}
	td = common.getServicesRD().getById("subjects_join")
	otd = svcs.OutputTableDef.fromTableDef(td, None)
	with base.getTableConn() as conn:
		for row in rsc.TableForDef(td, connection=conn).iterQuery(otd, 
				"setName=%(setName)s AND subject IS NOT NULL", {"setName": setName}):
			svcsForSubjs.setdefault(row["subject"], []).append(row)
	for s in svcsForSubjs.values():
		s.sort(key=lambda a: a["title"])
	res = [{"subject": subject, "chunk": s}
		for subject, s in svcsForSubjs.iteritems()]
	res.sort(lambda a,b: cmp(a["subject"], b["subject"]))
	return res


def getChunkedServiceList(setName=None):
	"""returns a list of local services chunked by title char.

	This is mainly for the root page (see web.root).  Query the
	cache using the __system__/services key to clear the cache on services
	reload.
	"""
	setName = setName or 'local'
	return utils.chunk(
		sorted(queryServicesList("setName=%(setName)s and not deleted", 
			{"setName": setName}), 
			key=lambda s: s.get("title").lower()),
		lambda srec: srec.get("title", ".")[0].upper())


def cleanServiceTablesFor(rd, connection):
	"""removes/invalidates all entries originating from rd from the service
	tables.
	"""
# this is a bit of a hack: We're running services#tables' newSource
#	skript without then importing anything new.
	tables = rsc.Data.create(
		common.getServicesRD().getById("tables"),
		connection=connection)
	tables.runScripts("newSource", sourceToken=rd)


def basename(tableName):
	if "." in tableName:
		return tableName.split(".")[-1]
	else:
		return tableName


def getTableDef(tableName):
	"""returns a tableDef instance for the schema-qualified tableName.

	If no such table is known to the system, a NotFoundError is raised.
	"""
	with base.AdhocQuerier(base.getTableConn) as q:
		res = list(q.query("SELECT tableName, sourceRD FROM dc.tablemeta WHERE"
				" LOWER(tableName)=LOWER(%(tableName)s)", {"tableName": tableName}))
	if len(res)!=1:
		raise base.NotFoundError(tableName, what="table",
			within="data center table listing.", hint="The table is missing from"
			" the dc.tablemeta table.  This gets filled at gavoimp time.")
	tableName, rdId = res[0]
	return base.caches.getRD(rdId).getById(basename(tableName))
