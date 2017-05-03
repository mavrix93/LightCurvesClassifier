"""
Basic code for defining objects in the data center: Structures, their 
attributes, fundamental VO conventions.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.

# Not checked by pyflakes: API file with gratuitous imports

# This doesn't belong here and it should go away again, but right now,
# astLib has an issue in the de_DE (and probably other) locales.
import locale, os
os.environ["LC_ALL"] = 'C'
locale.setlocale(locale.LC_ALL, 'C')

from gavo.base import caches

from gavo.base.attrdef import *

from gavo.base.complexattrs import *

from gavo.base.config import(
	get as getConfig, set as setConfig,
	getDBProfile)

from gavo.base.coords import Box

from gavo.base.events import EventDispatcher

from gavo.base.macros import (StandardMacroMixin, MacroPackage,
	MacDefAttribute, MacroError, ExpansionDelegator)

ui = EventDispatcher()
del EventDispatcher

from gavo.utils import Undefined

from gavo.base.common import *

from gavo.base.literals import *

from gavo.base.meta import (
	MetaSyntaxError, MetaError, MetaCardError, NoMetaKey,
	InfoItem as MetaInfoItem,
	MetaMixin, ComputedMetaMixin,
	MetaBuilder,
	getMetaText, makeMetaValue, makeMetaItem)

from gavo.base.metavalidation import MetaValidationError, validateStructure

from gavo.base.observer import ObserverBase, listensTo

from gavo.base.osinter import (getGroupId, makeSharedDir, makeSitePath,
	getBinaryName, makeAbsoluteURL, openDistFile, getVersion)

from gavo.base.parsecontext import (
	IdAttribute, OriginalAttribute, ReferenceAttribute, ParseContext,
	ReferenceListAttribute, resolveId, resolveCrossId, resolveNameBased)

from gavo.base.sqlsupport import (getDBConnection, 
	DBError, QueryCanceledError, IntegrityError,
	AdhocQuerier, UnmanagedQuerier,
	savepointOn,
	connectionConfiguration,
	getUntrustedConn,
	getTableConn, getAdminConn, getUntrustedConn,
	getWritableTableConn, getWritableAdminConn, getWritableUntrustedConn,
	setDBMeta, getDBMeta)

from gavo.base.structure import (Structure, ParseableStructure, 
	DataContent, makeStruct, RestrictionMixin)


from gavo.base.typesystems import *

from gavo.base.valuemappers import (SerManager, ValueMapperFactoryRegistry,
	VOTNameMaker)

from gavo.base.sqlmunge import (getSQLForField, getSQLKey, 
	joinOperatorExpr)

from gavo.base.unitconv import (
	computeConversionFactor, parseUnit, computeColumnConversions,
	IncompatibleUnits, BadUnit)

from gavo.base.xmlstruct import parseFromString, parseFromStream, feedTo

# preferred MIME type for VOTables we make
votableType = "application/x-votable+xml"

__version__ = getVersion()

DEBUG = False
IS_DACHS_SERVER = False
