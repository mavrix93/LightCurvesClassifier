"""
Parsing identifiers, getting res tuples and resobs from them.

The DC-internal identifiers are, by default, formed as
ivo://<authority-from-config>/<sourceRD path>/<id within path>.

Thus, all renderers of a given service have the same ivo-id, which is
to say, they are all just capabilities on the same record.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import re

from gavo import base
from gavo.registry import common
from gavo.registry import nonservice
from gavo.registry import servicelist


def computeIdentifierFromRestup(restup):
	"""returns an identifier from a res tuple.
	"""
	return restup["ivoid"]


_idPattern = re.compile("ivo://(\w[^!;:@%$,/]+)(/[^?#]*)?")

def parseIdentifier(identifier):
	"""returns a pair of authority, resource key for identifier.

	Identifier has to be an ivo URI.

	In the context of the gavo DC, the resource key either starts with
	static/ or consists of an RD id and a service ID.
	"""
	mat = _idPattern.match(identifier)
	if not mat:
		raise common.IdDoesNotExist(identifier)
	return mat.group(1), (mat.group(2) or "")[1:]


def getRestupFromIdentifier(identifier):
	"""returns the record for identifier in the services table.
	"""
	matches = servicelist.queryServicesList(
		"ivoid=%(identifier)s",
		locals(), tableName="resources")
	if len(matches)!=1:
		raise common.IdDoesNotExist(identifier)
	return matches[0]


def getResobFromRestup(restup):
	"""returns a resob for a res tuple.

	restup at least has to contain the sourceRD and resId fields.

	The item that is being returned is either a service or a
	NonServiceResource (including DeletedResource).  All of these have
	a getMeta method and should be able to return the standard DC
	metadata.
	"""
	if restup["deleted"]:
		return base.makeStruct(nonservice.DeletedResource,
			resTuple=restup)
	sourceRD, resId = restup["sourceRD"], restup["resId"]
	try:
		return base.caches.getRD(sourceRD).getById(resId)
	except KeyError:
		raise base.ui.logOldExc(base.NotFoundError(resId, what="service",
			within="RD %s"%sourceRD, hint="This usually happens when you"
			" forgot to run gavopublish %s"%sourceRD))


def getResobFromIdentifier(identifier):
	"""returns a resob for an identifier.
	"""
	return getResobFromRestup(getRestupFromIdentifier(identifier))
