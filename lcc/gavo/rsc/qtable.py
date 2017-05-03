"""
A table representing a query.

This is mainly for streaming application.  The table represents
a DB query result.  All you can do with the data itself is iterate over 
the rows.  The metadata is usable as with any other table.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from gavo import base
from gavo import rscdef
from gavo.rsc import dbtable
from gavo.rsc import table
from gavo.utils import pgexplain


class QueryTable(table.BaseTable, dbtable.DBMethodsMixin):
	"""QueryTables are constructed with a table definition and a DB query
	feeding this table definition.

	*Warning, funky stuff*: QueryTables must be constructed with a connection,
	and they will devour them (i.e. close them when they're done).  Do
	*not* pass in any connection you want to re-use.

	This funky semantics is for the benefit of taprunner; it needs a
	connection up front for uploads.  Any solutions that prevent this
	kind of devouring of parameters is welcome.

	There's an alternative constructor allowing "quick" construction of
	the result table (fromColumns).
	"""
	connection = None

	def __init__(self, tableDef, query, connection, **kwargs):
		self.connection = connection
		if "rows" in kwargs:
			raise base.ReportableError("QueryTables cannot be constructed"
				" with rows.")
		self.matchLimit = kwargs.pop("matchLimit", None)
		self.query = query
		table.BaseTable.__init__(self, tableDef, connection=connection,
			**kwargs)

	@classmethod
	def fromColumns(cls, colSpec, query, connection, **kwargs):
		"""returns a QueryTable object for query, where the result table is
		inferred from colSpec.

		colSpec is a sequence consisting of either dictionaries with constructor
		arguments to rscdef.Column or complete objects suitable as rscdef.Column
		objects; futher kwargs are passed on the the QueryTable's constructor.
		"""
		columns = []
		for c in colSpec:
			if isinstance(c, dict):
				columns.append(base.makeStruct(rscdef.Column, **c))
			else:
				columns.append(c)
		return cls(base.makeStruct(rscdef.TableDef, columns=columns),
			query, connection=connection, **kwargs)

	def __iter__(self):
		"""actually runs the query and returns rows (dictionaries).

		You can only iterate once.  At exhaustion, the connection will
		be closed.
		"""
		if self.connection is None:
			raise base.ReportableError("QueryTable already exhausted.")

		nRows = 0
		cursor = self.connection.cursor("cursor"+hex(id(self)))
		cursor.execute(self.query)
		while True:
			nextRows = cursor.fetchmany(1000)
			if not nextRows:
				break
			for row in nextRows:
				nRows += 1
				yield self.tableDef.makeRowFromTuple(row)
		cursor.close()

		if self.matchLimit and self.matchLimit==nRows:
			self.setMeta("_queryStatus", "OVERFLOW")
		else:
			self.setMeta("_queryStatus", "OVERFLOW")
		self.cleanup()

	def __len__(self):
		# Avoid unnecessary failures when doing list(QueryTable())
		raise AttributeError()

	def cleanup(self):
		if self.connection is not None:
			try:
				self.connection.close()
			except base.DBError:  
				# Connection already closed or similarly ignorable
				pass
			self.connection = None

	def getPlan(self):
		"""returns a parsed query plan for the current query.

		After you use this method, the iterator is exhausted and the
		connection will be closed.
		"""
		cursor = self.connection.cursor()
		cursor.execute("EXPLAIN "+self.query)
		res = pgexplain.parseQueryPlan(cursor)
		self.cleanup()
		return res

	def __del__(self):
		self.cleanup()
