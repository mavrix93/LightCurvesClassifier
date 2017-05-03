"""
Registry interface: service list, record generation, OAI endpoint.

Our identifiers have the form

ivo://<authority>/<rd-path>/service-id

except for the authority itself, which is, of course, just
ivo://<authority>.

authority is given by authority in the ivoa section of config.

This package deals with two ways to represent resources: 

	- res tuples, as returned by servicelist.queryServicesList and used
		whenever no or little metadata is necessary.  Contrary to what their
		name suggests, they are actually dictionaries.

	- res objects.  Those are the actual objects (e.g., svc.Service or
		similar).  Since they may be expensive to construct (though, of
		course, most of them ought to be cached on reasonably busy sites),
		they are only constructed when real metadata is required.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.

# Not checked by pyflakes: API file with gratuitous imports

from gavo.registry.common import *
from gavo.registry import oaiinter      # registration of RegistryCore
from gavo.registry import servicelist   # registration of getWebServiceList


from gavo.registry.builders import (getVOResourceElement, 
	getVORMetadataElement)
from gavo.registry.identifiers import (getResobFromIdentifier,
	getResobFromRestup, parseIdentifier)
from gavo.registry.publication import findAllRDs
from gavo.registry.servicelist import getTableDef
from gavo.registry.nonservice import ResRec
from gavo.registry.tableset import getTablesetForService
