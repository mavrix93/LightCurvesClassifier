"""
Definition of rowmakers.

rowmakers are objects that take a dictionary of some kind and emit
a row suitable for inclusion into a table.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import bisect
import fnmatch
import re
import sys
import traceback

from gavo import base
from gavo import utils
from gavo.rscdef import common
from gavo.rscdef import procdef
from gavo.rscdef import rmkfuncs
from gavo.rscdef import rowtriggers


__docformat__ = "restructuredtext en"


class Error(base.Error):
	pass


class MappedExpression(base.Structure):
	"""a base class for map and var.

	You must give a destDict class attribute to make these work.
	"""
	
	destDict = None
	restrictedMode = False

	_dest = base.UnicodeAttribute("key", 
		default=base.Undefined, 
		description="Name of the column the value is to end up in.",
		copyable=True, 
		strip=True, 
		aliases=["dest", "name"])

	_src = base.UnicodeAttribute("source", 
		default=None,
		description="Source key name to convert to column value (either a grammar"
		" key or a var).", 
		copyable=True, 
		strip=True,
		aliases=["src"])

	_nullExcs = base.UnicodeAttribute("nullExcs", 
		default=base.NotGiven,
		description="Exceptions that should be caught and"
		" cause the value to be NULL, separated by commas.")

	_expr = base.DataContent(
		description="A python expression giving the value for key.", 
		copyable=True, 
		strip=True)

	_nullExpr = base.UnicodeAttribute("nullExpr", 
		default=base.NotGiven,
		description="A python expression for a value that is mapped to"
		" NULL (None).  Equality is checked after building the value, so"
		" this expression has to be of the column type.  Use map with"
		" the parseWithNull function to catch null values before type"
		" conversion.")

	def completeElement(self, ctx):
		self.restrictedMode = getattr(ctx, "restricted", False)
		if self.restrictedMode and (
				self.content_
				or self.nullExpr
				or self.nullValue):
			raise base.RestrictedElement("map", hint="In restricted mode, only"
				" maps with a source attribute are allowed; nullExpr or nullValue"
				" are out, too, since they can be used to inject raw code.")
		if not self.content_ and not self.source:
			self.source = self.key
		if self.content_ and "\\" in self.content_:
			self.content_ = self.parent.expand(self.content_)

	def validate(self):
		"""checks that code content is a parseable python expression and that
		the destination exists in the tableDef
		"""
		self._validateNext(MappedExpression)

		if (self.content_ and self.source) or not (self.content_ or self.source):
			raise base.StructureError("Map must have exactly one of source attribute"
				" or element content")

		if not utils.identifierPattern.match(self.key):
			raise base.LiteralParseError("name", self.key,
				hint="Var keys must be valid python"
				" identifiers, and '%s' is not"%self.key)

		if self.source:
			if not utils.identifierPattern.match(self.source):
				raise base.LiteralParseError("source", self.source,
					hint="Map sources must be (python)"
					" identifiers, and '%s' is not"%self.source)

		if self.nullExpr is not base.NotGiven:
			utils.ensureExpression(self.nullExpr)

		if self.content_:
			utils.ensureExpression(common.replaceProcDefAt(self.content_), self.name_)

		if self.nullExcs is not base.NotGiven:
			utils.ensureExpression(self.nullExcs, "%s.nullExcs"%(self.name_))

	def getCode(self, columns):
		"""returns python source code for this map.
		"""
		code = []

		if self.content_:
			code.append('%s["%s"] = %s'%(self.destDict, self.key, self.content_))
		else:
			colDef = columns.getColumnByName(self.key)
			try:
				code.append('%s["%s"] = %s'%(self.destDict,
					self.key, 
					base.sqltypeToPythonCode(colDef.type)%'vars["%s"]'%self.source))
			except base.ConversionError:
				raise base.ui.logOldExc(base.LiteralParseError("map", colDef.type,
					hint="Auto-mapping to %s is impossible since"
					" no default map for %s is known"%(self.key, colDef.type)))

		if self.nullExpr is not base.NotGiven:
			code.append('\nif %s["%s"]==%s: %s["%s"] = None'%(
				self.destDict,
				self.key, 
				self.nullExpr, 
				self.destDict,
				self.key))
		code = "".join(code)

		if self.nullExcs is not base.NotGiven:
			code = 'try:\n%s\nexcept (%s): %s["%s"] = None'%(
				re.sub("(?m)^", "  ", code), 
				self.nullExcs, 
				self.destDict,
				self.key)
		return code


class MapRule(MappedExpression):
	"""A mapping rule.

	To specify the source of a mapping, you can either
	
	- grab a value from what's emitted by the grammar or defined using var via
		the source attribute.  The value given for source is converted to a 
		python value and stored.
	- or give a python expression in the body.  In that case, no further
	  type conversion will be attempted.

	If neither source or a body is given, map uses the key attribute as its
	source attribute.

	The map rule generates a key/value pair in the result record.
	"""
	name_ = "map"
	destDict = "result"


class VarDef(MappedExpression):
	"""A definition of a rowmaker variable.

	It consists of a name and a python expression, including function
	calls.  The variables are entered into the input row coming from
	the grammar.

	var elements are evaluated before apply elements, in the sequence
	they are in the RD.  You can refer to keys defined by vars already
	evaluated in the usual @key manner.
	"""
	name_ = "var"
	destDict = "vars"


class ApplyDef(procdef.ProcApp):
	"""A code fragment to manipulate the result row (and possibly more).

	Apply elements allow embedding python code in rowmakers.

	The current input fields from the grammar (including the rowmaker's vars) 
	are available in the vars dictionary and can be changed there.  You can 
	also add new keys.

	You can add new keys for shipping out in the result dictionary.

	The active rowmaker is available as parent.  It is also used to
	expand macros.

	The table that the rowmaker feeds to can be accessed as targetTable.  
	You probably only want to change meta information here (e.g., warnings 
	or infos).

	As always in procApps, you can get the embedding RD as rd; this is
	useful to, e.g., resolve references using rd.getByRD, and specify 
	resdir-relative file names using rd.getAbsPath.
	"""
	name_ = "apply"
	requiredType = "apply"
	formalArgs = "vars, result, targetTable"
	
	def getFuncCode(self):
		return common.replaceProcDefAt(procdef.ProcApp.getFuncCode(self))


class RowmakerMacroMixin(base.StandardMacroMixin):
	"""is a collection of macros available to rowmakers.

	NOTE: All macros should return only one single physical python line,
	or they will mess up the calculation of what constructs caused errors.
	"""
	def macro_standardPubDID(self):
		"""returns the "standard publisher DID" for the current product.

		The publisher dataset identifier (PubDID) is important in protocols like
		SSAP and obscore.  If you use this macro, the PubDID will be your
		authority, the path compontent ~, and the inputs-relative path of 
		the input file as the parameter.

		You *can* of course define your PubDIDs in a different way.
		"""
		return ('getStandardPubDID(vars["parser_"].sourceToken)')

	def macro_inputRelativePath(self, liberalChars="True"):
		"""returns an expression giving the current source's path 
		relative to inputsDir
		"""
		return ('getInputsRelativePath('
			'vars["parser_"].sourceToken, liberalChars=%s)'
			)%base.parseBooleanLiteral(liberalChars)
	
	def macro_rowsProcessed(self):
		"""returns an expression giving the number of records already 
		ingested for this source.
		"""
		return 'vars["parser_"].recNo'

	def macro_property(self, property):
		"""returns an expression giving the property on the current DD.
		"""
		return 'curDD_.getProperty("%s")'%property

	def macro_sourceDate(self):
		"""returns an expression giving the timestamp of the current source.
		"""
		return ('datetime.utcfromtimestamp('
			'os.path.getmtime(vars["parser_"].sourceToken))')
		
	def macro_srcstem(self):
		"""returns the stem of the source file currently parsed.
		
		Example: if you're currently parsing /tmp/foo.bar, the stem is foo.
		"""
		return 'os.path.splitext(os.path.basename(vars["parser_"].sourceToken))[0]'

	def macro_lastSourceElements(self, numElements):
		"""returns an expression calling rmkfuncs.lastSourceElements on
		the current input path.
		"""
		return 'lastSourceElements(vars["parser_"].sourceToken, int(numElements))'

	def macro_rootlessPath(self):
		"""returns an expression giving the current source's path with 
		the resource descriptor's root removed.
		"""
		return 'utils.getRelativePath(rd_.resdir, vars["parser_"].sourceToken)'

	def macro_inputSize(self):
		"""returns an expression giving the size of the current source.
		"""
		return 'os.path.getsize(vars["parser_"].sourceToken)'

	def macro_docField(self, name):
		"""returns an expression giving the value of the column name in the 
		document parameters.
		"""
		return '_parser.getParameters()[fieldName]'

	def macro_qName(self):
		"""returns the qName of the table we are currently parsing into.
		"""
		return "tableDef.getQName()"


class RowmakerDef(base.Structure, RowmakerMacroMixin):
	"""A definition of the mapping between grammar input and finished rows
	ready for shipout.

	Rowmakers consist of variables, procedures and mappings.  They
	result in a python callable doing the mapping.

	RowmakerDefs double as macro packages for the expansion of various
	macros.  The standard macros will need to be quoted, the rowmaker macros
	above yield python expressions.

	Within map and var bodies as well as late apply pars and apply bodies, 
	you can refer to the grammar input as vars["name"] or, shorter @name.

	To add output keys, use map or, in apply bodies, add keys to the
	result dictionary.
	"""
	name_ = "rowmaker"

	_maps = base.StructListAttribute("maps", childFactory=MapRule,
		description="Mapping rules.", copyable=True)
	_vars = base.StructListAttribute("vars", childFactory=VarDef,
		description="Definitions of intermediate variables.",
		copyable=True)
	_apps = base.StructListAttribute("apps",
		childFactory=ApplyDef, description="Procedure applications.",
		copyable=True)
	_rd = common.RDAttribute()
	_idmaps = base.StringListAttribute("idmaps", description="List of"
		' column names that are just "mapped through" (like map with key'
		" only); you can use shell patterns to select multiple colums at once.",
		copyable=True)
	_simplemaps = base.IdMapAttribute("simplemaps", description=
		"Abbreviated notation for <map source>; each pair is destination:source", 
		copyable=True)
	_ignoreOn = base.StructAttribute("ignoreOn", default=None,
		childFactory=rowtriggers.IgnoreOn, description="Conditions on the"
		" input record coming from the grammar to cause the input"
		" record to be dropped by the rowmaker, i.e., for this specific"
		" table.  If you need to drop a row for all tables being fed,"
		" use a trigger on the grammar.", copyable=True)
	_original = base.OriginalAttribute()

	@classmethod
	def makeIdentityFromTable(cls, table, **kwargs):
		"""returns a rowmaker that just maps input names to column names.
		"""
		if "id" not in kwargs:
			kwargs["id"] = "autogenerated rowmaker for table %s"%table.id
		return base.makeStruct(cls, idmaps=[c.name for c in table], **kwargs)

	@classmethod
	def makeTransparentFromTable(cls, table, **kwargs):
		"""returns a rowmaker that maps input names to column names without
		touching them.

		This is for crazy cases in which the source actually provides 
		pre-parsed data that any treatment would actually ruin.
		"""
		if "id" not in kwargs:
			kwargs["id"] = "autogenerated rowmaker for table %s"%table.id
		return base.makeStruct(cls, maps=[
				base.makeStruct(MapRule, key=c.name, content_="vars[%s]"%repr(c.name))
					for c in table],
			**kwargs)

	def completeElement(self, ctx):
		if self.simplemaps:
			for k,v in self.simplemaps.iteritems():
				nullExcs = base.NotGiven
				if v.startswith("@"):
					v = v[1:]
					nullExcs = "KeyError,"
				self.feedObject("maps", base.makeStruct(MapRule, 
					key=k, source=v, nullExcs=nullExcs))
		self._completeElementNext(RowmakerDef, ctx)

	def _getSourceFromColset(self, columns):
		"""returns the source code for a mapper to a column set.
		"""
		lineMap, line = {}, 0
		source = []

		def appendToSource(srcLine, line, lineMarker):
			source.append(srcLine)
			line += 1
			lineMap[line] = lineMarker
			line += source[-1].count("\n")
			return line

		if self.ignoreOn:
			line = appendToSource("if checkTrigger(vars):\n"
				"  raise IgnoreThisRow(vars)",
				line, "Checking ignore")
		for v in self.vars:
			line = appendToSource(v.getCode(columns), line, "assigning "+v.key)
		for a in self.apps:
			line = appendToSource(
				"%s(vars, result, targetTable)"%a.name, 
				line, "executing "+a.name)
		for m in self.maps:
			line = appendToSource(m.getCode(columns), line, "building "+m.key)
		return "\n".join(source), lineMap

	def _getSource(self, tableDef):
		"""returns the source code for a mapper to tableDef's columns.
		"""
		return self._getSourceFromColset(tableDef.columns)

	def _getGlobals(self, tableDef):
		globals = {}
		for a in self.apps:
			globals[a.name] = a.compile()
		if self.ignoreOn:
			globals["checkTrigger"] = self.ignoreOn
		globals["tableDef_"] = tableDef
		globals["rd_"] = self.rd
		return globals

	def _resolveIdmaps(self, columns):
		"""adds mappings for self's idmap within column set.
		"""
		if self.idmaps is None:
			return
		existingMaps = set(m.key for m in self.maps)
		baseNames = [c.name for c in columns]
		for colName in self.idmaps:
			matching = fnmatch.filter(baseNames, colName)
			if not matching:
				raise base.NotFoundError(colName, "columns matching", "unknown")
			for dest in matching:
				if dest not in existingMaps:
					self.maps.append(MapRule(self, key=dest).finishElement(None))
		self.idmaps = []

	def _checkTable(self, columns, id):
		"""raises a LiteralParseError if we try to map to non-existing
		columns.
		"""
		for map in self.maps:
			try:
				columns.getColumnByName(map.key)
			except KeyError:
				raise base.ui.logOldExc(base.LiteralParseError(self.name_, map.key, 
					"Cannot map to '%s' since it does not exist in %s"%(
						map.key, id)))

	def _buildForTable(self, tableDef):
		"""returns a RowmakerDef with everything expanded and checked for
		tableDef.

		This may raise LiteralParseErrors if self's output is incompatible
		with tableDef.
		"""
		res = self.copyShallowly()
		try:
			res._resolveIdmaps(tableDef.columns)
			res._checkTable(tableDef.columns, tableDef.id)
		except base.NotFoundError, ex:
			ex.within = "table %s's columns"%tableDef.id
			raise
		return res

	def _realCompileForTableDef(self, tableDef):
		"""helps compileForTableDef.
		"""
		rmk = self._buildForTable(tableDef)
		source, lineMap = rmk._getSource(tableDef)
		globals = rmk._getGlobals(tableDef)
		return Rowmaker(common.replaceProcDefAt(source), 
			self.id, globals, tableDef.getDefaults(), lineMap)

	def compileForTableDef(self, tableDef):
		"""returns a function receiving a dictionary of raw values and
		returning a row ready for adding to a tableDef'd table.

		To do this, we first make a rowmaker instance with idmaps resolved
		and then check if the rowmaker result and the table structure
		are compatible.
		"""
		return utils.memoizeOn(tableDef, self, self._realCompileForTableDef,
			tableDef)

	def copyShallowly(self):
		return base.makeStruct(self.__class__, maps=self.maps[:], 
			vars=self.vars[:], idmaps=self.idmaps[:], 
			apps=self.apps[:], ignoreOn=self.ignoreOn)


class ParmakerDef(RowmakerDef):
	name_ = "parmaker"

	def _buildForTable(self, tableDef):
		res = self.copyShallowly()
		try:
			res._resolveIdmaps(tableDef.params)
			res._checkTable(tableDef.params, tableDef.id)
		except base.NotFoundError, ex:
			ex.within = "table %s's params"%tableDef.id
			raise
		return res

	def _getSource(self, tableDef):
		"""returns the source code for a mapper to tableDef's columns.
		"""
		return self._getSourceFromColset(tableDef.params)


identityRowmaker = base.makeStruct(RowmakerDef, idmaps="*")


class Rowmaker(object):
	"""A callable that arranges for the mapping of key/value pairs to 
	other key/value pairs.

	Within DaCHS, Rowmakers generate database rows (and parameter dictionaries)
	from the output of grammars.

	It is constructed with the source of the mapping function, a dictionary of
	globals the function should see, a dictionary of defaults, giving keys to be
	inserted into the incoming rowdict before the mapping function is called, and
	a map of line numbers to names handled in that line.

	It is called with a dictionary of locals for the functions (i.e.,
	usually the result of a grammar iterRows).
	"""
	def __init__(self, source, name, globals, defaults, lineMap):
		try:
			self.code = compile(source, "generated mapper code", "exec")
		except SyntaxError, msg:
			raise base.ui.logOldExc(
				base.BadCode(source, "rowmaker", msg))
		self.source, self.name = source, name
		globals.update(rmkfuncs.__dict__)
		self.globals, self.defaults = globals, defaults
		self.keySet = set(self.defaults)
		self.lineMap = sorted(lineMap.items())

	def _guessExSourceName(self, tb):
		"""returns an educated guess as to which mapping should have
		caused that traceback in tb.

		This is done by inspecting the second-topmost stackframe.  It
		must hold the generated line that, possibly indirectly, caused
		the exception.  This line should be in the lineMap generated by
		RowmakerDef._getSource.
		"""
		if tb.tb_next:
			excLine = tb.tb_next.tb_lineno
			base.ui.notifyDebug(
				"Here's the traceback:\n%s"%"".join(traceback.format_tb(tb)))
		else: # toplevel failure, internal
			return "in toplevel (internal failure)"
		destInd = min(len(self.lineMap)-1, 
			bisect.bisect_left(self.lineMap, (excLine, "")))
		# If we're between lineMap entries, the one before the guessed one
		# is the one we want
		if self.lineMap[destInd][0]>excLine and destInd:
			destInd -= 1
		return self.lineMap[destInd][1]

	def _guessError(self, ex, rowdict, tb):
		"""tries to shoehorn a ValidationError out of ex.
		"""
		base.ui.notifyDebug("Rowmaker failed.  Exception below.  Failing source"
			" is:\n%s"%self.source)
		destName = self._guessExSourceName(tb)
		if isinstance(ex, KeyError):
			msg = "Key %s not found in a mapping."%unicode(ex)
			hint = ("This probably means that your grammar did not yield the"
				" field asked for.  Alternatively, bugs in procs might also"
				" cause this.")
		else:
			msg = unicode(str(ex), "iso-8859-1", "replace")
			hint = ("This is a failure in more-or-less user-provided code."
				"  The source of the failing code should be in the log (but make"
				" sure it's the source the error is reported for; with procs,"
				" this might not be the case).")
		raise base.ui.logOldExc(base.ValidationError("While %s in %s: %s"%(
			destName, self.name, msg), destName.split()[-1], rowdict,
			hint=hint))

	def __call__(self, vars, table):
		try:
			locals = {
				"vars": vars,
				"result": {},
				"targetTable": table
			}
			missingKeys = self.keySet-set(vars)
			for k in missingKeys:
				vars[k] = self.defaults[k]
			exec self.code in self.globals, locals
			return locals["result"]
		except rmkfuncs.IgnoreThisRow: # pass these on
			raise
		except base.ValidationError:   # hopefully downstream knows better than we
			raise
		except Exception, ex:
			self._guessError(ex, locals["vars"], sys.exc_info()[2])
