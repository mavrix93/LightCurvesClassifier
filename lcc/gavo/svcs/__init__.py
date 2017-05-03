"""
Services, cores, and support.

A Service is something that receives some sort of structured data (typically,
a nevow context), processes it into input data using a grammar (default is
the ContextGrammar), pipes it through a core to receive a data set and
optionally tinkers with that data set.

A core receives a data set, processes it, and returns another data set.

Support code is in common.  Most importantly, this is QueryMeta, a data
structure carrying lots of information on the query being processed.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.

# Not checked by pyflakes: API file with gratuitous imports

from gavo.svcs.common import (Error, UnknownURI, ForbiddenURI, WebRedirect,
	Authenticate, BadMethod,
	QueryMeta, emptyQueryMeta, getTemplatePath, loadSystemTemplate)

from gavo.svcs.core import getCore, Core, CORE_REGISTRY

from gavo.svcs.customcore import CustomCore

from gavo.svcs.customwidgets import (DBOptions, FormalDict, 
	SimpleSelectChoice, 
	NumericExpressionField, DateExpressionField, StringExpressionField, 
	ScalingTextArea)

from gavo.svcs.inputdef import (
	InputTable, InputKey, ContextGrammar, InputDescriptor,
	makeAutoInputDD)

from gavo.svcs.outputdef import OutputField, OutputTableDef

from gavo.svcs.renderers import RENDERER_REGISTRY, getRenderer

from gavo.svcs.runner import runWithData

from gavo.svcs.service import (Service, SvcResult, Publication, PreparsedInput)

from gavo.svcs.standardcores import (DBCore, CondDesc,
	mapDBErrors)

from gavo.svcs.computedcore import ComputedCore

from gavo.svcs.uploadcores import UploadCore
