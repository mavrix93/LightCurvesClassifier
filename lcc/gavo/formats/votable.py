"""
A facade for parsing and generating VOTables to and from internal data
representations.

The actual implementations are in two separate modules.  Always access
them through this module.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.

# Not checked by pyflakes: API file with gratuitous imports

from gavo.formats.votableread import (makeTableDefForVOTable,
	makeDDForVOTable, uploadVOTable,
	AutoQuotedNameMaker, QuotedNameMaker)
from gavo.formats.votablewrite import (getAsVOTable,
	writeAsVOTable, makeVOTable, VOTableContext)
