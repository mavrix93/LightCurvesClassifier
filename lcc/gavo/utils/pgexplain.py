"""
Parsing Postgres query plans (somewhat).
"""

#c Copyright 2008-2016, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import re

_opKVRE = r"(?P<operation>[^\s][^(]*[^\s])\s+\((?P<keyval>[^)]*)\)"
_rootLinePat = re.compile(r"^%s"%_opKVRE)
_otherLinePat = re.compile(r"^(?P<indent>\s+)->\s+%s"%_opKVRE)
_kvPat = re.compile(r"(\w+)=([^\s]+)")


def _parseKV(kvLiteral):
	return dict((mat.group(1), mat.group(2))
		for mat in _kvPat.finditer(kvLiteral))


def _lexPlannerLine(inputLine):
	"""returns a triple of indent, operation, operation dict for an explain 
	output line.

	The explainer output lines are usually 
	[<indent> "->" ]<operation> "(" <key-value-pairs> ")"

	Lines not having this format make this function return None.
	"""
	mat = _rootLinePat.match(inputLine)
	if mat:
		return 0, mat.group("operation"), _parseKV(mat.group("keyval"))
	mat = _otherLinePat.match(inputLine)
	if mat:
		return (len(mat.group("indent")), mat.group("operation"), 
			_parseKV(mat.group("keyval")))
	# fallthrough
	return None


def _parseVal_cost(val):
	return tuple(map(float, val.split("..")))

def _parseVal_rows(val):
	return int(val)


def _parseKeyedValues(kvDict):
	"""parses the values in an operation dictionary.
	"""
	newKV = {}
	for key, value in kvDict.iteritems():
		try:
			newKV[str(key)] = globals()["_parseVal_"+key](value)
		except KeyError:
			pass
	return newKV


def _getChildren(phrases, childIndent):
	"""returns the children with indented by childIndent.

	A helper for _makePlannerNode.
	"""
	children = []
	while phrases and phrases[0][0]==childIndent:
		children.append(_makePlannerNode(phrases))
	return tuple(children)


def _makePlannerNode(phrases):
	"""returns a tuple tree for phrases.

	The tree structure is explained at parseQueryPlan, phrases are results
	of _lexPlannerTree.
	"""
	p = phrases.pop(0)
	children = ()
	if phrases:
		children = _getChildren(phrases, phrases[0][0])
	return (str(p[1]), 
		_parseKeyedValues(p[2])
		)+children


def parseQueryPlan(pgPlan):
	"""returns a parsed query plan from an iterator returning postgres
	explain lines.

	pgPlan usually is a cursor resulting from an EXPLAIN query.

	The returned query plan is a tuple tree containing nodes of 
	(op type, op dict, (children)), where op dict contains  key-value
	pairs for things like cost, rows, etc.
	"""
	phrases = [toks for toks in (_lexPlannerLine(tup[0]) for tup in pgPlan)
		if toks]
	return _makePlannerNode(phrases)
