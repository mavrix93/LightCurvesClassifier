"""
Tables, base and in memory.

Basically, a table consists of a list of dictionaries (the rows) and a
table definition (resdef.TableDef).

You should, in general, not construct the tables directly but use
the tables.TableForDef factory.  The reason is that some classes ignore
certain aspects of TableDefs (indices, uniqueForceness) or may not be
what TableDef requires at all (onDisk).  Arguably there should be
different TableDefs for all these aspects, but then I'd have a plethora
of TableDef elements, which I think is worse than a factory function.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from gavo import base
from gavo import rscdef
from gavo.rsc import common

import sys

class Error(base.Error):
	pass


class _Feeder(object):
	"""A device for getting data into a table.

	A feeder is a context manager that rejects all action from without
	the controlled section.  Within the controlled section, you can use:

		- add(row) -> None -- add row to table.  This may raise all kinds
			of crazy exceptions.
		- flush() -> None -- flush out all data that may be cached to the table
		  (this is done automatically on a successful exit)
		- reset() -> None -- discard any data that may still wait to be 
		  flushed to the table

	At the end of the controlled block, the importFinished or importFailed 
	methods or the parent table are called depending on whether all is
	well or an exception happened.  If importFinished raises and
	exception, it is handed on to importFailed and re-raised if importFailed
	returns False.

	The batch size constructor argument is for the benefit of DBTables.

	The flush and reset methods are necessary when you do explicit buffering and
	connection management; you will need to call flush before committing a
	transaction and reset before rolling one back.
	"""
	def __init__(self, table, batchSize=1024):
		self.table = table
		self.nAffected = 0
		self.active = False

	def _assertActive(self):
		if not self.active:
			raise base.DataError("Trying to feed a dormant feeder.")

	def getAffected(self):
		return self.nAffected

	def add(self, row):
		self._assertActive()
		if self.table.validateRows:
			self.table.tableDef.validateRow(row)
		self.table.addRow(row)
		self.nAffected += 1

	def flush(self):
		self._assertActive()
		# no-op for ram feeder

	def reset(self):
		self._assertActive()
		# no-op for ram feeder

	def __enter__(self):
		self.active = True
		return self

	def __exit__(self, excType=None, excVal=None, excTb=None):
		try:
			if excType is None: # all ok
				try:
					self.table.importFinished()
				except:
					if not self.table.importFailed(*sys.exc_info()):
						raise
			else:           # exception occurred in controlled block
				self.table.importFailed(excType, excVal, excTb)
		finally:
			self.active = False
		return False
	

def _makeFailIncomplete(name):
	def fail(self, *args, **kwargs):
		raise NotImplementedError("%s is an incomplete Table implementation."
			"  No method '%s' defined."%(self.__class__.__name__, name))
	return fail


class BaseTable(base.MetaMixin, common.ParamMixin):
	"""is a container for row data.

	Tables consist of rows, where each row maps column names to their
	value for that row.  The rows are accessible at least by iterating
	over a table.

	Tables get constructed with a tableDef and keyword arguments.  For
	convenience, tables must accept any keyword argument and only pluck those
	out it wants.

	Here's a list of keywords used by BaseTables or known subclasses:

		- validateRows -- have rows be validated by the tableDef before addition
			(all Tables)
		- rows -- a list of rows the table has at start (InMemoryTables; DbTables
			will raise an error on these).
		- connection -- a database connection to use for accessing DbTables.
		- votCasts -- a dictionary mapping column names to dictionaries overriding
			keys of valuemappers.AnnontatedColumn.
		- params -- a dictionary mapping param keys to values, where python
		  values and literals allowed.

	You can add rows using the addRow method.  For bulk additions, however,
	it may be much more efficient to call getFeeder (though for in-memory
	tables, there is no advantage).

	Tables can run "scripts" if someone furnishes them with a _runScripts
	method.  This currently is only done for DBTables.  See Scripting_.

	Initial Metadata is populated from the tableDef.

	Tables have to implement the following methods:

		- __iter__
		- __len__
		- __getitem__(n) -- returns the n-th row or raises an IndexError
		- removeRow(row) removes a row from the table or raises an
			IndexError if the row does not exist.  This is a slow, O(n) operation.
		- addRow(row) -- appends new data to the table
		- getRow(*args) -- returns a row by the primary key.  If no primary key
			is defined, a ValueError is raised, if the key is not present, a
			KeyError.  An atomic primary key is accessed through its value,
			for compound primary keys a tuple must be passed.
		- getFeeder(**kwargs) -> feeder object -- returns an object with add and 
			exit methods.  See feeder above.
		- importFinished() -> None -- called when a feeder exits successfully
		- importFailed(*excInfo) -> boolean -- called when feeding has failed;
			when returning True, the exception that has caused the failure
			is not propagated.
		- close() -> may be called by clients to signify the table will no
			longer be used and resources should be cleared (e.g., for DBTables
			with private connections).
	"""
	_runScripts = None

	def __init__(self, tableDef, **kwargs):
		base.MetaMixin.__init__(self)
		self.tableDef = tableDef
		self.setMetaParent(self.tableDef.getMetaParent())
		self.meta_ = self.tableDef.meta_.copy()
		self.validateRows = kwargs.get("validateRows", False)
		self.votCasts = kwargs.get("votCasts", {})
		self.role = kwargs.get("role")
		self._initParams(self.tableDef, kwargs.pop("params", None))

	__iter__ = _makeFailIncomplete("__iter__")
	__len__ = _makeFailIncomplete("__len__")
	removeRow = _makeFailIncomplete("removeRow")
	addRow = _makeFailIncomplete("addRow")
	getRow = _makeFailIncomplete("getRow")
	getFeeder = _makeFailIncomplete("getFeeder")

	def addTuple(self, tupRow):
		self.addRow(self.tableDef.makeRowFromTuple(tupRow))

	def importFinished(self):
		pass
	
	def importFailed(self, *excInfo):
		return False

	def close(self):
		pass

	def runScripts(self, phase, **kwargs):
		if self._runScripts:  # if defined, it was set by data and make.
			self._runScripts(self, phase, **kwargs)


class InMemoryTable(BaseTable):
	"""is a table kept in memory.

	This table only keeps an index for the primaray key.  All other indices
	are ignored.
	"""
	def __init__(self, tableDef, **kwargs):
		BaseTable.__init__(self, tableDef, **kwargs)
		self.rows = kwargs.get("rows", [])
	
	def __iter__(self):
		return iter(self.rows)
	
	def __len__(self):
		return len(self.rows)

	def removeRow(self, row):
		self.rows.remove(row)

	def addRow(self, row):
		if self.validateRows:
			try:
				self.tableDef.validateRow(row)
			except rscdef.IgnoreThisRow:
				return
		self.rows.append(row)


	def getRow(self, *args):
		raise ValueError("Cannot use getRow in index-less table")

	def getFeeder(self, **kwargs):
		return _Feeder(self, **kwargs)


class InMemoryIndexedTable(InMemoryTable):
	"""is an InMemoryTable for a TableDef with a primary key.
	"""
	def __init__(self, tableDef, **kwargs):
		InMemoryTable.__init__(self, tableDef, **kwargs)
		if not self.tableDef.primary:
			raise Error("No primary key given for InMemoryIndexedTable")
		self._makeRowIndex()

	def removeRow(self, row):
# This remains slow since we do not keep the index of a row in self.rows
		InMemoryTable.removeRow(self, row)
		del self.rowIndex[self.tableDef.getPrimaryIn(row)]

	def addRow(self, row):
		if self.validateRows:
			try:
				self.tableDef.validateRow(row)
			except rscdef.IgnoreThisRow:
				return
		self.rows.append(row)
		self.rowIndex[self.tableDef.getPrimaryIn(row)] = row

	def getRow(self, *args):
		return self.rowIndex[args]

	def _makeRowIndex(self):
		"""recreates the index of primary keys to rows.
		"""
		self.rowIndex = {}
		for r in self.rows:
			self.rowIndex[self.tableDef.getPrimaryIn(r)] = r


class UniqueForcedTable(InMemoryIndexedTable):
	"""is an InMemoryTable with an enforced policy on duplicate
	primary keys.

	See resdef.TableDef for a discussion of the policies.
	"""
	def __init__(self, tableDef, **kwargs):
		# hide init rows (if present) in the next line to not let
		# duplicate primaries slip in here.
		rows = kwargs.pop("rows", [])
		InMemoryIndexedTable.__init__(self, tableDef, **kwargs)
		try:
			self.resolveConflict = {
				"check": self._ensureRowIdentity,
				"drop": self._dropNew,
				"overwrite": self._overwriteOld,
				"dropOld": self._overwriteOld,
			}[self.tableDef.dupePolicy]
		except KeyError, msg:
			raise base.ui.logOldExc(
				Error("Invalid conflict resolution strategy: %s"%str(msg)))
		for row in rows:
			self.addRow(row)

	def _ensureRowIdentity(self, row, key):
		"""raises an exception if row is not equivalent to the row stored
		for key.

		This is one strategy for resolving primary key conflicts.
		"""
		storedRow = self.rowIndex[key]
		if row.keys()!=storedRow.keys():
			raise Error("Differing rows for primary key %s: %s vs. %s"%(
				key, self.rowIndex[key], row))
		for colName in row:
			if row[colName] is None or storedRow[colName] is None:
				continue
			if row[colName]!=storedRow[colName]:
				raise base.ValidationError(
					"Differing rows for primary key %s;"
					" %s vs. %s"%(key, row[colName],
						storedRow[colName]), colName=colName, row=row)

	def _dropNew(self, row, key):
		"""does nothing.

		This is for resolution of conflicting rows (the "drop" strategy).
		"""
		pass
	
	def _overwriteOld(self, row, key):
		"""overwrites the existing rows with key in table with rows.

		This is for resolution of conflicting rows (the "overwrite"
		strategy).

		Warning: This is typically rather slow.
		"""
		storedRow = self.rowIndex[key]
		self.removeRow(storedRow)
		return self.addRow(row)

	def addRow(self, row):
		if self.validateRows:
			try:
				self.tableDef.validateRow(row)
			except rscdef.IgnoreThisRow:
				return
		key = self.tableDef.getPrimaryIn(row)
		if key in self.rowIndex:
			return self.resolveConflict(row, key)
		else:
			self.rowIndex[key] = row
		return InMemoryIndexedTable.addRow(self, row)
