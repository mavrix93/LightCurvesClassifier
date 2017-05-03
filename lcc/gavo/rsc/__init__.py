"""
Instantiated resources (tables, etc), plus data mangling.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.

# Not checked by pyflakes: API file with gratuitous imports

from gavo.rsc.common import DBTableError, FLUSH
from gavo.rsc.dbtable import DBTable
from gavo.rsc.qtable import QueryTable
from gavo.rsc.table import BaseTable
from gavo.rsc.tables import TableForDef, makeTableForQuery, makeTableFromRows
from gavo.rsc.data import Data, makeData, wrapTable, makeDependentsFor
from gavo.rsc.common import (getParseOptions, 
	parseValidating, parseNonValidating)
from gavo.rsc.metatable import MetaTableHandler
