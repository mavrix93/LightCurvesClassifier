"""
Functions for adding defaults to STC-S concrete syntax trees.

Default addition is governed by the two dicts at the bottom of
the module:

	- pathFunctions -- maps path tuples to handling functions.  If there
		is a match here, no name-based defaulting is done
	- nodeNameFunctions -- maps the last element of a path tuple to
		handling functions.
"""

#c Copyright 2008-2016, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


def getSpaceFlavor(node):
	if node["type"]=="Convex":
		return "UNITSPHER"
	else:
		return "SPHER2"


def getSpaceUnit(node):
	if node["frame"] and node["frame"].startswith("GEO"):
		return "deg deg m"
	elif node["flavor"].startswith("CART"):
		return "m"
	elif node["flavor"]=="UNITSPHER":
		return ""
	else:
		return "deg"


def getEquinox(node):
	if node["frame"]=="FK4":
		return "B1950.0"
	elif node["frame"]=="FK5":
		return "J2000.0"
	else:
		return None


def getRedshiftUnit(node):
	if node["redshiftType"]=="VELOCITY":
		return "km/s"
	else:
		return "nil"


def _addDefaultsToNode(node, defaults):
	"""adds defaults to node.

	defaults is a sequence of (key, default) pairs, where default is either
	a string (which gets added in a list node), a list (which gets added
	directly) or a function(node) -> string or list to obtain the default.

	Values are only added to a node if the correponding key is not yet
	present.
	"""
	for key, value in defaults:
		if key not in node:
			if not isinstance(value, (basestring, list)):
				value = value(node)
				if value is None:
					continue
			node[key] = value


def _removeDefaultsFromNode(node, defaults):
	"""removes defaults from node.

	See _addDefaultsToNode for details.
	"""
	defaultedKeys = []
	for key, value in node.iteritems():
		if key in defaults:
			default = defaults[key]
			if not isinstance(default, (basestring, list)):
				default = default(node)
			if value==default:
				defaultedKeys.append(key)
	for key in defaultedKeys:
		del node[key]


def _makeDefaulter(defaults):
	"""returns a defaulting function filling in what is defined in
	defaults.
	"""
	def func(node):
		return _addDefaultsToNode(node, defaults)
	return func


def _makeUndefaulter(defaults):
	"""returns a function removing values in nodes that have their default
	values.
	"""
	def func(node):
		return _removeDefaultsFromNode(node, dict(defaults))
	return func


defaults = {
	"space": [
		("flavor", getSpaceFlavor),
		("equinox", getEquinox),
		("unit", getSpaceUnit)],
	"time": [
		("unit", "s")],
	"spectral": [
		("unit", "Hz")],
	"redshift": [
		("redshiftType", "REDSHIFT"),
		("unit", getRedshiftUnit),
		("dopplerdef", "OPTICAL")],
	"velocity": [
		("unit", "m/s"),],
}

defaultingFunctions = dict(
	(k, _makeDefaulter(v)) for k, v in defaults.iteritems())

undefaultingFunctions = dict(
	(k, _makeUndefaulter(v)) for k, v in defaults.iteritems())
