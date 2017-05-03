"""
Common interface to table implementations.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from gavo import rscdef
from gavo.rsc import common
from gavo.rsc import dbtable
from gavo.rsc import table



def TableForDef(tableDef, suppressIndex=False, 
		parseOptions=common.parseNonValidating, **kwargs):
	"""returns a table instance suitable for holding data described by
	tableDef.

	This is the main interface to table instancation.

	suppressIndex=True can be used to suppress index generation on 
	in-memory tables with primary keys.  Use it when you are sure
	you will not need the index (e.g., if staging an on-disk table).

	See getParseOptions above for parseOptions.
	"""
	if isinstance(tableDef, rscdef.SimpleView):
		tableDef = tableDef.getTableDef()
	if tableDef.onDisk:
		if tableDef.viewStatement:
			cls = dbtable.View
		else:
			cls = dbtable.DBTable
		return cls(tableDef, suppressIndex=suppressIndex, 
			validateRows=parseOptions.validateRows,
			commitAfterMeta=parseOptions.commitAfterMeta,
			tableUpdates=parseOptions.doTableUpdates, **kwargs)
	elif tableDef.forceUnique:
		return table.UniqueForcedTable(tableDef, 
			validateRows=parseOptions.validateRows, **kwargs)
	elif tableDef.primary and not suppressIndex:
		return table.InMemoryIndexedTable(tableDef, 
			validateRows=parseOptions.validateRows, **kwargs)
	else:
		return table.InMemoryTable(tableDef, validateRows=parseOptions.validateRows,
			**kwargs)


def makeTableForQuery(queriedTable, resultTableDef, fragment, pars, 
		distinct=False, limits=None, suppressIndex=True,
		connection=None):
	"""returns a table from resultTableDef containing the results for
	a query for fragment and pars in queriedTable.

	resultTableDef must be a TableDef with svc.OutputField columns
	(which you can easily generate from columns using 
	svc.OutputTableDef.fromColumns)

	queriedTable must be a DBTable instance.

	The other arguments are just handed through to dbtable.iterQuery.
	"""
	return TableForDef(resultTableDef, suppressIndex=suppressIndex,
		connection=connection,
		rows=[r for r in queriedTable.iterQuery(resultTableDef, fragment, pars,
			distinct, limits)])


def makeTableFromRows(tableDef, iterator):
	"""returns a table for tableDef, taking raw rows from iterator
	and using a default-None rowmaker.
	"""
	t = TableForDef(tableDef)
	rmk = rscdef.RowmakerDef.makeTransparentFromTable(tableDef
		).compileForTableDef(tableDef)
	for row in iterator:
		t.addRow(rmk(row, t))
	return t
