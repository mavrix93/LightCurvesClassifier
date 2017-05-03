"""
Operations on annotated ADQL trees done by parseAnnotated.

These can be considered "bug fixes" for ADQL, where we try to
make the parse tree more suitable for later translation into
SQL.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from gavo.adql import morphhelpers
from gavo.adql import nodes


############## INTERSECTS to CONTAINS
# Unfortunately, the ADQL spec mandates that any INTERSECTS with a
# POINT argument should be treated as if it were CONTAINs with
# arguments swapped as required.  This morphing code tries to do 
# this before translation.  One major reason to do this within
# the translation layer rather than relying on the SQL code
# generation is that probably all generators profit from knowing
# that there's a special case "point within <geometry>".

def _intersectsWithPointToContains(node, state):
	if node.funName!='INTERSECTS':
		return node
	ltype = getattr(node.args[0].fieldInfo, "type", None)
	rtype = getattr(node.args[1].fieldInfo, "type", None)
	if ltype=='spoint':
		return nodes.PredicateGeometryFunction(funName="CONTAINS",
			args=node.args)
	elif rtype=='spoint':
		return nodes.PredicateGeometryFunction(funName="CONTAINS",
			args=[node.args[1], node.args[0]])
	return node
	

_builtinMorphs = {
	'predicateGeometryFunction': _intersectsWithPointToContains,
}

_morpher = morphhelpers.Morpher(_builtinMorphs)

builtinMorph = _morpher.morph

