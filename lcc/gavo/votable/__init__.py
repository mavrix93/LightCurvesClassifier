"""
GAVO's VOTable python library.
"""

#c Copyright 2008-2016, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


# Not checked by pyflakes: API file with gratuitous imports

from gavo.votable.coding import unravelArray

from gavo.votable.common import (VOTableError, VOTableParseError,
	BadVOTableLiteral, BadVOTableData)

# escapeX were part of this package's interface
from gavo.utils.stanxml import escapePCDATA, escapeAttrVal

from gavo.votable.model import VOTable as V, voTag

from gavo.votable.paramval import guessParamAttrsForValue, serializeToParam

from gavo.votable.parser import parse, parseString, readRaw

from gavo.votable.simple import load, loads, save, makeDtype

from gavo.votable.tablewriter import (
	DelayedTable, OverflowElement, asString, write)

from gavo.votable.tapquery import ADQLTAPJob, ADQLSyncJob
from gavo.votable.tapquery import Error as TAPQueryError
