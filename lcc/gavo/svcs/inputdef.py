"""
Description and handling of inputs to services.

This module in particular describes the InputKey, the primary means
of describing input widgets and their processing.

They are collected in contextGrammars, entities creating input tables
and parameters.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import itertools

from gavo import base
from gavo import grammars
from gavo import rscdef
from gavo import utils
from gavo.protocols import dali
from gavo.rscdef import column
from gavo.svcs import pql
from gavo.svcs import vizierexprs

MS = base.makeStruct


_RENDERER_ADAPTORS = {
	'form': vizierexprs.adaptInputKey,
	'pql': pql.adaptInputKey,
}

def getRendererAdaptor(renderer):
	"""returns a function that returns input keys adapted for renderer.

	The function returns None if no adapter is necessary.  This
	only takes place for inputKeys within a buildFrom condDesc.
	"""
	return _RENDERER_ADAPTORS.get(renderer.parameterStyle)


class InputKey(column.ParamBase):
	"""A description of a piece of input.

	Think of inputKeys as abstractions for input fields in forms, though
	they are used for services not actually exposing HTML forms as well.

	Some of the DDL-type attributes (e.g., references) only make sense here
	if columns are being defined from the InputKey.

	You can give a "defaultForForm" property on inputKeys to supply
	a string literal default that will be pre-filled in the form
	renderer and is friends but not for other renderers (like S*AP).

	Properties evaluated:

	* defaultForForm -- a value entered into form fields by default
	  (be stingy with those; while it's nice to not have to set things
	  presumably right for almost everyone, having to delete stuff
	  you don't want over and over is really annoying).
	* adaptToRenderer -- any non-empty value here causes the param
	  to be adapted for the renderer (e.g., float becomes vizierexpr-float).
		You'll usually not want this, because the expressions are 
		generally evaluated by the database, and the condDescs do the
		adaptation themselves.  This is mainly for rare situations like
		file uploads in custom cores.
	"""
	name_ = "inputKey"

	# XXX TODO: make widgetFactory and showItems properties.
	_widgetFactory = base.UnicodeAttribute("widgetFactory", default=None,
		description="A python expression for a custom widget"
		" factory for this input,"
		" e.g., 'Hidden' or 'widgetFactory(TextArea, rows=15, cols=30)'",
		copyable=True)
	_showItems = base.IntAttribute("showItems", default=3,
		description="Number of items to show at one time on selection widgets.",
		copyable=True)
	_inputUnit = base.UnicodeAttribute("inputUnit", default=None,
		description="Override unit of the table column with this.",
		copyable=True)
	_std = base.BooleanAttribute("std", default=False,
		description="Is this input key part of a standard interface for"
		" registry purposes?",
		copyable=True)
	_multiplicity = base.UnicodeAttribute("multiplicity", default=None,
		copyable=True,
		description="Set"
			" this to single to have an atomic value (chosen at random"
			" if multiple input values are given),"
			" forced-single to have an atomic value"
			" and raise an exception if multiple values come in, or"
			" emit to receive lists.  On the form renderer, this is"
			" ignored, and the values are what nevow formal passes in."
			" If not given, it is single unless there is a values element with"
			" options, in which case it's multiple.")

	# Don't validate meta for these -- while they are children
	# of validated structures (services), they don't need any
	# meta at all.  This should go as soon as we have a sane
	# inheritance hierarchy for tables.
	metaModel = None

	def completeElement(self, ctx):
		self._completeElementNext(InputKey, ctx)
		if self.restrictedMode and self.widgetFactory:
			raise base.RestrictedElement("widgetFactory")

	def onElementComplete(self):
		self._onElementCompleteNext(InputKey)
		# compute scaling if an input unit is given
		self.scaling = None
		if self.inputUnit:
			self.scaling = base.computeConversionFactor(self.inputUnit, self.unit)

		if self.multiplicity is None:
			self.multiplicity = "single"
			if self.isEnumerated():
				# these almost always want lists returned.
				self.multiplicity = "multiple"
	
	def onParentComplete(self):
		if self.parent and hasattr(self.parent, "required"):
			# children of condDescs inherit their requiredness
			# (unless defaulted)
			self.required = self.parent.required
		# but if there's a default, never require an input
		if self.value:
			self.required = False

	@classmethod
	def fromColumn(cls, column, **kwargs):
		"""returns an InputKey for query input to column.
		"""
		if isinstance(column, InputKey):
			if kwargs:
				return column.change(**kwargs)
			else:
				return column

		instance = cls(None)
		instance.feedObject("original", column)

		if column.isEnumerated():
			instance.feedObject("multiplicity", "multiple")

		for k,v in kwargs.iteritems():
			instance.feed(k, v)
		if not "required" in kwargs:
			instance.feedObject("required", False)
		return instance.finishElement(None)


class InputTable(rscdef.TableDef):
	"""an input table for a core.

	For the standard cores, these have no rows but only params, with the
	exception of ComputedCore, which can build program input from rows.

	Typically, however, the input table definition is made from a core's 
	condDescs and thus never explicitely defined.  In these cases, 
	adaptForRenderer becomes relevant.  This is for when one renderer, e.g.,
	form, needs to expose a different interface than another, e.g., a
	protocol-based renderer.  SCS is a good example, where the form renderer
	has a single argument for the position.
	"""
	name_ = "inputTable"
	_params = rscdef.ColumnListAttribute("params",
		childFactory=InputKey, description='Input parameters for'
		' this table.', copyable=True, aliases=["param"])

	def adaptForRenderer(self, renderer):
		"""returns an inputTable tailored for renderer.

		This is discussed in svcs.core's module docstring.
		"""
		newParams, changed = [], False
		rendName = renderer.name
		adaptor = getRendererAdaptor(renderer)

		for param in self.params:
			if param.getProperty("onlyForRenderer", None) is not None:
				if param.getProperty("onlyForRenderer")!=rendName:
					changed = True
					continue
			if param.getProperty("notForRenderer", None) is not None:
				if param.getProperty("notForRenderer")==rendName:
					changed = True
					continue

			if param.getProperty("adaptToRenderer", None) and adaptor:
				changed = True
				param = adaptor(param)

			newParams.append(param)
		if changed:
			return self.change(params=newParams)
		else:
			return self


class ContextRowIterator(grammars.RowIterator):
	"""is a row iterator over "contexts", i.e. single dictionary-like objects.
	"""
	def __init__(self, grammar, sourceToken, **kwargs):
		grammars.RowIterator.__init__(self, grammar,
			utils.CaseSemisensitiveDict(sourceToken),
			**kwargs)

	def _completeRow(self, rawRow):
		dali.mangleUploads(rawRow)

		caseNormalized = dict((k.lower(),v) for k, v in rawRow.iteritems())
		procRow = {}

		if self.grammar.rejectExtras:
			extraNames = set(caseNormalized
				)-set(p.name.lower() for p in self.grammar.inputTable.params)
			if extraNames:
				raise base.ValidationError("The following parameter(s) are"
				" not accepted by this service: %s"%",".join(sorted(extraNames)),
				"(various)")

		for ik in self.grammar.inputTable.params:
			if ik.name in rawRow:
				val = rawRow[ik.name]
			else:
				val = self.grammar.defaults.get(ik.name, None)

			if val is not None and not isinstance(val, list):
				val = [val]

			procRow[ik.name] = val

		return procRow

	def _iterRows(self):
		if self.grammar.rowKey is not base.NotGiven:
			sequences = []

			for ik in self.grammar.iterInputKeys():
				if ik.name==self.grammar.rowKey:
					continue

				val = self.sourceToken.get(ik.name)
				if isinstance(val, list):
					sequences.append((ik.name, itertools.cycle(val)))
				elif val is None or val==[]:
					sequences.append((ik.name, itertools.repeat(
						self.grammar.defaults.get(ik.name))))
				else:
					sequences.append((ik.name, itertools.repeat(val)))
			
			inSeq = self.sourceToken[self.grammar.rowKey]
			if not isinstance(inSeq, list):
				inSeq = [inSeq]

			for item in inSeq:
				row = {self.grammar.rowKey: item}
				for key, iterator in sequences:
					row[key] = iterator.next()
				yield row

	def getParameters(self):
		return self._completeRow(self.sourceToken)
	
	def getLocator(self):
		return "Context input"


class ContextGrammar(grammars.Grammar):
	"""A grammar for web inputs.

	These are almost exclusively in InputDDs.  They hold InputKeys
	defining what they take from the context.

	For DBCores, the InputDDs are generally defined implicitely
	via CondDescs.	Thus, only for other cores will you ever need
	to bother with ContextGrammars (unless you're going for special
	effects).

	The source tokens for context grammars are dictionaries; these
	are either typed dictionaries from nevow, where the values
	usually are atomic, or, preferably, the dictionaries of lists
	from request.args.

	ContextGrammars only yield rows if there's a rowKey defined.
	In that case, an outer join of all other parameters is returned;
	with rowKey defined, the input keys are obtained from the table's
	columns.

	In normal usage, they just yield a single parameter row,
	corresponding to the source dictionary possibly completed with
	defaults, where non-requried input keys get None defaults where not
	given.  Missing required parameters yield errors.

	Since most VO protocols require case-insensitive matching of parameter
	names, matching of input key names and the keys of the input dictionary
	is attempted first literally, then disregarding case.
	"""
	name_ = "contextGrammar"

	_inputTable = base.ReferenceAttribute("inputTable", 
		default=base.NotGiven, 
		description="The table that is to be built using this grammar", 
		copyable=True)

	_inputKeys = rscdef.ColumnListAttribute("inputKeys", 
		childFactory=InputKey, 
		description="Input keys this context grammar should parse."
		"  These must not be given if there is an input table defined.")

	_rowKey = base.UnicodeAttribute("rowKey", 
		default=base.NotGiven,
		description="The name of a key that is used to generate"
			" rows from the input",
		copyable=True)

	_rejectExtras = base.BooleanAttribute("rejectExtras",
		default=False,
		description="If true, the grammar will reject extra input parameters."
			"  Note that for form-based services, there *are* extra parameters"
			" not declared in the services' input tables.  Right now,"
			" contextGrammar does not ignore those.",
		copyable=True)

	_original = base.OriginalAttribute("original")

	rowIterator = ContextRowIterator


	def onElementComplete(self):
		if self.inputKeys==[]:
			if self.inputTable is base.NotGiven:
				raise base.StructureError("Either inputKeys or inputTable"
					" must be given in a context grammar")
			else:
				if self.rowKey:
					self.inputKeys = [InputKey.fromColumn(c) 
						for c in self.inputTable.columns]
				else:
					self.inputKeys = self.inputTable.params

		else:
			if self.inputTable is not base.NotGiven:
				raise base.StructureError("InputKeys and inputTable must not"
					" both be given in a context grammar")
			else:
				columns = []
				if self.rowKey:
					columns = self.inputKeys
				self.inputTable = MS(InputTable, params=self.inputKeys,
					columns=columns)

		self.defaults = {}
		for ik in self.iterInputKeys():
			if not ik.required:
				self.defaults[ik.name] = None
			if ik.value is not None:
				self.defaults[ik.name] = ik.value
		self._onElementCompleteNext(ContextGrammar)

	def iterInputKeys(self):
		for ik in self.inputKeys:
			yield ik


_OPTIONS_FOR_MULTIS = {
	"forced-single": ", single=True, forceUnique=True",
	"single": ", single=True",
	"multiple": "",
}

def makeAutoParmaker(inputTable):
	"""returns a default parmaker for an inputTable.

	The default parmaker feeds all parameters the inputTable wants, taking
	into account the multiplicity.
	"""
	maps = []
	for par in inputTable.params:
		makeValue = "getHTTPPar(vars['%s'], lambda a: %s%s)"%(
			par.name,
			base.sqltypeToPythonCode(par.type)%"a", 
			_OPTIONS_FOR_MULTIS[par.multiplicity])

		if par.required:
			makeValue = "requireValue(%s, %s)"%(makeValue, repr(par.name))

		maps.append(MS(rscdef.MapRule, dest=par.name, content_=makeValue))

	return MS(rscdef.ParmakerDef, maps=maps, id="parameter parser")


class InputDescriptor(rscdef.DataDescriptor):
	"""A data descriptor for defining a core's input.

	In contrast to normal data descriptors, InputDescriptors generate
	a contextGrammar to feed the table mentioned in the first make if
	no grammar is given (this typically is the input table of the core).  
	Conversely, if a contextGrammar is given but no make, a make with a table
	having params defined by the contextGrammar's inputKeys is 
	automatically generated.

	Attributes like auto, dependents, sources and the like probably
	make little sense for input descriptors.
	"""
	name_ = "inputDD"

	def completeElement(self, ctx):
		# If there is a make, i.e. table, infer the context grammar,
		# if there's a context grammar, infer the table.
		if self.makes and self.grammar is None:
			self.feedObject("grammar", MS(ContextGrammar,
				inputTable=self.makes[0].table))
		
		if not self.makes and isinstance(self.grammar, ContextGrammar):
			rowmaker = base.NotGiven
			if getattr(self.grammar, "rowKey", False):
				rowmaker = rscdef.RowmakerDef.makeIdentityFromTable(
					self.grammar.inputTable)

			self.feedObject("make", MS(rscdef.Make, 
				table=self.grammar.inputTable,
				rowmaker=rowmaker,
				parmaker=makeAutoParmaker(self.grammar.inputTable)))
		self._completeElementNext(InputDescriptor, ctx)


def makeAutoInputDD(core):
	"""returns a standard inputDD for a core.

	The standard inputDD is just a context grammar with the core's input
	keys, and the table structure defined by these input keys.
	"""
	return MS(InputDescriptor,
		grammar=MS(ContextGrammar, inputTable=core.inputTable,
# the rejectExtras thing below is an experiment.  It may go away again.
			rejectExtras=getattr(core, "rejectExtras", False)))
