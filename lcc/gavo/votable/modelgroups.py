"""
Data model related code.

This is intended for STC groups and possibly similarly handled data models.

Basically, these come in groups with certain utypes; these in turn contain
FIELDRefs and INFOs specifying utype-value pairs.

The idea here is to have [un]marshal_DMNAME functions in here that expect
some defined top-level element.  In the case of STC, that top-level
element is the table, but other elements are conceivable.

To keep the library working even without the STC package, the stc import is
protected by a try...except clause.  You can check the availability of
STC by inspecting modelgroups.stcAvailable.
"""

#c Copyright 2008-2016, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from gavo.votable.model import VOTable as V


try:
	from gavo import stc
	stcAvailable = True
except ImportError:
	stcAvailable = False


######################## Helpers

def _getUtypedGroupsFromAny(votObj, utype):
	return [g 
		for g in votObj.iterChildrenOfType(V.GROUP) 
		if g.utype and g.utype.startswith(utype)]


def _getUtypedGroupsFromResource(votRes, utype):
	"""yields groups of utype from below the V.RESOURCE votRes.

	The function recursively searches child TABLE and RESOURCE
	instances.
	"""
	stcGroups = []
	stcGroups.extend(_getUtypedGroupsFromAny(votRes, utype))
	for child in votRes.iterChildren():
		if isinstance(child, V.TABLE):
			stcGroups.extend(_getUtypedGroupsFromAny(child, utype))
		elif isinstance(child, V.RESOURCE):
			stcGroups.extend(_getUtypedGroupsFromResource(child, utype))
	return stcGroups


def _getUtypedGroupsFromVOTable(vot, utype):
	"""returns a list of all groups of utype from a votable.

	Make this available in the votable library?
	"""
	allGroups = []
	for res in vot.iterChildrenOfType(V.RESOURCE):
		allGroups.extend(_getUtypedGroupsFromResource(res, utype))
	return allGroups


def _extractUtypes(group, refClass):
	"""yields utype-value pairs extracted from the children of group.

	refClass is the class to be used for column references.  This will
	usually be a stanxml.Stub derived class.
	"""
	for child in group.iterChildren():
		if isinstance(child, V.PARAM):
			yield child.utype, child.value
		elif isinstance(child, V.FIELDref):
			yield child.utype, refClass(child.ref)
		else:
			pass # other children are ignored.



########################## STC

def unmarshal_STC(tableNode):
	"""iterates over pairs of (colInfo, system) pairs of STC information
	on tableNode.

	system are STC ASTs; colInfo maps column ids to the column utype in
	system.
	"""
	for obsLocGroup in _getUtypedGroupsFromAny(tableNode, 
			"stc:CatalogEntryLocation"):
		utypes, colInfo = [], {}
		for utype, value in _extractUtypes(obsLocGroup, stc.ColRef):
			if isinstance(value, stc.ColRef):
				colInfo[value.dest] = utype
			utypes.append((utype, value))
		yield colInfo, stc.parseFromUtypes(utypes)


def _makeUtypeContainer(utype, value, getIdFor):
	"""returns a PARAM or FIELDref element serializing the utype, value pair.

	If the value is a ColRef, the result will be a FIELDref.

	see marshal_STC for info on getIdFor
	"""
	if isinstance(value, stc.ColRef):
		destId = getIdFor(value)
		if value.toParam:
			return V.PARAMref(utype=utype, ref=destId)
		else:
			return V.FIELDref(utype=utype, ref=destId)
	else:
		return V.PARAM(name=utype.split(".")[-1], utype=utype, value=value,
			datatype="char", arraysize="*")


def marshal_STC(ast, getIdFor):
	"""returns an stc:CatalogEntryLocation group for ast.

	ast is an AST object from GAVO's STC library.

	getIdFor must be a function returning the id for an stc.ColRef object.
	The main issue here is that the STC library deals with unqualified column 
	names.  These may clash when several tables are combined within a VOTable.
	Thus, you will have to have some mechanism to generate unique ids for
	the FIELDs (e.g. using utils.IdManagerMixin).  getIdFor must resolve
	ColRefs (with column names in their dest) to unique ids.
	"""
	container = V.GROUP(utype="stc:CatalogEntryLocation")
	for utype, value in stc.getUtypes(ast, includeDMURI=True):
		try:
			container[_makeUtypeContainer(utype, value, getIdFor)]
		except KeyError:  # column referenced is not in result
			pass
	return container
