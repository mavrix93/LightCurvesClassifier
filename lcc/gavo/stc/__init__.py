"""
Support for the IVOA Space-Time-Coordinate data model.

We're dealing with a huge data model here that probably can't be
fully implemented in any sense of the word.

So, we have a stripped down data model in the form of an abstract syntax
tree here (defined in the dm submodule).  This can be built directly or
from various input formats (XXXast submodules).  From the AST, you can
also build various output formats (XXXgen submodules).

All other operations should be performed on the AST.

Note that this is slow as a dog.  I doubt we'll ever see performant STC
implementations.  This is really intended for one-shot transformations,
e.g. into functions or a query language.  Don't do any transformations
in serious loops.
"""

#c Copyright 2008-2016, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


# Not checked by pyflakes: API file with gratuitous imports

import sys

from gavo.stc.common import (STCError, STCSParseError, STCLiteralError,
	STCValueError, STCNotImplementedError, STCUnitError,
	STCNamespace, stcSpaceRefFrames, stcRefPositions, ColRef)

from gavo.stc.times import (parseISODT, 
	jYearToDateTime, dateTimeToJYear,
	bYearToDateTime, dateTimeToBYear,
	jdnToDateTime, dateTimeToJdn,
	mjdToDateTime, dateTimeToMJD,
	JD_MJD,
	datetimeMapperFactory)

# hardcore stc only from 2.5 upwards
if sys.version_info[0]>=2 and sys.version_info[1]>4:  
	from gavo.stc.conform import conform as conformTo, getSimple2Converter

	from gavo.stc.dm import fromPgSphere

	from gavo.stc.eq import EquivalencePolicy, defaultPolicy

	from gavo.stc.stcsast import parseSTCS, parseQSTCS

	from gavo.stc.stcsgen import getSTCS, getSpatialSystem

	from gavo.stc.stcx import STC

	from gavo.stc.stcxast import parseSTCX, parseFromETree

	from gavo.stc.stcxgen import astToStan, getSTCXProfile, nodeToStan

	from gavo.stc.syslib import getLibrarySystem

	from gavo.stc.tapstc import (TAP_SYSTEMS, getTAPSTC, getSimpleSTCSParser,
		parseSimpleSTCS, simpleSTCSToPolygon)

	from gavo.stc.utypegen import getUtypes

	from gavo.stc.utypeast import parseFromUtypes

	def getSTCX(ast, rootElement):
		return astToStan(ast, rootElement)
