"""
Adding field infos to columns and other objects in an ADQL parse tree.

When we want to generate VOTables from ADQL queries, we must know types,
units, ucds, and the like, and we need to know STC information for
all columns in a query.

To do that, we traverse the parse tree postorder looking for nodes that have
an addFieldInfos method (note the plural).  These then get called,
which causes one of the classes in adql.fieldinfos to be constructed
and assigned to the node's fieldInfos attribute.  The source for
these infos is either an AnnotationContext (and thus typically
the user-supplied retrieveFieldInfos function) or derived annotations.
These are computed by the nodes themselves, using their addFieldInfo 
(singular!) method.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import contextlib

from gavo import utils
from gavo import stc



class AnnotationContext(object):
	"""An context object for the annotation process.

	It is constructed with a field info retriever function (see below)
	and an equivalence policy for STC objects.

	It has errors and warnings attributes consisting of user-exposable
	error strings accrued during the annotation process.

	The annotation context also manages the namespaces for column reference
	resolution.  It maintains a stack of getters; is is maintained
	using the customResolver context manager.

	Finally, the annotation context provides a ancestors attribute that,
	at any time, gives a list of the current node's ancestor nodes.
	"""
	def __init__(self, retrieveFieldInfos, equivalencePolicy=stc.defaultPolicy):
		self.retrieveFieldInfos = retrieveFieldInfos
		self.policy = equivalencePolicy
		self.colResolvers = []
		self.errors, self.warnings = [], []
		self.ancestors = []

	@contextlib.contextmanager
	def customResolver(self, getter):
		"""a context manager temporarily installing a difference field info
		getter.
		"""
		self.colResolvers.append(getter)
		try:
			yield
		finally:
			self.colResolvers.pop()

	def getFieldInfo(self, colName, tableName):
		"""returns the value of the current field info getter for tableName.

		This should be a sequence of (colName, common.FieldInfo) pairs.
		"""
		res = self.colResolvers[-1](colName, tableName)
		if res is None:
			raise utils.ReportableError("Internal Error: resolver returned NULL for"
				" %s.%s.  Please report this to the gavo@ari.uni-heidelberg.de"
				" together with the failed query."%(tableName, colName))
		return res


def _annotateTraverse(node, context):
	"""does the real tree traversal for annotate.
	"""
	context.ancestors.append(node)
	for c in node.iterNodeChildren():
		_annotateTraverse(c, context)
	context.ancestors.pop()
	if hasattr(node, "addFieldInfos"):
		node.addFieldInfos(context)


def annotate(node, context):
	"""adds annotations to all nodes wanting some.

	This is done by a postorder traversal of the tree, identifying all
	annotable objects.

	context should be an AnnotationContext instance.  You can also just
	pass in a field info getter.  In that case, annotation runs with the
	default stc equivalence policy.

	The function returns the context used in any case.
	"""
	if not isinstance(context, AnnotationContext):
		context = AnnotationContext(context)
	_annotateTraverse(node, context)
	return context


def dumpFieldInfoedTree(tree):
	"""dumps an ADQL parse tree, giving the computed annotations.

	For debugging.
	"""
	import pprint
	def traverse(node):
		res = []
		if hasattr(node, "fieldInfo"):
			res.append("%s <- %s"%(node.type, repr(node.fieldInfo)))
		if hasattr(node, "fieldInfos"):
			res.append("%s -- %s"%(node.type, repr(node.fieldInfos)))
		res.extend(filter(None, [traverse(child) for child in 
			node.iterNodeChildren()]))
		if len(res)==1:
			return res[0]
		else:
			return res
	pprint.pprint(traverse(tree))
