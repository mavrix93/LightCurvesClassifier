"""
Parsing, annotating, and morphing queries in the Astronomical Data
Query Language.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.

# Not checked by pyflakes: API file with gratuitous imports

from gavo.adql.annotations import annotate

from gavo.adql.common import *

from gavo.adql.tree import (
	getTreeBuildingGrammar, registerNode)

from gavo.adql.nodes import (flatten, registerRegionMaker)

from gavo.adql.grammar import (
	getADQLGrammar as getRawGrammar, 
	allReservedWords,
	ParseException, ParseSyntaxException)

from gavo.adql.morphpg import (
	morphPG)

from gavo.adql.fieldinfo import getSubsumingType, FieldInfo

from gavo.adql.ufunctions import userFunction

from gavo.adql.postproc import builtinMorph


def getSymbols():
	return getTreeBuildingGrammar()[0]

def getGrammar():
	return getTreeBuildingGrammar()[1]

def parseToTree(adqlStatement):
	"""returns a "naked" parse tree for adqlStatement.

	It contains no annotations, so you'll usually not want to use this.
	"""
	return utils.pyparseString(getGrammar(), adqlStatement)[0]

def parseAnnotating(adqlStatement, fieldInfoGetter):
	"""returns a tuple of context, parsedTree for parsing and annotating
	adqlStatement.

	The builtin morphs are performed on the tree.
	"""
	parsedTree = parseToTree(adqlStatement)
	ctx = annotate(parsedTree, fieldInfoGetter)
	return ctx, builtinMorph(parsedTree)[1]
