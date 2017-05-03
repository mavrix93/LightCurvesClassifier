"""
Resources and their structures (DDs, TableDefs, etc), plus quite a bit 
of source parsing.

The top-level resource descriptor currently is described in a top-level 
modules.  This should probably change, it should go into this package;
that would take some work, though, since rscdesc currently needs to know
about grammars, cores, etc, available.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.

# Not checked by pyflakes: API file with gratuitous imports

from gavo.rscdef.builtingrammars import (GRAMMAR_REGISTRY, getGrammar)

from gavo.rscdef.column import (Column, Option, Values, makeOptions,
	Param)

from gavo.rscdef.common import (RDAttribute, ResdirRelativeAttribute,
	ColumnListAttribute, NamePathAttribute, ColumnList, IVOMetaMixin,
	getStandardPubDID, getAccrefFromStandardPubDID, getInputsRelativePath,
	replaceProcDefAt)

from gavo.rscdef.dddef import (DataDescriptor, Make,
	SourceSpec)

from gavo.rscdef.group import Group, ParameterReference, ColumnReference

from gavo.rscdef.mixins import MixinDef

from gavo.rscdef.procdef import ProcDef, ProcApp

from gavo.rscdef.rmkdef import RowmakerDef, ParmakerDef, MapRule

from gavo.rscdef.rmkfuncs import (addProcDefObject, IgnoreThisRow,
	getFlatName)

from gavo.rscdef.rowtriggers import IgnoreOn, TriggerPulled

from gavo.rscdef.scripting import Script

from gavo.rscdef.tabledef import (TableDef, SimpleView, makeTDForColumns)
