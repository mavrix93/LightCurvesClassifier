"""
This should evolve into a useful API to GAVO code for more-or-less external
clients.

For now, it just makes sure that standard RDs can be imported.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.

# Not checked by pyflakes: API file with gratuitous imports

from gavo import base
from gavo import rscdesc
from gavo import votable
from gavo import web

getRD = base.caches.getRD
RD = rscdesc.RD

from gavo.base import (getConfig, setConfig,
	getDBConnection,
	UnmanagedQuerier, AdhocQuerier, 
	getTableConn, getAdminConn, getUntrustedConn,
	getWritableAdminConn,
	NoMetaKey, Error, StructureError, ValidationError, LiteralParseError, 
	ReportableError, NotFoundError, RDNotFound, SourceParseError,
	parseFromString,
	ui)

from gavo.formats.votablewrite import (writeAsVOTable, getAsVOTable,
	VOTableContext)

from gavo.rsc import (TableForDef, DBTable, makeData, parseValidating,
	parseNonValidating, getParseOptions, Data)

from gavo.rscdef import TableDef, getFlatName

from gavo.user.logui import LoggingUI

from gavo.votable import VOTableError, ADQLTAPJob
