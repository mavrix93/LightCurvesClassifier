"""
Writing tables in JSON.

We use python's built-in json engine to write an -- as yet -- ad-hoc json
format that essentially looks like this:

{
	"contains": "table",
	"columns": { (column metadata more or less as in VOTable) }
	"data": { (rows as tuples) }
	("warnings": [...])
}

No streaming at all is forseen for this format at this point.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import json

from gavo import base
from gavo import rsc
from gavo.formats import common


class JSONMetaBuilder(base.MetaBuilder):
	"""A MetaBuilder for mapping table meta information into our standard
	JSON structure.
	"""
	def __init__(self, jsonStructure):
		self.result = jsonStructure
		base.MetaBuilder.__init__(self)
	
	def getResult(self):
		return self.result
	
	def enterValue(self, value):
		if self.curAtoms[-1]=="_warning":
			self.result.setdefault("warnings", []).append(unicode(value))
		elif self.curAtoms[-1]=="_queryStatus":
			self.result["queryStatus"] = unicode(value)


def _getJSONColumns(serManager):
	"""returns a sequence of VOTable-like column description dictionaries.
	"""
	res = []
	for annCol in serManager:
		res.append(annCol.annotations.copy())
		res[-1].pop("displayHint", None)
		res[-1].pop("winningFactory", None)
		res[-1].pop("nullvalue", None)
		res[-1].pop("note", None)
	return res


def _getJSONParams(serManager):
	"""returns a dict of param dicts.
	"""
	result = {
		'contains': "params",
	}
	for param in serManager.table.iterParams():
		if param.value is not None:
			result[param.name] = {
				'value': param.value,
				'unit': param.unit,
				'ucd': param.ucd,
				'description': param.description,}
	return result


def _getJSONStructure(table, acquireSamples=False):
	"""returns a dictionary representing table for JSON serialisation.
	"""
	if isinstance(table, rsc.Data):
		table = table.getPrimaryTable()
	sm = base.SerManager(table, acquireSamples=acquireSamples)
	
	result = {
		'contains': "table",
		'params': _getJSONParams(sm),
		'columns': _getJSONColumns(sm),
		'data': list(sm.getMappedTuples()),
	}
	table.traverse(JSONMetaBuilder(result))
	return result


def writeTableAsJSON(table, target, acquireSamples=False):
	"""writes table to the target in ad-hoc JSON.
	"""
	jsonPayload = _getJSONStructure(table, acquireSamples)
	return json.dump(jsonPayload, target, encoding="utf-8")


# NOTE: while json could easily serialize full data elements,
# right now we're only writing single tables.
common.registerDataWriter("json", writeTableAsJSON, "application/json",
	"JSON")
