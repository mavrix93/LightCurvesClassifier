"""
Basic handling for embedded procedures.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.

from gavo import base
from gavo import utils
from gavo.rscdef import common
from gavo.rscdef import rmkfuncs



# Move this one to utils?
def unionByKey(*sequences):
	"""returns all items in sequences uniqued by the items' key attributes.

	The order of the sequence items is not maintained, but items in
	later sequences override those in earlier ones.
	"""
	allItems = {}
	for seq in sequences:
		for item in seq:
			allItems[item.key] = item
	return allItems.values()


class RDParameter(base.Structure):
	"""A base class for parameters.
	"""
	_name = base.UnicodeAttribute("key", default=base.Undefined,
		description="The name of the parameter", copyable=True, strip=True,
		aliases=["name"])
	_descr = base.NWUnicodeAttribute("description", default=None,
		description="Some human-readable description of what the"
		" parameter is about", copyable=True, strip=True)
	_expr = base.DataContent(description="The default for the parameter."
		" The special value __NULL__ indicates a NULL (python None) as usual."
		" An empty content means a non-preset parameter, which must be filled"
		" in applications.  The magic value __EMPTY__ allows presetting an"
		" empty string.",
		copyable=True, strip=True, default=base.NotGiven)
	_late = base.BooleanAttribute("late", default=False,
		description="Bind the name not at setup time but at applying"
		" time.  In rowmaker procedures, for example, this allows you to"
		" refer to variables like vars or rowIter in the bindings.")

	def isDefaulted(self):
		return self.content_ is not base.NotGiven

	def validate(self):
		self._validateNext(RDParameter)
		if not utils.identifierPattern.match(self.key):
			raise base.LiteralParseError("name", self.key, hint=
				"The name you supplied was not defined by any procedure definition.")

	def completeElement(self, ctx):
		if self.content_=="__EMPTY__":
			self.content_ = ""
		self._completeElementNext(RDParameter, ctx)


class ProcPar(RDParameter):
	"""A parameter of a procedure definition.

	Bodies of ProcPars are interpreted as python expressions, in
	which macros are expanded in the context of the procedure application's
	parent.  If a body is empty, the parameter has no default and has
	to be filled by the procedure application.
	"""
	name_ = "par"
	def validate(self):
		self._validateNext(ProcPar)
		# Allow non-python syntax when things look like macro calls.
		if self.content_ and not "\\" in self.content_:
			utils.ensureExpression(
				common.replaceProcDefAt(self.content_), self.key)


class Binding(ProcPar):
	"""A binding of a procedure definition parameter to a concrete value.

	The value to set is contained in the binding body in the form of
	a python expression.  The body must not be empty.
	"""
	name_ = "bind"

	def validate(self):
		self._validateNext(Binding)
		if not self.content_ or not self.content_.strip():
			raise base.StructureError("Binding bodies must not be empty.")


class ProcSetup(base.Structure):
	"""Prescriptions for setting up a namespace for a procedure application.

	You can add names to this namespace you using par(ameter)s.
	If a parameter has no default and an procedure application does
	not provide them, an error is raised.

	You can also add names by providing a code attribute containing
	a python function body in code.  Within, the parameters are
	available.  The procedure application's parent can be accessed
	as parent.  All names you define in the code are available as
	globals to the procedure body.

	Caution: Macros are expanded within the code; this means you
	need double backslashes if you want a single backslash in python
	code.
	"""
	name_ = "setup"

	_code = base.ListOfAtomsAttribute("codeFrags",
		description="Python function bodies setting globals for the function"
		" application.  Macros are expanded in the context"
		" of the procedure's parent.", 
		itemAttD=base.UnicodeAttribute("code", description="Python function"
			" bodies setting globals for the function application.  Macros"
			" are expanded in the context of the procedure's parent.",
			copyable=True),
		copyable=True)
	_pars = base.StructListAttribute("pars", ProcPar,
		description="Names to add to the procedure's global namespace.", 
		copyable=True)
	_original = base.OriginalAttribute()

	def _getParSettingCode(self, useLate, indent, bindings):
		"""returns code that sets our parameters.

		If useLate is true, generate for late bindings.  Indent the
		code by indent.  Bindings is is a dictionary overriding
		the defaults or setting parameter values.
		"""
		parCode = []
		for p in self.pars:
			if p.late==useLate:
				val = bindings.get(p.key, base.NotGiven)
				if val is base.NotGiven:
					val = p.content_
				parCode.append("%s%s = %s"%(indent, p.key, val))
		return "\n".join(parCode)

	def getParCode(self, bindings):
		"""returns code doing setup bindings un-indented.
		"""
		return self._getParSettingCode(False, "", bindings)

	def getLateCode(self, bindings):
		"""returns code doing late (in-function) bindings indented with two
		spaces.
		"""
		return self._getParSettingCode(True, "  ", bindings)

	def getBodyCode(self):
		"""returns the body code un-indented.
		"""
		collectedCode = []
		for frag in self.codeFrags:
			collectedCode.append(
				utils.fixIndentation(frag, "", governingLine=1))
		return "\n".join(collectedCode)


class ProcDef(base.Structure, base.RestrictionMixin):
	"""An embedded procedure.

	Embedded procedures are python code fragments with some interface defined
	by their type.  They can occur at various places (which is called procedure
	application generically), e.g., as row generators in grammars, as applys in
	rowmakers, or as SQL phrase makers in condDescs.

	They consist of the actual actual code and, optionally, definitions like
	the namespace setup, configuration parameters, or a documentation.

	The procedure applications compile into python functions with special
	global namespaces.  The signatures of the functions are determined by
	the type attribute.

	ProcDefs are referred to by procedure applications using their id.
	"""
	name_ = "procDef"

	_code = base.UnicodeAttribute("code", default=base.NotGiven,
		copyable=True, description="A python function body.")
	_setup = base.StructListAttribute("setups", ProcSetup,
		description="Setup of the namespace the function will run in", 
		copyable=True)
	_doc = base.UnicodeAttribute("doc", default="", description=
		"Human-readable docs for this proc (may be interpreted as restructured"
		" text).", copyable=True)
	_type = base.EnumeratedUnicodeAttribute("type", default=None, description=
		"The type of the procedure definition.  The procedure applications"
		" will in general require certain types of definitions.",
		validValues=["t_t", "apply", "rowfilter", "sourceFields", "mixinProc",
			"phraseMaker", "descriptorGenerator", "dataFunction", "dataFormatter",
			"metaMaker", "regTest"], 
			copyable=True,
		strip=True)
	_original = base.OriginalAttribute()


	def getCode(self):
		"""returns the body code indented with two spaces.
		"""
		if self.code is base.NotGiven:
			return ""
		else:
			return utils.fixIndentation(self.code, "  ", governingLine=1)

	@utils.memoized
	def getSetupPars(self):
		"""returns all parameters used by setup items, where lexically
		later items override earlier items of the same name.
		"""
		return unionByKey(*[s.pars for s in self.setups])

	def getLateSetupCode(self, boundNames):
		return "\n".join(s.getLateCode(boundNames) for s in self.setups)

	def getParSetupCode(self, boundNames):
		return "\n".join(s.getParCode(boundNames) for s in self.setups)

	def getBodySetupCode(self, boundNames):
		return "\n".join(s.getBodyCode() for s in self.setups)


class ProcApp(ProcDef):
	"""An abstract base for procedure applications.

	Deriving classes need to provide:

		- a requiredType attribute specifying what ProcDefs can be applied.
		- a formalArgs attribute containing a (python) formal argument list
		- of course, a name_ for XML purposes.
	
	They can, in addition, give a class attribute additionalNamesForProcs,
	which is a dictionary that is joined into the global namespace during
	procedure compilation.
	"""
	_procDef = base.ReferenceAttribute("procDef", forceType=ProcDef,
		default=base.NotGiven, description="Reference to the procedure"
		" definition to apply", copyable=True)
	_bindings = base.StructListAttribute("bindings", description=
		"Values for parameters of the procedure definition",
		childFactory=Binding, copyable=True)
	_name = base.UnicodeAttribute("name", default=base.NotGiven,
		description="A name of the proc.  ProcApps compute their (python)"
		" names to be somwhat random strings.  Set a name manually to"
		" receive more easily decipherable error messages.  If you do that,"
		" you have to care about name clashes yourself, though.", strip=True)

	requiredType = None

	additionalNamesForProcs = {}

	def validate(self):
		if self.procDef and self.procDef.type and self.requiredType:
			if self.procDef.type!=self.requiredType:
				raise base.StructureError("The procDef %s has type %s, but"
					" here %s procDefs are required."%(self.procDef.id,
						self.procDef.type, self.requiredType))
		self._validateNext(ProcApp)
		self._ensureParsBound()

	def completeElement(self, ctx):
		self._completeElementNext(ProcApp, ctx)
		if self.name is base.NotGiven:  # make up a name from self's id
			self.name = ("proc%x"%id(self)).replace("-", "")

	@utils.memoized
	def getSetupPars(self):
		"""returns the setup parameters for the proc app, where procDef
		parameters may be overridden by self's parameters.
		"""
		allSetups = []
		if self.procDef is not base.NotGiven:
			allSetups.extend(self.procDef.setups)
		allSetups.extend(self.setups)
		return unionByKey(*[s.pars for s in allSetups])

	def _ensureParsBound(self):
		"""raises an error if non-defaulted pars of procDef are not filled
		by the bindings.
		"""
		bindNames = set(b.key for b in self.bindings)
		for p in self.getSetupPars():
			if not p.isDefaulted():
				if not p.key in bindNames:
					raise base.StructureError("Parameter %s is not defaulted in"
						" %s and thus must be bound."%(p.key, self.name))
			if p.key in bindNames:
				bindNames.remove(p.key)

		if bindNames:
			raise base.StructureError("May not bind non-existing parameter(s)"
				" %s."%(", ".join(bindNames)))

	def onElementComplete(self):
		self._onElementCompleteNext(ProcApp)
		self._boundNames = dict((b.key, b.content_) for b in self.bindings)

	def _combineWithProcDef(self, methodName, boundNames):
		# A slightly tricky helper method for the implementation of get*SetupCode:
		# this combines the results of calling methodName on a procDef
		# (where applicable) with calling it on ProcDef for self.
		parts = []
		if self.procDef is not base.NotGiven:
			parts.append(getattr(self.procDef, methodName)(boundNames))
		parts.append(getattr(ProcDef, methodName)(self, boundNames))
		return "\n".join(parts)

	def getLateSetupCode(self, boundNames):
		return self._combineWithProcDef("getLateSetupCode", boundNames)

	def getParSetupCode(self, boundNames):
		return self._combineWithProcDef("getParSetupCode", boundNames)

	def getBodySetupCode(self, boundNames):
		return self._combineWithProcDef("getBodySetupCode", boundNames)

	def getSetupCode(self):
		code = "\n".join((
			self.getParSetupCode(self._boundNames),
			self.getBodySetupCode(self._boundNames)))
		if "\\" in code:
			code = self.parent.expand(code)
		return code

	def _getFunctionDefinition(self, mainSource):
		"""returns mainSource in a function definition with proper 
		signature including setup of late code.
		"""
		parts = [self.getLateSetupCode(self._boundNames)]
		parts.append(mainSource)
		body = "\n".join(parts)
		if not body.strip():
			body = "  pass"
		return "def %s(%s):\n%s"%(self.name, self.formalArgs,
			body)

	def getFuncCode(self):
		"""returns a function definition for this proc application.

		This includes bindings of late parameters.

		Locally defined code overrides code defined in a procDef.
		"""
		mainCode = ""
		if self.code is base.NotGiven:
			if self.procDef is not base.NotGiven:
				mainCode = self.procDef.getCode()
		else:
			mainCode = self.getCode()
		code = self._getFunctionDefinition(mainCode)
		if "\\" in code:
			code = self.parent.expand(code)
		return code

	def _compileForParent(self, parent):
		"""helps compile.
		"""
		# go get the RD for parent; it's always handy in this kind
		# of code
		curEl = parent
		while not hasattr(curEl, "rd"):
			if curEl.parent:
				curEl = curEl.parent
			else:
				break
		try:
			rd = curEl.rd
		except AttributeError:
			# maybe an unrooted element
			rd = None
			
		return rmkfuncs.makeProc(
				self.name, self.getFuncCode(),
				self.getSetupCode(), parent,
				rd=rd,
				**self.additionalNamesForProcs)

	def compile(self, parent=None):
		"""returns a callable for this procedure application.

		You can pass a different parent; it will then be used to
		expand macros.  If you do not give it, the embedding structure will
		be used.
		"""
		if parent is None:
			parent = self.parent
		return utils.memoizeOn(parent, self, self._compileForParent, parent)
