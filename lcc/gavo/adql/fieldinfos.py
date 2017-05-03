"""
FieldInfos are collections of inferred metadata on the columns present
within ADQL relations.

In generation, this module distinguishes between query-like (select...)
and table-like (from table references) field infos.  The functions
here are called from the addFieldInfo methods of the respective
nodes classes.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


# XXX TODO: This is a horrible mess.  Carefully read the SQL specification,
# figure out the actual rules for name resolution and then write an
# actual namespace management in annotations.py

from __future__ import with_statement

from gavo.adql import common


class FieldInfos(object):
	"""
	A base class for field annotations.

	Subclasses of those are attached to physical tables, joins, and
	subqueries.

	The information on columns is kept in two places:
	
		- seq -- a sequence of attributes of the columns in the
			order in which they are selected
		- columns -- maps column names to attributes or None if a column
			name is not unique.  Column names are normalized by lowercasing here
			(which, however, does not affect L{utils.QuotedName}s).

	A FieldInfos object is instanciated with the object it will annotate,
	and the annotation (i.e., setting of the fieldInfos attribute on
	the parent) will happen during instanciation.
	"""
	def __init__(self, parent, context):
		self.seq, self.columns = [], {}
		parent.fieldInfos = self
		self._collectSubTables(parent, context)

	def __repr__(self):
		return "<Column information %s>"%(repr(self.seq))

	def _namesMatch(self, table, toName):
		"""returns true when table could be referred to by toName.

		This means that either the name matches or toName is table's original
		name.

		toName is a qualified name (i.e., including schema).
		"""
		if not hasattr(table, "tableName"): # the root query specifiation
			return toName==""

		return (table.tableName.qName==toName.qName
			or (
				table.originalTable
				and
					table.originalTable==toName.qName))

	def locateTable(self, refName):
		"""returns a table instance matching the node.TableName refName.

		If no such table is in scope, the function raises a TableNotFound.
		"""
		for t in self.subTables:
			if self._namesMatch(t, refName):
				return t
		raise common.TableNotFound(refName.qName)

	def addColumn(self, label, info):
		"""adds a new visible column to this info.

		This entails both entering it in self.columns and in self.seq.
		"""
		label = label.lower()
		if label in self.columns:
			if self.columns[label]!=info:
				self.columns[label] = None # Sentinel for ambiguous names
		else:
			self.columns[label] = info
		self.seq.append((label, info))

	def getFieldInfo(self, colName, refName=None):
		"""returns a FieldInfo object for colName.

		Unknown columns result in a ColumnNotFound exception.

		refName is ignored here; we may check that it's identical with
		parent's name later.
		"""
		colName = colName.lower()
		fi = self.columns.get(colName, common.Absent)
		if fi is common.Absent:
			raise common.ColumnNotFound(colName)
		if fi is None:
			# This can happen on joined tables
			if refName is not None:
				return self.locateTable(refName).getFieldInfo(colName)
			raise common.AmbiguousColumn(colName)
		return fi


class TableFieldInfos(FieldInfos):
	"""FieldInfos coming from something that's basically a table in the DB.

	This includes joins.

	To instanciate those, use the makeForNode class method below.
	"""

	@classmethod
	def makeForNode(cls, tableNode, context):
		"""returns a TableFieldInfos instance for an ADQL tableNode.

		context is an AnnotationContext.

		Whatever tableNode actually is, it The needs an originalTable
		attribute which is used to retrieve the column info.
		"""
		result = cls(tableNode, context)
		
		# add infos for the table itself.
		if tableNode.originalTable:
			for colName, fieldInfo in context.retrieveFieldInfos(
					tableNode.originalTable):
				result.addColumn(colName, fieldInfo)
		
		# add infos for joined tables as necessary; since we to a postorder
		# traversal, those have already been annotated.
		commonColumns = cls._computeCommonColumns(tableNode)
		emittedCommonColumns = set()
		for jt in getattr(tableNode, "joinedTables", ()):
				for label, info in jt.fieldInfos.seq:
					if label in commonColumns:
						if label not in emittedCommonColumns:
							result.addColumn(label, info)
							emittedCommonColumns.add(label)
					else:
						result.addColumn(label, info)

		# annotate any join specs present
		with context.customResolver(result.getFieldInfo):
			_annotateNodeRecurse(tableNode, context)
		return result

	def _collectSubTables(self, node, context):
		self.subTables = list(node.getAllTables())

	@staticmethod
	def _computeCommonColumns(tableNode):
		"""returns a set of column names that only occur once in the result
		table.

		For a natural join, that's all column names occurring in all tables,
		for a USING join, that's all names occurring in USING, else it's 
		an empty set.

		This is a helper for makeFieldInfosForTable.
		"""
		joinType = getattr(tableNode, "getJoinType", lambda: "CROSS")()
		if joinType=="NATURAL":
			# NATURAL JOIN, collect common names
			return reduce(lambda a,b: a&b, 
				[set(t.fieldInfos.columns) for t in tableNode.joinedTables])
		elif joinType=="USING":
			return set(tableNode.joinSpecification.usingColumns)
		else: # CROSS join, comma, etc.
			return set()


def _annotateNodeRecurse(node, context):
	"""helps QueryFieldInfos.
	"""
	for c in node.iterNodeChildren():
		_annotateNodeRecurse(c, context)
	if hasattr(node, "addFieldInfo") and node.fieldInfo is None:
		node.addFieldInfo(context)


class QueryFieldInfos(FieldInfos):
	"""FieldInfos inferred from a FROM clause.

	To instanciate those, use the makeForNode class method below.
	"""

	# enclosingQuery is set non-None when a whereClause is found in the
	# ancestors in _collectSubTables.  It then refers to the query spec
	# the where clause is a child from.  All names from that qs are
	# also immediately accessible from the current qs.
	enclosingQuery = None


	@classmethod
	def makeForNode(cls, queryNode, context):
		"""cf. TableFieldInfos.makeForNode.
		"""
		result = cls(queryNode, context)

		# annotate the children of the select clause, using info
		# from queryNode's queried tables; we must manipulate the context's 
		# name resolution.
		with context.customResolver(result.getFieldInfoFromSources):
			for selField in queryNode.getSelectFields():
				_annotateNodeRecurse(selField, context)

		# annotate the children of the where clause, too -- their types
		# and such may be needed by morphers
		with context.customResolver(result.getFieldInfo):
			if queryNode.whereClause:
				_annotateNodeRecurse(queryNode.whereClause, context)
			if queryNode.having:
				_annotateNodeRecurse(queryNode.having, context)
			if queryNode.groupby:
				_annotateNodeRecurse(queryNode.groupby, context)

		for col in queryNode.getSelectFields():
			result.addColumn(col.name, col.fieldInfo)
		return result

	def _getEnclosingQuery(self, context):
		"""returns the enclosing query specification if this is a subquery within
		a where clause.
		"""
		ancs = context.ancestors
		index = len(ancs)-1
		while index>=0:
			if ancs[index].type=="whereClause":
				return ancs[index-1]
			index -= 1

	def _collectSubTables(self, queryNode, context):
		self.subTables = list(
			queryNode.fromClause.tableReference.getAllTables())
		self.tableReference = queryNode.fromClause.tableReference

		# if we are in a from clause, add its querySpecification, too
		# (for things like exists(select * from x where a=q.b))
		encQS = self._getEnclosingQuery(context)
		if encQS:
			self.subTables.append(encQS)
			self.subTables.extend(
				encQS.fromClause.tableReference.getAllTables())
			self.enclosingQuery = encQS

	def getFieldInfoFromSources(self, colName, refName=None):
		"""returns a field info for colName from anything in the from clause.

		That is, the columns in the select clause are ignored.  Use this to
		resolve expressions from the queries' select clause.

		See getFieldInfo for reName
		"""
		colName = colName.lower()
		matched = []
		if refName is None:
			# no explicit table reference, in immediate table
			subCols = self.tableReference.fieldInfos.columns
			if colName in subCols and subCols[colName]:
				matched.append(subCols[colName])
			if self.enclosingQuery:
				subCols = (self.enclosingQuery.fromClause.
					tableReference.fieldInfos.columns)
				if colName in subCols and subCols[colName]:
					matched.append(subCols[colName])

		else:
			# locate an appropriate table
			subCols = self.locateTable(refName).fieldInfos.columns
			if colName in subCols and subCols[colName]:
				matched.append(subCols[colName])

		# XXX TODO: build a qualified colName here if necessary
		return common.getUniqueMatch(matched, colName)

	def getFieldInfo(self, colName, refName=None):
		"""returns a field info for colName in self or any tables this
		query takes columns from.

		To do that, it collects all fields of colName in self and subTables and
		returns the matching field if there's exactly one.  Otherwise, it
		will raise ColumnNotFound or AmbiguousColumn.

		If the node.TableName instance refName is given, the search will be 
		restricted to the matching tables.
		"""
		ownMatch = None
		if refName is None:
			ownMatch = self.columns.get(colName, None)
		if ownMatch:
			return ownMatch
		else:
			return self.getFieldInfoFromSources(colName, refName)
