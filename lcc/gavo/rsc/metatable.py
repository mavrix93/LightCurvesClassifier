"""
Handling table metadata in the dc.(table|column)meta tables.

This has been a mediocre plan, and it's almost unused these days except
to locate RDs for tables.  Hence, we should tear this entire thing down
and have the table->RD mapping stowed somewhere else.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.

import functools

from gavo import base



def _retryProtect(m):
	"""decorates m such that any function call is retried after self.reset
	is called.
	"""
	def f(self, *args, **kwargs):
		try:
			return m(self, *args, **kwargs)
		except:
			self.reset()
			return m(self, *args, **kwargs)

	return functools.update_wrapper(f, m)


class MetaTableHandler(object):
	"""an interface to DaCHS meta tables.

	This used to be a fairly complex interface to all sorts for DC-related
	metadata.  These day, the only thing it does is figure out where
	table definitions reside and which are available for ADQL.  This thing 
	has been a bad idea all around.

	Though you can construct MetaTableHandlers of your own, you should
	use base.caches.getMTH(None) when reading.
	"""
	def __init__(self):
		self.rd = base.caches.getRD("__system__/dc_tables")
		self._createObjects()

	def _createObjects(self):
		self.readerConnection = base.getDBConnection(
			"trustedquery", autocommitted=True)

	def close(self):
		try:
			self.readerConnection.close()
		except base.InterfaceError:
			# connection already closed
			pass

	def reset(self):
		self.close()
		self._createObjects()

	@_retryProtect
	def getTableDefForTable(self, tableName):
		"""returns a TableDef for tableName.

		As it is not a priori clear which RD a given table lives in,
		this goes through dc.tablemeta to figure this out.  The
		object comes from the actual RD, though, so this might very well
		trigger database action and RD loading.
		"""
		if not "." in tableName:
			tableName = "public."+tableName
		
		for row in self.readerConnection.queryToDicts(
				"select sourcerd, tablename from dc.tablemeta where"
				"  lower(tableName)=%(tableName)s",
				{"tableName": tableName.lower()}):
			break
		else:
			raise base.ui.logOldExc(
				base.NotFoundError(tableName, "table", "dc_tables"))

		return base.caches.getRD(row["sourcerd"]
			).getById(row["tablename"].split(".")[-1])

	@_retryProtect
	def getTAPTables(self):
		"""returns a list of all names of tables accessible through TAP in
		this data center.
		"""
		return [r["tablename"] for r in
			self.readerConnection.queryToDicts(
				"select tablename from dc.tablemeta where adql")]


def _getMetaTable(ignored):
	return MetaTableHandler()

base.caches.makeCache("getMTH", _getMetaTable)
