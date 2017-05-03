"""
Node classes and factories used in ADQL tree processing.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import re
import weakref

from gavo import stc
from gavo import utils
from gavo.adql import common
from gavo.adql import fieldinfo
from gavo.adql import fieldinfos
from gavo.imp import pyparsing
from gavo.stc import tapstc


################ Various helpers

def symbolAction(*symbols):
	"""is a decorator to mark functions as being a parseAction for symbol.

	This is evaluated by getADQLGrammar below.  Be careful not to alter
	global state in such a handler.
	"""
	def deco(func):
		for symbol in symbols:
			if hasattr(func, "parseActionFor"):
				func.parseActionFor.append(symbol)
			else:
				func.parseActionFor = [symbol]
		func.fromParseResult = func
		return func
	return deco


def getType(arg):
	"""returns the type of an ADQL node or the value of str if arg is a string.
	"""
	if isinstance(arg, basestring):
		return str
	else:
		return arg.type


def flatten(arg):
	"""returns the SQL serialized representation of arg.
	"""
	if isinstance(arg, basestring):
		return arg
	elif isinstance(arg, pyparsing.ParseResults):
		return " ".join(flatten(c) for c in arg)
	else:
		return arg.flatten()


def autocollapse(nodeBuilder, children):
	"""inhibts the construction via nodeBuilder if children consists of
	a single ADQLNode.

	This function will automatically be inserted into the the constructor
	chain if the node defines an attribute collapsible=True.
	"""
	if len(children)==1 and isinstance(children[0], ADQLNode):
		return children[0]
	return nodeBuilder.fromParseResult(children)


def collectUserData(infoChildren):
	userData, tainted = (), False
	for c in infoChildren:
		userData = userData+c.fieldInfo.userData
		tainted = tainted or c.fieldInfo.tainted
	return userData, tainted


def flattenKWs(obj, *fmtTuples):
	"""returns a string built from the obj according to format tuples.

	A format tuple is consists of a literal string, and
	an attribute name.  If the corresponding attribute is
	non-None, the plain string and the flattened attribute
	value are inserted into the result string, otherwise
	both are ignored.

	Nonexisting attributes are taken to have None values.

	To allow unconditional literals, the attribute name can
	be None.  The corresponding literal is always inserted.

	All contributions are separated by single blanks.

	This is a helper method for flatten methods of parsed-out
	elements.
	"""
	res = []
	for literal, attName in fmtTuples:
		if attName is None:
			res.append(literal)
		else:
			if getattr(obj, attName, None) is not None:
				if literal:
					res.append(literal)
				res.append(flatten(getattr(obj, attName)))
	return " ".join(res)


def cleanNamespace(ns):
	"""removes all names starting with an underscore from the dict ns.

	This is intended for _getInitKWs methods.  ns is changed in place *and*
	returned for convenience
	"""
	return dict((k,v) for k,v in ns.iteritems() if not k.startswith("_")
		and k!="cls")


def getChildrenOfType(nodeSeq, type):
	"""returns a list of children of type typ in the sequence nodeSeq.
	"""
	return [c for c in nodeSeq if getType(c)==type]


def getChildrenOfClass(nodeSeq, cls):
	return [c for c in nodeSeq if isinstance(c, cls)]


class BOMB_OUT(object): pass

def _uniquify(matches, default, exArgs):
# helper method for getChildOfX -- see there
	if len(matches)==0:
		if default is not BOMB_OUT: 
			return default
		raise common.NoChild(*exArgs)
	if len(matches)!=1:
		raise common.MoreThanOneChild(*exArgs)
	return matches[0]


def getChildOfType(nodeSeq, type, default=BOMB_OUT):
	"""returns the unique node of type in nodeSeq.

	If there is no such node in nodeSeq or more than one, a NoChild or
	MoreThanOneChild exception is raised,  Instead of raising NoChild,
	default is returned if given.
	"""
	return _uniquify(getChildrenOfType(nodeSeq, type),
		default, (type, nodeSeq))


def getChildOfClass(nodeSeq, cls, default=BOMB_OUT):
	"""returns the unique node of class in nodeSeq.

	See getChildOfType.
	"""
	return _uniquify(getChildrenOfClass(nodeSeq, cls),
		default, (cls, nodeSeq))


def parseArgs(parseResult):
	"""returns a sequence of ADQL nodes suitable as function arguments from 
	parseResult.

	This is for cleaning up _parseResults["args"], i.e. stuff from the
	Args symbol decorator in grammar.
	"""
	args = []
	for _arg in parseResult:
		# _arg is either another ParseResult, an ADQL identifier, or an ADQLNode
		if isinstance(_arg, (ADQLNode, basestring, utils.QuotedName)):
			args.append(_arg)
		else:
			args.append(autocollapse(NumericValueExpression, _arg))
	return tuple(args)


######################### Generic Node definitions


class ADQLNode(utils.AutoNode):
	"""
	A node within an ADQL parse tree.

	ADQL nodes may be parsed out; in that case, they have individual attributes
	and are craftily flattened in special methods.  We do this for nodes
	that are morphed.

	Other nodes basically just have a children attribute, and their flattening
	is just a concatenation for their flattened children.  This is convenient
	as long as they are not morphed.
	
	To derive actual classes, define 
	
		- the _a_<name> class attributes you need,
		- the type (a nonterminal from the ADQL grammar) 
		- plus bindings if the class handles more than one symbol,
		- a class method _getInitKWs(cls, parseResult); see below.
		- a method flatten() -> string if you define a parsed ADQLNode.
		- a method _polish() that is called just before the constructor is
			done and can be used to create more attributes.  There is no need
			to call _polish of superclasses.

	The _getInitKWs methods must return a dictionary mapping constructor argument
	names to values.  You do not need to manually call superclass _getInitKWs,
	since the fromParseResult classmethod figures out all _getInitKWs in the
	inheritance tree itself.  It calls all of them in the normal MRO and updates
	the argument dictionary in reverse order.  
	
	The fromParseResult class method additionally filters out all names starting
	with an underscore; this is to allow easy returning of locals().
	"""
	type = None
# XXX Do we want this messy _getInitKWs business?  Or should we have
# classic super()-type stuff?

	@classmethod
	def fromParseResult(cls, parseResult):
		initArgs = {}
		for superclass in reversed(cls.mro()):
			if hasattr(superclass, "_getInitKWs"):
				initArgs.update(superclass._getInitKWs(parseResult))
		try:
			return cls(**cleanNamespace(initArgs))
		except TypeError:
			raise common.BadKeywords("%s, %s"%(cls, cleanNamespace(initArgs)))

	def _setupNode(self):
		for cls in reversed(self.__class__.mro()):
			if hasattr(cls, "_polish"):
				cls._polish(self)
		self._setupNodeNext(ADQLNode)

	def __repr__(self):
		return "<ADQL Node %s>"%(self.type)

	def flatten(self):
		"""returns a string representation of the text content of the tree.

		This default implementation will only work if you returned all parsed
		elements as children.  This, in turn, is something you only want to
		do if you are sure that the node is question will not be morphed.

		Otherwise, override it to create an SQL fragment out of the parsed
		attributes.
		"""
		return " ".join(flatten(c) for c in self.children)

	def getFlattenedChildren(self):
		"""returns a list of all preterminal children of all children of self.

		A child is preterminal if it has string content.
		"""
		fl = [c for c in self.children if isinstance(c, basestring)]
		def recurse(node):
			for c in node.children:
				if isinstance(c, ADQLNode):
					if c.isPreterminal():
						fl.append(c)
					recurse(c)
		recurse(self)
		return fl

	def asTree(self):
		res = []
		for name, val in self.iterChildren():
			if isinstance(val, ADQLNode):
				res.append(val.asTree())
		return self._treeRepr()+tuple(res)
	
	def _treeRepr(self):
		return (self.type,)
	
	def iterTree(self):
		for name, val in self.iterChildren():
			if isinstance(val, ADQLNode):
				for item in val.iterTree():
					yield item
			yield name, val
			

class TransparentMixin(object):
	"""a mixin just pulling through the children and serializing them.
	"""
	_a_children = ()

	@classmethod
	def _getInitKWs(cls, _parseResult):
		return {"children": list(_parseResult)}


class FieldInfoedNode(ADQLNode):
	"""An ADQL node that carries a FieldInfo.

	This is true for basically everything in the tree below a derived
	column.  This class is the basis for column annotation.

	You'll usually have to override addFieldInfo.  The default implementation
	just looks in its immediate children for anything having a fieldInfo,
	and if there's exactly one such child, it adopts that fieldInfo as
	its own, not changing anything.

	FieldInfoedNode, when change()d, keep their field info.  This is usually
	what you want when morphing, but sometimes you might need adjustments.
	"""
	fieldInfo = None

	def _getInfoChildren(self):
		return [c for c in self.iterNodeChildren() if hasattr(c, "fieldInfo")]

	def addFieldInfo(self, context):
		infoChildren = self._getInfoChildren()
		if len(infoChildren)==1:
			self.fieldInfo = infoChildren[0].fieldInfo
		else:
			if len(infoChildren):
				msg = "More than one"
			else:
				msg = "No"
			raise common.Error("%s child with fieldInfo with"
				" no behaviour defined in %s, children %s"%(
					msg,
					self.__class__.__name__,
					list(self.iterChildren())))

	def change(self, **kwargs):
		other = ADQLNode.change(self, **kwargs)
		other.fieldInfo = self.fieldInfo
		return other


class FunctionNode(FieldInfoedNode):
	"""An ADQLNodes having a function name and arguments.

	The rules having this as action must use the Arg "decorator" in
	grammar.py around their arguments and must have a string-valued
	result "fName".

	FunctionNodes have attributes args (unflattened arguments),
	and funName (a string containing the function name, all upper
	case).
	"""
	_a_args = ()
	_a_funName = None

	@classmethod
	def _getInitKWs(cls, _parseResult):
		try:
			args = parseArgs(_parseResult["args"]) #noflake: locals returned
		except KeyError: # Zero-Arg function
			pass
		funName = _parseResult["fName"].upper() #noflake: locals returned
		return locals()

	def flatten(self):
		return "%s(%s)"%(self.funName, ", ".join(flatten(a) for a in self.args))



class ColumnBearingNode(ADQLNode):
	"""A Node types defining selectable columns.

	These are tables, subqueries, etc.  This class is the basis for the
	annotation of tables and subqueries.

	Their getFieldInfo(name)->fi method gives annotation.FieldInfos 
	objects for their columns, None for unknown columns.

	These keep their fieldInfos on a change()
	"""
	fieldInfos = None
	originalTable = None

	def getFieldInfo(self, name):
		if self.fieldInfos:
			return self.fieldInfos.getFieldInfo(name)
	
	def getAllNames(self):
		"""yields all relation names mentioned in this node.
		"""
		raise TypeError("Override getAllNames for ColumnBearingNodes.")

	def change(self, **kwargs):
		other = ADQLNode.change(self, **kwargs)
		other.fieldInfos = self.fieldInfos
		return other


############# Toplevel query language node types (for query analysis)

class TableName(ADQLNode):
	type = "tableName"
	_a_cat = None
	_a_schema = None
	_a_name = None

	def __eq__(self, other):
		if hasattr(other, "qName"):
			return self.qName.lower()==other.qName.lower()
		try:
			return self.qName.lower()==other.lower()
		except AttributeError:
			# other has no lower, so it's neither a string nor a table name;
			# thus, fall through to non-equal case
			pass
		return False

	def __ne__(self, other):
		return not self==other

	def __nonzero__(self):
		return bool(self.name)

	def __str__(self):
		return "TableName(%s)"%self.qName

	def _polish(self):
		# Implementation detail: We map tap_upload to temporary tables
		# here; therefore, we can just nil out anything called tap_upload.
		# If we need more flexibility, this probably is the place to implement
		# the mapping.
		if self.schema and self.schema.lower()=="tap_upload":
			self.schema = None

		self.qName = ".".join(flatten(n) 
			for n in (self.cat, self.schema, self.name) if n) 

	@classmethod
	def _getInitKWs(cls, _parseResult):
		_parts = _parseResult[::2]
		cat, schema, name = [None]*(3-len(_parts))+_parts
		return locals()

	def flatten(self):
		return self.qName

	def lower(self):
		"""returns self's qualified name in lower case.
		"""
		return self.qName.lower()


class PlainTableRef(ColumnBearingNode):
	"""A reference to a simple table.
	
	The tableName is the name this table can be referenced as from within
	SQL, originalName is the name within the database; they are equal unless
	a correlationSpecification has been given.
	"""
	type = "possiblyAliasedTable"
	_a_tableName = None      # a TableName instance
	_a_originalTable = None  # a TableName instance

	@classmethod
	def _getInitKWs(cls, _parseResult):
		if _parseResult.get("alias"):
			tableName = TableName(name=_parseResult.get("alias"))
			originalTable = _parseResult.get("tableName")
		else:
			tableName = getChildOfType(_parseResult, "tableName")
			originalTable = tableName  #noflake: locals returned
		return locals()

	def addFieldInfos(self, context):
		self.fieldInfos = fieldinfos.TableFieldInfos.makeForNode(self, context)

	def _polish(self):
		self.qName = flatten(self.tableName)

	def flatten(self):
		ot = flatten(self.originalTable)
		if ot!=self.qName:
			return "%s AS %s"%(ot, flatten(self.tableName))
		else:
			return self.qName

	def getAllNames(self):
		yield self.tableName.qName

	def getAllTables(self):
		yield self

	def makeUpId(self):
		# for suggestAName
		n = self.tableName.name
		if isinstance(n, utils.QuotedName):
			return "_"+re.sub("[^A-Za-z0-9_]", "", n.name)
		else:
			return n


class DerivedTable(ColumnBearingNode):
	type = "derivedTable"
	_a_query = None
	_a_tableName = None

	def getFieldInfo(self, name):
		return self.query.getFieldInfo(name)
	
	def _get_fieldInfos(self):
		return self.query.fieldInfos
	def _set_fieldInfos(self, val):
		self.query.fieldInfos = val
	fieldInfos = property(_get_fieldInfos, _set_fieldInfos)

	@classmethod
	def _getInitKWs(cls, _parseResult):
		return {'tableName': TableName(name=str(_parseResult.get("alias"))),
			'query': getChildOfClass(_parseResult, QuerySpecification),
		}

	def flatten(self):
		return "(%s) AS %s"%(flatten(self.query), flatten(self.tableName))

	def getAllNames(self):
		yield self.tableName.qName

	def getAllTables(self):
		yield self

	def makeUpId(self):
		# for suggestAName
		n = self.tableName.name
		if isinstance(n, utils.QuotedName):
			return "_"+re.sub("[^A-Za-z0-9_]", "", n.name)
		else:
			return n


class JoinSpecification(ADQLNode, TransparentMixin):
	"""A join specification ("ON" or "USING").
	"""
	type = "joinSpecification"
	
	_a_children = ()
	_a_predicate = None
	_a_usingColumns = ()

	@classmethod
	def _getInitKWs(cls, _parseResult):
		predicate = _parseResult[0].upper()
		if predicate=="USING":
			usingColumns = [ #noflake: locals returned
				n for n in _parseResult["columnNames"] if n!=',']
			del n
		children = list(_parseResult) #noflake: locals returned
		return locals()


class JoinOperator(ADQLNode, TransparentMixin):
	"""the complete join operator (including all LEFT, RIGHT, ",", and whatever).
	"""
	type = "joinOperator"

	def isCrossJoin(self):
		return self.children[0] in (',', 'CROSS')


class JoinedTable(ColumnBearingNode):
	"""A joined table.

	These aren't made directly by the parser since parsing a join into
	a binary structure is very hard using pyparsing.  Instead, there's
	the helper function makeJoinedTableTree handling the joinedTable
	symbol that manually creates a binary tree.
	"""
	type = None
	originalTable = None
	tableName = TableName()
	qName = None

	_a_leftOperand = None
	_a_operator = None
	_a_rightOperand = None
	_a_joinSpecification = None

	@classmethod
	def _getInitKWs(cls, _parseResult):
		leftOperand = _parseResult[0] #noflake: locals returned
		operator = _parseResult[1] #noflake: locals returned
		rightOperand = _parseResult[2] #noflake: locals returned
		if len(_parseResult)>3:
			joinSpecification = _parseResult[3] #noflake: locals returned
		return locals()

	def flatten(self):
		js = ""
		if self.joinSpecification is not None:
			js = flatten(self.joinSpecification)
		return "%s %s %s %s"%(
			self.leftOperand.flatten(),
			self.operator.flatten(),
			self.rightOperand.flatten(),
			js)

	def addFieldInfos(self, context):
		self.fieldInfos = fieldinfos.TableFieldInfos.makeForNode(self, context)

	def _polish(self):
		self.joinedTables = [self.leftOperand, self.rightOperand]

	def getAllNames(self):
		"""iterates over all fully qualified table names mentioned in this
		(possibly joined) table reference.
		"""
		for t in self.joinedTables:
			yield t.tableName.qName

	def getTableForName(self, name):
		return self.fieldInfos.locateTable(name)

	def makeUpId(self):
		# for suggestAName
		return "_".join(t.makeUpId() for t in self.joinedTables)

	def getJoinType(self):
		"""returns a keyword indicating how result rows are formed in this
		join.

		This can be NATURAL (all common columns are folded into one),
		USING (check the joinSpecification what columns are folded),
		CROSS (no columns are folded).
		"""
		if self.operator.isCrossJoin():
			if self.joinSpecification is not None:
				raise common.Error("Cannot use cross join with a join predicate.")
			return "CROSS"
		if self.joinSpecification is not None:
			if self.joinSpecification.predicate=="USING":
				return "USING"
			if self.joinSpecification.predicate=="ON":
				return "CROSS"
		return "NATURAL"

	def getAllTables(self):
		"""returns all actual tables and subqueries (not sub-joins) 
		within this join.
		"""
		res = []
		def collect(node):
			if hasattr(node.leftOperand, "leftOperand"):
				collect(node.leftOperand)
			else:
				res.append(node.leftOperand)
			if hasattr(node.rightOperand, "leftOperand"):
				collect(node.rightOperand)
			else:
				res.append(node.rightOperand)
		collect(self)
		return res


class SubJoin(ADQLNode):
	"""A sub join (JoinedTable surrounded by parens).

	The parse result is just the parens and a joinedTable; we need to
	camouflage as that joinedTable.
	"""
	type = "subJoin"
	_a_joinedTable = None

	@classmethod
	def _getInitKWs(cls, _parseResult):
		return {"joinedTable": _parseResult[1]}

	def flatten(self):
		return "("+self.joinedTable.flatten()+")"

	def __getattr__(self, attName):
		return getattr(self.joinedTable, attName)


@symbolAction("joinedTable")
def makeBinaryJoinTree(children):
	"""takes the parse result for a join and generates a binary tree of
	JoinedTable nodes from it.

	It's much easier to do this in a separate step than to force a 
	non-left-recursive grammar to spit out the right parse tree in the
	first place.
	"""
	try:
		children = list(children)
		while len(children)>1:
			if len(children)>3 and isinstance(children[3], JoinSpecification):
				exprLen = 4
			else:
				exprLen = 3
			args = children[:exprLen]
			children[:exprLen] = [JoinedTable.fromParseResult(args)]
	except:
		# remove this, it's just here for debugging
		import traceback
		traceback.print_exc()
		raise
	return children[0]


class TransparentNode(ADQLNode, TransparentMixin):
	"""An abstract base for Nodes that don't parse out anything.
	"""
	type = None


class WhereClause(TransparentNode):
	type = "whereClause"

class Grouping(TransparentNode):
	type = "groupByClause"

class Having(TransparentNode):
	type = "havingClause"

class OrderBy(TransparentNode):
	type = "sortSpecification"


class QuerySpecification(ColumnBearingNode): 
	type = "querySpecification"

	_a_setQuantifier = None
	_a_setLimit = None
	_a_selectList = None
	_a_fromClause = None
	_a_whereClause = None
	_a_groupby = None
	_a_having = None
	_a_orderBy = None

	def _polish(self):
		self.query = weakref.proxy(self)

	@classmethod
	def _getInitKWs(cls, _parseResult):
		res = {}
		for name in ["setQuantifier", "setLimit", "fromClause",
				"whereClause", "groupby", "having", "orderBy"]:
			res[name] = _parseResult.get(name)
		res["selectList"] = getChildOfType(_parseResult, "selectList")
		return res

	def _iterSelectList(self):
		for f in self.selectList.selectFields:
			if isinstance(f, DerivedColumn):
				yield f
			elif isinstance(f, QualifiedStar):
				for sf in self.fromClause.getFieldsForTable(f.sourceTable):
					yield sf
			else:
				raise common.Error("Unexpected %s in select list"%getType(f))

	def getSelectFields(self):
		if self.selectList.allFieldsQuery:
			return self.fromClause.getAllFields()
		else:
			return self._iterSelectList()

	def addFieldInfos(self, context):
		self.fieldInfos = fieldinfos.QueryFieldInfos.makeForNode(self, context)

	def resolveField(self, fieldName):
		return self.fromClause.resolveField(fieldName)

	def getAllNames(self):
		return self.fromClause.getAllNames()

	def flatten(self):
		return flattenKWs(self, ("SELECT", None),
			("", "setQuantifier"),
			("TOP", "setLimit"),
			("", "selectList"),
			("", "fromClause"),
			("", "whereClause"),
			("", "groupby"),
			("", "having"),
			("", "orderBy"),)

	def suggestAName(self):
		"""returns a string that may or may not be a nice name for a table
		resulting from this query.

		Whatever is being returned here, it's a regular SQL identifier.
		"""
		try:
			sources = [tableRef.makeUpId()
				for tableRef in self.fromClause.getAllTables()]
			if sources:
				return "_".join(sources)
			else:
				return "query_result"
		except:  # should not happen, but we don't want to bomb from here
			import traceback;traceback.print_exc()
			return "weird_table_report_this"

	def getContributingNames(self):
		"""returns a set of table names mentioned below this node.
		"""
		names = set()
		for name, val in self.iterTree():
			if isinstance(val, TableName):
				names.add(val.flatten())
		return names


class ColumnReference(FieldInfoedNode):
	type = "columnReference"
	bindings = ["columnReference", "geometryValue"]
	_a_refName = None  # if given, a TableName instance
	_a_name = None

	def _polish(self):
		if not self.refName:
			self.refName = None
		self.colName = ".".join(
			flatten(p) for p in (self.refName, self.name) if p)

	@classmethod
	def _getInitKWs(cls, _parseResult):
		names = [_c for _c in _parseResult if _c!="."]
		names = [None]*(4-len(names))+names
		refName = TableName(cat=names[0], 
			schema=names[1], 
			name=names[2])
		if not refName:
			refName = None
		return {
			"name": names[-1],
			"refName": refName}

	def addFieldInfo(self, context):
		self.fieldInfo = context.getFieldInfo(self.name, self.refName)

	def flatten(self):
		return self.colName

	def _treeRepr(self):
		return (self.type, self.name)


class FromClause(ADQLNode):
	type = "fromClause"
	_a_tableReference = ()

	@classmethod
	def _getInitKWs(cls, _parseResult):
		tableReference = _parseResult[1] #noflake: locals returned
		return locals()
	
	def flatten(self):
		return "FROM %s"%self.tableReference.flatten()
	
	def getAllNames(self):
		"""returns the names of all tables taking part in this from clause.
		"""
		return self.tableReference.getAllNames()
	
	def resolveField(self, name):
		return self.tableReference.getFieldInfo(name)

	def _makeColumnReference(self, sourceTableName, colPair):
		"""returns a ColumnReference object for a name, colInfo pair from a 
		table's fieldInfos.
		"""
		cr = ColumnReference(name=colPair[0], refName=sourceTableName)
		cr.fieldInfo = colPair[1]
		return cr

	def getAllFields(self):
		"""returns all fields from all tables in this FROM.

		On an unannotated tree, this will return the empty list.
		"""
		res = []
		for column in self.tableReference.fieldInfos.seq:
			res.append(self._makeColumnReference(
				self.tableReference.tableName, column))
		return res

	def getFieldsForTable(self, srcTableName):
		"""returns the fields in srcTable.

		srcTableName is a TableName.
		"""
		table = self.tableReference.fieldInfos.locateTable(srcTableName)
		return [self._makeColumnReference(table.tableName, ci)
			for ci in table.fieldInfos.seq]

	def getAllTables(self):
		return self.tableReference.getAllTables()


class DerivedColumn(FieldInfoedNode):
	"""A column within a select list.
	"""
	type = "derivedColumn"
	_a_expr = None
	_a_alias = None
	_a_tainted = True
	_a_name = None

	def _polish(self):
		if self.name is None:
			if getType(self.expr)=="columnReference":
				self.name = self.expr.name
			else:
				self.name = utils.intToFunnyWord(id(self))
		if getType(self.expr)=="columnReference":
			self.tainted = False

	@classmethod
	def _getInitKWs(cls, _parseResult):
		expr = _parseResult["expr"] #noflake: locals returned
		alias = _parseResult.get("alias") #noflake: locals returned
		if alias is not None:
			name = alias #noflake: locals returned
		return locals()
	
	def flatten(self):
		return flattenKWs(self,
			("", "expr"),
			("AS", "alias"))

	def _treeRepr(self):
		return (self.type, self.name)


class QualifiedStar(ADQLNode):
	type = "qualifiedStar"
	_a_sourceTable = None  # A TableName for the column source

	@classmethod
	def _getInitKWs(cls, _parseResult):
		parts = _parseResult[:-2:2] # kill dots and star
		cat, schema, name = [None]*(3-len(parts))+parts
		return {"sourceTable": TableName(cat=cat, schema=schema, name=name)}
	
	def flatten(self):
		return "%s.*"%flatten(self.sourceTable)


class SelectList(ADQLNode):
	type = "selectList"
	_a_selectFields = ()
	_a_allFieldsQuery = False

	@classmethod
	def _getInitKWs(cls, _parseResult):
		allFieldsQuery = _parseResult.get("starSel", False)
		if allFieldsQuery:
			# Will be filled in by query, we don't have the from clause here.
			selectFields = None  #noflake: locals returned
		else:
			selectFields = list(_parseResult.get("fieldSel")) #noflake: locals returned
		return locals()
	
	def flatten(self):
		if self.allFieldsQuery:
			return self.allFieldsQuery
		else:
			return ", ".join(flatten(sf) for sf in self.selectFields)


######## all expression parts we need to consider when inferring units and such

class Comparison(ADQLNode):
	"""is required when we want to morph the braindead contains(...)=1 into
	a true boolean function call.
	"""
	type = "comparisonPredicate"
	_a_op1 = None
	_a_opr = None
	_a_op2 = None

	@classmethod
	def _getInitKWs(cls, _parseResult):
		op1, opr, op2 = _parseResult #noflake: locals returned
		return locals()
	
	def flatten(self):
		return "%s %s %s"%(flatten(self.op1), self.opr, flatten(self.op2))


def _guessNumericType(literal):
	"""returns a guess for a type suitable to hold a numeric value given in
	literal.

	I don't want to pull through the literal symbol that matched
	from grammar in all cases.  Thus, at times I simply guess the type 
	(and yes, I'm aware that -32768 still is a smallint).
	"""
	try:
		val = int(literal)
		if abs(val)<32767:
			type = "smallint"
		elif abs(val)<2147483648:
			type = "integer"
		else:
			type = "bigint"
	except ValueError:
		type = "double precision"
	return type


class Factor(FieldInfoedNode, TransparentMixin):
	"""is a factor within an SQL expression.

	factors may have only one (direct) child with a field info and copy
	this.  They can have no child with a field info, in which case they're
	simply numeric (about the weakest assumption: They're doubles).
	"""
	type = "factor"
	collapsible = True

	def addFieldInfo(self, context):
		infoChildren = self._getInfoChildren()
		if infoChildren:
			assert len(infoChildren)==1
			self.fieldInfo = infoChildren[0].fieldInfo
		else:
			self.fieldInfo = fieldinfo.FieldInfo(
				_guessNumericType("".join(self.children)), "", "")


class CombiningFINode(FieldInfoedNode):
	def addFieldInfo(self, context):
		infoChildren = self._getInfoChildren()
		if not infoChildren:
			if len(self.children)==1: 
				# probably a naked numeric literal in the grammar, e.g., 
				# in mathFunction
				self.fieldInfo = fieldinfo.FieldInfo(
					_guessNumericType(self.children[0]), "", "")
			else:
				raise common.Error("Oops -- did not expect '%s' when annotating %s"%(
					"".join(self.children), self))
		elif len(infoChildren)==1:
			self.fieldInfo = infoChildren[0].fieldInfo
		else:
			self.fieldInfo = self._combineFieldInfos()


class Term(CombiningFINode, TransparentMixin):
	type = "term"
	collapsible = True

	def _combineFieldInfos(self):
# These are either multiplication or division
		toDo = self.children[:]
		opd1 = toDo.pop(0)
		fi1 = opd1.fieldInfo
		while toDo:
			opr = toDo.pop(0)
			fi1 = fieldinfo.FieldInfo.fromMulExpression(opr, fi1, 
				toDo.pop(0).fieldInfo)
		return fi1


class NumericValueExpression(CombiningFINode, TransparentMixin):
	type = "numericValueExpression"
	collapsible = True

	def _combineFieldInfos(self):
# These are either addition or subtraction
		toDo = self.children[:]
		fi1 = toDo.pop(0).fieldInfo
		while toDo:
			opr = toDo.pop(0)
			fi1 = fieldinfo.FieldInfo.fromAddExpression(
				opr, fi1, toDo.pop(0).fieldInfo)
		return fi1


class StringValueExpression(FieldInfoedNode, TransparentMixin):
	type = "stringValueExpression"
	collapsible = True

	def addFieldInfo(self, context):
# This is concatenation; we treat is as if we'd be adding numbers
		infoChildren = self._getInfoChildren()
		if infoChildren:
			fi1 = infoChildren.pop(0).fieldInfo
			if fi1.type=="unicode":
				baseType = "unicode"
			else:
				baseType = "text"
			while infoChildren:
				if infoChildren[0].fieldInfo.type=="unicode":
					baseType = "unicode"
				fi1 = fieldinfo.FieldInfo.fromAddExpression(
					"+", fi1, infoChildren.pop(0).fieldInfo, forceType=baseType)
			self.fieldInfo = fi1
		else:
			self.fieldInfo = fieldinfo.FieldInfo(
				"text", "", "")
	

class GenericValueExpression(CombiningFINode, TransparentMixin):
	"""A container for value expressions that we don't want to look at
	closer.

	It is returned by the makeValueExpression factory below to collect
	stray children.
	"""
	def _combineFieldInfos(self):
		# we don't really know what these children are.  Let's just give up
		# unless all child fieldInfos are more or less equal (which of course
		# is a wild guess).
		childUnits, childUCDs = set(), set()
		infoChildren = self._getInfoChildren()
		for c in infoChildren:
			childUnits.add(c.fieldInfo.unit)
			childUCDs.add(c.fieldInfo.ucd)
		if len(childUnits)==1 and len(childUCDs)==1:
			# let's taint the first info and be done with it
			return infoChildren[0].fieldInfo.copyModified(tainted=True)
		else:
			# if all else fails: let's hope someone can make a string from it
			return fieldinfo.FieldInfo("text", "", "")


@symbolAction("valueExpression")
def makeValueExpression(children):
	if len(children)!=1:
		res = GenericValueExpression.fromParseResult(children)
		res.type = "valueExpression"
		return res
	else:
		return children[0]


class SetFunction(TransparentMixin, FieldInfoedNode):
	"""is an aggregate function.

	These typically amend the ucd by a word from the stat family and copy
	over the unit.  There are exceptions, however, see table in class def.
	"""
	type = "setFunctionSpecification"

	funcDefs = {
		'AVG': ('stat.mean', None, "double precision"),
		'MAX': ('stat.max', None, None),
		'MIN': ('stat.min', None, None),
		'SUM': (None, None, None),
		'COUNT': ('meta.number', '', "integer"),}

	def addFieldInfo(self, context):
		ucdPref, newUnit, newType = self.funcDefs[self.children[0].upper()]

		# try to find out about our child
		infoChildren = self._getInfoChildren()
		if infoChildren:
			assert len(infoChildren)==1
			fi = infoChildren[0].fieldInfo
		else:
			fi = fieldinfo.FieldInfo("double precision", "", "")

		if ucdPref is None:
			# ucd of a sum is the ucd of the summands?
			ucd = fi.ucd
		else:
			ucd = ";".join(p for p in (ucdPref, fi.ucd) if p)

		# most of these keep the unit of what they're working on
		if newUnit is None:
			newUnit = fi.unit

		# most of these keep the type of what they're working on
		if newType is None:
			newType = fi.type

		self.fieldInfo = fieldinfo.FieldInfo(
			newType, unit=newUnit, ucd=ucd, userData=fi.userData, tainted=fi.tainted)


class NumericValueFunction(FunctionNode):
	"""is a numeric function.

	This is really a mixed bag.  We work through handlers here.  See table
	in class def.  Unknown functions result in dimlesses.
	"""
	type = "numericValueFunction"
	collapsible = True  # if it's a real function call, it has at least
		# a name, parens and an argument and thus won't be collapsed.

	funcDefs = {
		"ACOS": ('rad', '', None),
		"ASIN": ('rad', '', None),
		"ATAN": ('rad', '', None),
		"ATAN2": ('rad', '', None),
		"PI": ('', '', None),
		"RAND": ('', '', None),
		"EXP": ('', '', None),
		"LOG": ('', '', None),
		"LOG10": ('', '', None),
		"SQRT": ('', '', None),
		"SQUARE": ('', '', None),
		"POWER": ('', '', None),
		"ABS": (None, None, "keepMeta"),
		"CEILING": (None, None, "keepMeta"),
		"FLOOR": (None, None, "keepMeta"),
		"ROUND": (None, None, "keepMeta"),
		"TRUNCATE": (None, None, "keepMeta"),
		"DEGREES": ('deg', None, "keepMeta"),
		"RADIANS": ('rad', None, "keepMeta"),
	}

	def _handle_keepMeta(self, infoChildren):
		fi = infoChildren[0].fieldInfo
		return fi.unit, fi.ucd

	def addFieldInfo(self, context):
		infoChildren = self._getInfoChildren()
		unit, ucd = '', ''
		overrideUnit, overrideUCD, handlerName = self.funcDefs.get(
			self.funName, ('', '', None))
		if handlerName:
			unit, ucd = getattr(self, "_handle_"+handlerName)(infoChildren)
		if overrideUnit:
			unit = overrideUnit
		if overrideUCD:
			ucd = overrideUCD
		self.fieldInfo = fieldinfo.FieldInfo("double precision",
			unit, ucd, *collectUserData(infoChildren))
		self.fieldInfo.tainted = True


class CharacterStringLiteral(FieldInfoedNode):
	"""according to the current grammar, these are always sequences of
	quoted strings.
	"""
	type = "characterStringLiteral"
	bindings = ["characterStringLiteral", "generalLiteral"]

	_a_value = None

	@classmethod
	def _getInitKWs(cls, _parseResult):
		value = "".join(_c[1:-1] for _c in _parseResult) #noflake: locals returned
		return locals()

	def flatten(self):
		return "'%s'"%(self.value.replace("'", "\\'"))

	def addFieldInfo(self, context):
		self.fieldInfo = fieldinfo.FieldInfo("text", "", "")


###################### Geometry and stuff that needs morphing into real SQL

class CoosysMixin(object):
	"""is a mixin that works cooSys into FieldInfos for ADQL geometries.
	"""
	_a_cooSys = None

	@classmethod
	def _getInitKWs(cls, _parseResult):
		refFrame = _parseResult.get("coordSys", "")
		if isinstance(refFrame, ColumnReference):
			raise NotImplementedError("References frames must not be column"
				" references.")
		return {"cooSys":  refFrame}


class GeometryNode(CoosysMixin, FieldInfoedNode):
	"""Nodes for geometry constructors.

	Although these look like functions, they are different in that their
	"arguments" are explicitely named.  We repeat that here, so all
	Geometries need _getInitKWs methods.

	Also, this needs custom flattening.  To keep it simple, they just define
	argSeq attributes containing the names of the attributes to be flattened
	to obtain the arguments.
	"""
	def flatten(self):
		return "%s(%s)"%(self.type.upper(),
			", ".join(flatten(getattr(self, name)) for name in self.argSeq))

	def addFieldInfo(self, context):
		fis = [fi 
			for fi in (getattr(self, arg).fieldInfo for arg in self.argSeq)
			if fi.stc]
		childUserData, childUnits = [], []
		thisSystem = tapstc.getSTCForTAP(self.cooSys)

		# get reference frame from first child if not given in node
		if thisSystem.astroSystem.spaceFrame.refFrame is None:
			if fis:
				thisSystem = fis[0].stc

		for index, fi in enumerate(fis):
			childUserData.extend(fi.userData)
			childUnits.append(fi.unit)
			if not context.policy.match(fi.stc, thisSystem):
				context.errors.append("When constructing %s: Argument %d has"
					" incompatible STC"%(self.type, index+1))

		self.fieldInfo = fieldinfo.FieldInfo(
			type=self.sqlType,
			unit=",".join(childUnits), 
			ucd="", 
			userData=tuple(childUserData), 
			stc=thisSystem)
		self.fieldInfo.properties["xtype"] = self.xtype


class Point(GeometryNode):
	type = "point"
	_a_x = _a_y = None
	xtype = "adql:POINT"
	sqlType = "spoint"

	argSeq = ("x", "y")

	@classmethod
	def _getInitKWs(cls, _parseResult):
		x, y = parseArgs(_parseResult["args"]) #noflake: locals returned
		return locals()


class Circle(GeometryNode):
	type = "circle"
	_a_x = _a_y = _a_radius = None
	argSeq = ("x", "y", "radius")
	xtype = "adql:REGION"
	sqlType = "scircle"

	@classmethod
	def _getInitKWs(cls, _parseResult):
		x, y, radius = parseArgs(_parseResult["args"]) #noflake: locals returned
		return locals()


class Box(GeometryNode):
	type = "box"
	_a_x = _a_y = _a_width = _a_height = None
	argSeq = ("x", "y", "width", "height")
	xtype = "adql:REGION"
	sqlType = "sbox"

	@classmethod
	def _getInitKWs(cls, _parseResult):
		x, y, width, height = parseArgs( #noflake: locals returned
			_parseResult["args"])
		return locals()


class Polygon(GeometryNode):
	type = "polygon"
	_a_coos = ()
	argSeq = ("coos",)
	xtype = "adql:REGION"
	sqlType = "spoly"

	@classmethod
	def _getInitKWs(cls, _parseResult):
		toDo = list(parseArgs(_parseResult["args"]))
		coos = []
		while toDo:
			coos.append(tuple(toDo[:2])) 
			del toDo[:2]
		return {"coos": tuple(coos)}

	def addFieldInfo(self, name):
		# XXX TODO: add a proper field info here
		self.fieldInfo = fieldinfo.FieldInfo("POLYGON", "", "")


_regionMakers = [] 
def registerRegionMaker(fun):
	"""adds a region maker to the region resolution chain.

	region makers are functions taking the argument to REGION and
	trying to do something with it.  They should return either some
	kind of FieldInfoedNode that will then replace the REGION or None,
	in which case the next function will be tried.

	As a convention, region specifiers here should always start with
	an identifier (like simbad, siapBbox, etc, basically [A-Za-z]+).
	The rest is up to the region maker, but whitespace should separate
	this rest from the identifier.
	"""
	_regionMakers.append(fun)


@symbolAction("region")
def makeRegion(children):
	if len(children)!=4 or not isinstance(children[2], CharacterStringLiteral):
		raise common.RegionError("Invalid argument to REGION: '%s'."%
			"".join(flatten(c) for c in children[2:-1]),
			hint="Here, regions must be simple strings; concatenations or"
			" non-constant parts are forbidden.  Use ADQL geometry expressions"
			" instead.")
	arg = children[2].value
	for r in _regionMakers:
		res = r(arg)
		if res is not None:
			return res
	raise common.RegionError("Invalid argument to REGION: '%s'."%
		arg, hint="None of the region parsers known to this service could"
		" make anything of your string.  While STC-S should in general"
		" be comprehendable to TAP services, it's probably better to"
		" use ADQL geometry functions.")


class STCSRegion(FieldInfoedNode):
	bindings = []     # we're constructed by makeSTCSRegion, not by the parser
	type = "stcsRegion"
	xtype = "adql:REGION"

	_a_tapstcObj = None # from tapstc -- STCSRegion or a utils.pgshere object

	def _polish(self):
		self.cooSys = self.tapstcObj.cooSys

	def addFieldInfo(self, context):
		# XXX TODO: take type and unit from tapstcObj
		self.fieldInfo = fieldinfo.FieldInfo("spoly", unit="deg", ucd=None, 
			stc=tapstc.getSTCForTAP(self.cooSys))
	
	def flatten(self):
		raise common.FlattenError("STCRegion objectcs cannot be flattened, they"
			" must be morphed.")


def makeSTCSRegion(spec):
	try:
		return STCSRegion(stc.parseSimpleSTCS(spec))
	except stc.STCSParseError:  #Not a valid STC spec, try next region parser
		return None

registerRegionMaker(makeSTCSRegion)


class Centroid(FunctionNode):
	type = "centroid"

	def addFieldInfo(self, context):
		self.fieldInfo = fieldinfo.FieldInfo(type="spoint",
			unit="", ucd="",
			userData=collectUserData(self._getInfoChildren())[0])


class Distance(FunctionNode):
	type = "distanceFunction"

	def addFieldInfo(self, context):
		self.fieldInfo = fieldinfo.FieldInfo(type="double precision",
			unit="deg", ucd="pos.angDistance", 
			userData=collectUserData(self._getInfoChildren())[0])


class PredicateGeometryFunction(FunctionNode):
	type = "predicateGeometryFunction"

	_pgFieldInfo = fieldinfo.FieldInfo("integer", "", "")

	def addFieldInfo(self, context):
		# swallow all upstream info, it really doesn't help here
		self.fieldInfo = self._pgFieldInfo

	def flatten(self):
		return "%s(%s)"%(self.funName, ", ".join(flatten(a) for a in self.args))


class PointFunction(FunctionNode):
	type = "pointFunction"

	def _makeCoordsysFieldInfo(self):
		return fieldinfo.FieldInfo("text", unit="", ucd="meta.ref;pos.frame")
	
	def _makeCoordFieldInfo(self):
		# unfortunately, our current system gives us no way to access the
		# actual point (that has proper field infos).  However,
		# if there's two userData items in the child's field info, we
		# save at least that.
		ind = int(self.funName[-1])-1
		cfi = self.args[0].fieldInfo
		try:
			unit = cfi.unit.split(",")[ind]
		except (TypeError, ValueError, IndexError):
			unit = None
		userData = ()
		if len(cfi.userData)==2:
			userData = (cfi.userData[ind],)
		return fieldinfo.FieldInfo("double precision", 
			ucd=None, unit=unit, userData=userData)

	def addFieldInfo(self, context):
		if self.funName=="COORDSYS":
			makeFieldInfo = self._makeCoordsysFieldInfo
		else: # it's coordN
			makeFieldInfo = self._makeCoordFieldInfo
		self.fieldInfo = makeFieldInfo()


class Area(FunctionNode):
	type = "area"

	def addFieldInfo(self, context):
		self.fieldInfo = fieldinfo.FieldInfo(type="double precision",
			unit="deg2", ucd="phys.angSize", 
			userData=collectUserData(self._getInfoChildren())[0])
