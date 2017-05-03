"""
Dropping resources.  For now, you can only drop entire RDs.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import os

from gavo import api
from gavo import base
from gavo.protocols import tap
from gavo.user import common


def _do_dropTable(tableName, conn):
	"""deletes rows generated from tableName from the DC's metadata
	(and tableName itself).
	"""
	q = base.UnmanagedQuerier(conn)
	for metaTableName, columnName in [
			("dc.tablemeta", "tableName"),
			("ivoa._obscoresources", "tableName"),
			("tap_schema.tables", "table_name")]:
		if q.tableExists(metaTableName):
			q.query("delete from %s where %s=%%(tableName)s"%(
				metaTableName, columnName),
				{"tableName": tableName})

	#	POSSIBLE SQL INJECTION when tableName is a suitably wicked
	# quoted name; right now, this is mitigated by the fact that
	# people that can call this don't need SQL injection since
	# they can execute anything gavoadmin can anyway.
	if q.viewExists(tableName):
		q.query("drop view "+tableName)
	elif q.tableExists(tableName):
		q.query("drop table "+tableName)


def dropTable():
	"""tries to "manually" purge a table from the DC's memory.

	This is a "toplevel" function inteded to be called by cli directly.
	"""
	def parseCmdline():
		from gavo.imp.argparse import ArgumentParser
		parser = ArgumentParser(
			description="Removes all traces of the named table within the DC.")
		parser.add_argument("tablename", help="The name of the table to drop,"
		 	" including the schema name.", nargs="+")
		return parser.parse_args()
	
	opts = parseCmdline()
	
	with base.getWritableAdminConn() as conn:
		for tableName in opts.tablename:
			_do_dropTable(tableName, conn)
		conn.execute("DELETE FROM dc.products WHERE sourcetable=%(t)s",
			{'t': tableName})


def _do_dropRD(opts, rdId, selectedIds=()):
	"""drops the data and services defined in the RD selected by rdId.
	"""
	try:
		rd = api.getRD(os.path.join(os.getcwd(), rdId))
	except api.RDNotFound:
		try:
			rd = api.getRD(rdId, forImport=True)
		except api.RDNotFound:
			rd = None
	

	with base.AdhocQuerier(base.getWritableAdminConn) as querier:
		if rd is not None:
			if opts.dropAll:
				dds = rd.dds
			else:
				dds = common.getPertainingDDs(rd, selectedIds)

			parseOptions = api.getParseOptions(systemImport=opts.systemImport)

			for dd in dds:
				api.Data.drop(dd, connection=querier.connection, 
					parseOptions=parseOptions)

			if not selectedIds or opts.dropAll:
				from gavo.registry import servicelist
				servicelist.cleanServiceTablesFor(rd, querier.connection)
				tap.unpublishFromTAP(rd, querier.connection)
		
		else:
			# If the RD doesn't exist any more, just manually purge it
			# from wherever it could have been mentioned.
			for tableName in ["dc.tablemeta", "tap_schema.tables", 
					"tap_schema.columns", "tap_schema.keys", "tap_schema.key_columns",
					"dc.resources", "dc.interfaces", "dc.sets", "dc.subjects",
					"dc.authors", "dc.res_dependencies"]:
				if querier.tableExists(tableName):
					querier.query(
						"delete from %s where sourceRd=%%(sourceRD)s"%tableName,
						{"sourceRD": rdId})


def dropRD():
	"""parses the command line and drops data and services for the
	selected RD.

	This is a "toplevel" function inteded to be called by cli directly.
	"""
	def parseCmdline():
		from gavo.imp.argparse import ArgumentParser
		parser = ArgumentParser(
			description="Drops all tables made in an RD's data element.")
		parser.add_argument("rdid", help="RD path or id to drop")
		parser.add_argument("ddids", help="Optional dd id(s) if you"
			" do not want to drop the entire RD.  Note that no service"
			" publications will be undone if you give DD ids.", nargs="*")
		parser.add_argument("-s", "--system", help="drop tables even if they"
			" are system tables",
			dest="systemImport", action="store_true")
		parser.add_argument("--all", help="drop all DDs in the RD,"
			" not only the auto ones (overrides manual selection)",
			dest="dropAll", action="store_true")
		return parser.parse_args()

	opts = parseCmdline()
	rdId = opts.rdid
	ddIds = None
	if opts.ddids:
		ddIds = set(opts.ddids)
	_do_dropRD(opts, rdId, ddIds)
