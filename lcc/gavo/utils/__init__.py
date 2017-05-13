"""
Miscellaneous helper modules for DACHS' python modules.

This comprises helpers and wrappers that do not need gavo.base but for some
reason or another should be within the dc package.
"""

#c Copyright 2008-2016, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


# Not checked by pyflakes: API file with gratuitous imports


import os

from gavo.utils.algotricks import (
	chunk, identity, topoSort, commonPrefixLength)

from gavo.utils.autonode import AutoNode

from gavo.utils.codetricks import (silence, ensureExpression, compileFunction,
	loadPythonModule, DeferredImport,
	memoized, identity, runInSandbox, document, 
	getKeyNoCase,
	buildClassResolver, CachedGetter, CachedResource, intToFunnyWord, 
	IdManagerMixin,
	addDefaults, iterDerivedClasses, iterDerivedObjects, iterConsecutivePairs,
	importModule, loadInternalObject, printFrames, memoizeOn, forgetMemoized,
	sandbox,
	in_dir, memoizedMethod, getTracebackAsString,
	Infimum, Supremum, NullObject,
	stealVar,
	AllEncompassingSet)

from gavo.utils.excs import *

# We reliably want the numpy version of pyfits.  Thus, always use
# from gavo.utils import pyfits rather than a direct import;  the
# "master import" is in fitstools, and we get pyfits from there.

from gavo.utils.fitstools import (readPrimaryHeaderQuick, pyfits,
	parseESODescriptors, shrinkWCSHeader, cutoutFITS, iterScaledRows,
	fitsLock)

from gavo.utils.mathtricks import *

from gavo.utils.misctricks import (Undefined, QuotedName, getfirst,
	logOldExc, sendUIEvent, pyparsingWhitechars, getWithCache,
	rstxToHTML, rstxToHTMLWithWarning, 
	couldBeABibcode,
	pyparseString, pyparseTransform, parseKVLine, makeKVLine,
	StreamBuffer, CaseSemisensitiveDict,
	NotInstalledModuleStub, grouped)

from gavo.utils.ostricks import (safeclose, urlopenRemote, 
	fgetmtime, cat, ensureDir, safeReplaced)

from gavo.utils.plainxml import StartEndHandler, iterparse, traverseETree

from gavo.utils.serializers import (defaultMFRegistry, registerDefaultMF)

from gavo.utils.stanxml import (ElementTree, xmlrender, 
	escapeAttrVal, escapePCDATA, registerPrefix, getPrefixInfo)

from gavo.utils.texttricks import (formatSize, 
	makeEllipsis, makeLeftEllipsis,
	floatRE, dateRE, datetimeRE, identifierPattern,
	datetimeToRFC2616, 
	parseDefaultDatetime, parseDefaultDate, parseDefaultTime,
	parseAccept,
	isoTimestampFmt, isoTimestampFmtNoTZ, parseISODT, formatISODT,
	formatRFC2616Date, parseRFC2616Date,
	getFileStem,
	fixIndentation, parsePercentExpression, hmsToDeg, dmsToDeg,
	fracHoursToDeg, degToHms, degToDms, getRelativePath, parseAssignments, 
	NameMap, formatSimpleTable, replaceXMLEntityRefs,
	ensureOneSlash, getRandomString,
	safe_str, iterSimpleText)
