"""
Services, i.e. combinations of a core and at least one renderer.

A Service is something that receives some sort of structured data (typically,
a nevow context, processes it into input data using a grammar (default is
the contextgrammar), pipes it through a core to receive a data set and
optionally tinkers with that data set.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import os
import urllib

from nevow import inevow

from nevow import tags as T, entities as E #noflake: for custom render fcts

from zope.interface import implements

from gavo import base
from gavo import rsc
from gavo import rscdef
from gavo import utils
from gavo.rsc import table
from gavo.rscdef import rmkdef
from gavo.svcs import common
from gavo.svcs import core
from gavo.svcs import inputdef
from gavo.svcs import outputdef
from gavo.svcs import renderers


def adaptTable(origTable, newColumns):
	"""returns a Data instance created from origTable with columns taken from
	newColumns.

	The adaptation works like this:

	(1) if names and units of newColumns are a subset of origTable.columns,
	return a table with the rows from origTable and the columns from
	newColumns.

	(1a) if origTable has a noPostprocess attribute, proceed to (4)

	(2) if names of newColumns are a subset of origTable.columns match
	but one or more units don't, set up a conversion routine and create
	new rows, combining them with newColumns to the result.

	(3) else raise an error.

	(4) Finally, stick the whole thing into a data container.

	This stinks.  I'm plotting to do away with it.
	"""
	if hasattr(origTable, "noPostprocess"):
		colDiffs = None
		newTd = origTable.tableDef

	else:
		colDiffs = base.computeColumnConversions(
			newColumns, origTable.tableDef.columns)
		newTd = origTable.tableDef.copy(origTable.tableDef.parent)
		newTd.columns = newColumns

	if not colDiffs:
		newTable = table.InMemoryTable(newTd, rows=origTable.rows)
		newTable.meta_ = origTable.meta_
		newTable._params = origTable._params

	else: # we need to do work
		rmk = rscdef.RowmakerDef(None)
		for col in newColumns:
			exprStart = ""
			if col.name in colDiffs:
				exprStart = "%s*"%colDiffs[col.name]
			rmk.feedObject("map", rmkdef.MapRule(rmk, dest=col.name,
				content_="%svars[%s]"%(exprStart, repr(col.name))
				).finishElement(None))
		newTable = table.InMemoryTable(newTd, validate=False)
		mapper = rmk.finishElement(None).compileForTableDef(newTd)
		for r in origTable:
			newTable.addRow(mapper(r, newTable))
		newTable._params = origTable._params

	return rsc.wrapTable(newTable, rdSource=origTable.tableDef)


class PreparsedInput(dict):
	"""a sentinel class signalling to the service that its input already
	is parsed.

	This is for for stuff coming from nevow formal rather than request.args,
	and to be fed into service.run.

	Construct with a dictionary.
	"""


class SvcResult(object):
	"""is a nevow.IContainer that has the result and also makes the
	input dataset accessible.

	It is constructed with an InMemoryTable instance coreResult,
	a table instance inputTable, the current querymeta, and a service
	instance.

	If a service is defined, SvcResult adapts coreResult to the
	columns defined by the service (getCurOutputFields).

	Original currently either is an InMemory table, in which case it gets
	adapted to what the service expects, or a data.Data instance (or
	something else; but few renderers will be able to handle "something else"), 
	which is left alone.

	SvcResult also makes queryMeta, inputTable and the service available.	This
	should give renderers access to basically all the information they need.  The
	resultmeta data item collects some of those.

	SvcResult objects must be able to fall back to sensible behaviour
	without a service.  This may be necessary in error handling.
	"""
	implements(inevow.IContainer)
	
	def __init__(self, coreResult, inputTable, queryMeta, service=None):
		self.inputTable = inputTable
		self.queryMeta = queryMeta
		self.service = service
		if (service and isinstance(coreResult, rsc.BaseTable)):
			coreResult = adaptTable(coreResult, 
				service.getCurOutputFields(queryMeta))
		self.original = coreResult

	def data_resultmeta(self, ctx):
		resultmeta = {
			"itemsMatched": self.queryMeta.get("Matched", 
				len(self.original.getPrimaryTable())),
			"Overflow": self.queryMeta.get("Overflow", False),
			"message": "",
		}
		return resultmeta

	def data_querypars(self, ctx=None):
		return dict((k, unicode(v)) 
			for k, v in self.queryMeta.getQueryPars().iteritems())
	
	def data_inputRec(self, ctx=None):
		return self.inputTable.getParamDict()

	def data_table(self, ctx=None):
		return self.original.getPrimaryTable()

	def getParam(self, paramName):
		"""returns getParam of the core result or that of its primary table.
		"""
		try:
			val = self.original.getParam(paramName)
			if val is not None:
				return val
		except (KeyError, base.NotFoundError):
			pass

		return self.original.getPrimaryTable().getParam(paramName)

	def child(self, ctx, name):
		return getattr(self, "data_"+name)(ctx)


class Publication(base.Structure, base.ComputedMetaMixin):
	"""A specification of how a service should be published.

	This contains most of the metadata for what is an interface in
	registry speak.
	"""
	name_ = "publish"

	_rd = rscdef.RDAttribute()
	_render = base.UnicodeAttribute("render", default=base.Undefined,
		description="The renderer the publication will point at.",
		copyable=True)
	_sets = base.StringSetAttribute("sets", 
		description="Comma-separated list of sets this service will be"
			" published in.  Predefined are: local=publish on front page,"
			" ivo_managed=register with the VO registry.  If you leave it"
			" empty, 'local' publication is assumed.",
			copyable="True")
	_service = base.ReferenceAttribute("service", default=base.NotGiven,
		description="Reference for a service actually implementing the"
			" capability corresponding to this publication.  This is"
			" mainly when there is a vs:WebBrowser service accompanying a VO"
			" protocol service, and this other service should be published"
			" in the same resource record.  See also the operator's guite.",
			copyable="True")
	_auxiliary = base.BooleanAttribute("auxiliary", default=False,
		description="Auxiliary publications are for capabilities"
			" not intended to be picked up for all-VO queries, typically"
			" because they are already registered with other services."
			" This is mostly used internally; you probably have no reason"
			" to touch it.")


	def completeElement(self, ctx):
		if self.render is base.Undefined:
			self.render = "form"
		if not self.sets:
			self.sets.add("local")
		if self.service is base.NotGiven:
			self.service = self.parent
		self.setMetaParent(self.service)
		self._completeElementNext(Publication, ctx)

	def validate(self):
		self._validateNext(Publication)
		try:
			renderers.getRenderer(self.render)
		except KeyError:
			raise base.StructureError("Unknown renderer: %s"%self.render)

	def _meta_accessURL(self):
		return self.service.getURL(self.render)

	def _meta_urlUse(self):
		return renderers.getRenderer(self.render).urlUse

	def _meta_requestMethod(self):
		return renderers.getRenderer(self.render).preferredMethod
	
	def _meta_resultType(self):
		return renderers.getRenderer(self.render).resultType


class CustomPageFunction(base.Structure, base.RestrictionMixin):
	"""An abstract base for nevow.rend.Page-related functions on services.
	"""
	_name = base.UnicodeAttribute("name", default=base.Undefined,
		description="Name of the render function (use this in the"
			" n:render attribute in custom templates).", copyable=True, strip=True)
	_code = base.DataContent(description="Function body of the renderer; the"
		" arguments are named ctx and data.", copyable=True)

	def onElementComplete(self):
		self._onElementCompleteNext(CustomPageFunction)
		vars = globals().copy()
		vars["service"] = self.parent
		exec ("def %s(ctx, data):\n%s"%(self.name,
				utils.fixIndentation(self.content_, newIndent="  ",
					governingLine=1).rstrip())) in vars
		self.func = vars[self.name]


class CustomRF(CustomPageFunction):
	"""A custom render function for a service.

	Custom render functions can be used to expose certain aspects of a service
	to Nevow templates.  Thus, their definition usually only makes sense with
	custom templates, though you could, in principle, override built-in
	render functions.

	In the render functions, you have the names ctx for nevow's context and
	data for whatever data the template passes to the renderer. 

	You can return anything that can be in a stan DOM.  Usually, this will be
	a string.  To return HTML, use the stan DOM available under the T namespace.

	As an example, the following code returns the current data as a link::

		return ctx.tag[T.a(href=data)[data]]
	
	You can access the embedding service as service, the embedding
	RD as service.rd.
	"""
	name_ = "customRF"


class CustomDF(CustomPageFunction):
	"""A custom data function for a service.

	Custom data functions can be used to expose certain aspects of a service
	to Nevow templates.  Thus, their definition usually only makes sense with
	custom templates, though you could, in principle, override built-in
	render functions.

	In the data functions, you have the names ctx for nevow's context and
	data for whatever data the template passes to the renderer. 

	You can access the embedding service as service, the embedding
	RD as service.rd.

	You can return arbitrary python objects -- whatever the render functions
	can deal with.  You could, e.g., write::

		<customDF name="now">
			return datetime.datetime.utcnow()
		</customDF>
	"""
	name_ = "customDF"


class CoreAttribute(base.ReferenceAttribute):
	def __init__(self):
		base.ReferenceAttribute.__init__(self, "core", 
			description="The core that does the computations for this service."
			"  Instead of a reference, you can use an immediate element"
			" of some registred core.", 
			forceType=core.Core, copyable=True, aliases=core.CORE_REGISTRY.keys())
	
	def _makeChild(self, name, parent):
		return core.getCore(name)(parent)


class Service(base.Structure, base.ComputedMetaMixin, 
		base.StandardMacroMixin, rscdef.IVOMetaMixin):
	"""A service definition.

	A service is a combination of a core and one or more renderers.  They
	can be published, and they carry the metadata published into the VO.

	You can set the defaultSort property on the service to a name of an
	output column to preselect a sort order.  Note again that this will
	slow down responses for all be the smallest tables unless there is
	an index on the corresponding column.

	Properties evaluated:

	* defaultFormSortKey -- a key to sort on by default.  This differs
	  from the dbCore's sortKey in that this does not suppress the
	  widget itself, it just sets a default for its value.  Don't use
	  this unless you have to; the combination of sort and limit can
	  have disastrous effects on the run time of queries.
	"""
	name_ = "service"

	_core = CoreAttribute()
	_templates = base.DictAttribute("templates", description="Custom"
		' nevow templates for this service; use key "form" to replace the Form'
		" renderer's standard template.  Start the path with two slashes to"
		" access system templates.", 
		itemAttD=rscdef.ResdirRelativeAttribute(
			"template", description="resdir-relative path to a nevow template"
			" used for the function given in key."), copyable=True)
	_publications = base.StructListAttribute("publications",
		childFactory=Publication, description="Sets and renderers this service"
			" is published with.")
	_limitTo = base.UnicodeAttribute("limitTo", default=None,
		description="Limit access to the group given; the empty default disables"
		" access control.", copyable="True")
	_customPage = rscdef.ResdirRelativeAttribute("customPage", default=None,
		description="resdir-relative path to custom page code.  It is used"
		" by the 'custom' renderer", copyable="True")
	_allowedRenderers = base.StringSetAttribute("allowed",
		description="Names of renderers allowed on this service; leave emtpy"
		" to allow the form renderer only.", copyable=True)
	_customRF = base.StructListAttribute("customRFs",
		description="Custom render functions for use in custom templates.",
		childFactory=CustomRF, copyable=True)
	_customDF = base.StructListAttribute("customDFs",
		description="Custom data functions for use in custom templates.",
		childFactory=CustomDF, copyable=True)
	_inputData = base.StructAttribute("inputDD", default=base.NotGiven,
		childFactory=inputdef.InputDescriptor, description="A data descriptor"
			" for obtaining the core's input, usually based on a contextGrammar."
			"  For many cores (e.g., DBCores), you do not want to give this"
			" but rather want to let service figure this out from the core.",
		copyable=True)
	_outputTable = base.StructAttribute("outputTable", default=base.NotGiven,
		childFactory=outputdef.OutputTableDef, copyable=True, description=
		"The output fields of this service.")
	_serviceKeys = base.StructListAttribute("serviceKeys",
		childFactory=inputdef.InputKey, description="Input widgets for"
			" processing by the service, e.g. output sets.", copyable=True)
	_defaultRenderer = base.UnicodeAttribute("defaultRenderer",
		default=None, description="A name of a renderer used when"
		" none is provided in the URL (lets you have shorter URLs).")
	_rd = rscdef.RDAttribute()
	_props = base.PropertyAttribute()
	_original = base.OriginalAttribute()

	metaModel = ("title(1), creationDate(1), description(1),"
		"subject, referenceURL(1), shortName(!)")

	# formats that should query the same fields as HTML (the others behave
	# like VOTables and offer a "verbosity" widget in forms).
	htmlLikeFormats = ["HTML", "tar"]

	####################### Housekeeping methods

	def __repr__(self):
		return "<Service at %x>"%id(self)

	def completeElement(self, ctx):
		self._completeElementNext(Service, ctx)
		if not self.allowed:
			self.allowed.add("form")

		if self.core is base.Undefined:
			# undefined cores are only allowed with custom pages
			# (Deprecated)
			if self.customPage:
				self.core = core.getCore("nullCore")(self.rd).finishElement(None)
				base.ui.notifyWarning("Custom page service %s without nullCore."
					"  This is deprecated, please fix"%self.id)
			else:
				raise base.StructureError("Services must have cores (add <nullCore/>"
					" if you really do not want a core, e.g., with fixed renderers).")

		# if there's only one renderer on this service, make it the default
		if self.defaultRenderer is None and len(self.allowed)==1:
			self.defaultRenderer = list(self.allowed)[0]
		# empty output tables are filled from the core
		if self.outputTable is base.NotGiven:
			self.outputTable = self.core.outputTable

		# cache all kinds of things expensive to create and parse
		self._coresCache = {}
		self._inputDDCache = {}
		self._loadedTemplates = {}
			
	def onElementComplete(self):
		self._onElementCompleteNext(Service)
		
		# Index custom render/data functions
		self.nevowRenderers = {}
		for customRF in self.customRFs:
			self.nevowRenderers[customRF.name] = customRF.func
		self.nevowDataFunctions = {}
		for customDF in self.customDFs:
			self.nevowDataFunctions[customDF.name] = customDF.func

		self._compileCustomPage()

		self._computeResourceType()

	def _compileCustomPage(self):
		if self.customPage:
			try:
				modNs, moddesc = utils.loadPythonModule(self.customPage)
				page = modNs.MainPage
			except ImportError, msg:
				raise base.LiteralParseError("customPage", self.customPage, 
					hint="While loading the custom page you specified, the following"
					" error was raised: '%s'.  See the log for a traceback."%
					unicode(msg))
			self.customPageCode = page, (os.path.basename(self.customPage),)+moddesc

	def getTemplate(self, key):
		"""returns the nevow template for the function key on this service.
		"""
		if key not in self._loadedTemplates:
			from nevow import loaders
			tp = self.templates[key]
			if tp.startswith("//"):
				self._loadedTemplates[key] = common.loadSystemTemplate(tp[2:])
			else:
				self._loadedTemplates[key] = loaders.xmlfile(
					os.path.join(self.rd.resdir, tp))
		return self._loadedTemplates[key]


	################### Registry and related methods.

	def _computeResourceType(self):
		"""sets the resType attribute.

		Services are resources, and the registry code wants to know what kind.
		This method ventures a guess.  You can override this decision by setting
		the resType meta item.
		"""
		if (self.outputTable.columns 
			or self.outputTable.verbLevel
			or "tap" in self.allowed):
			self.resType = "catalogService"
		else: # no output table defined, we're a plain service
			self.resType = "nonTabularService"

	def getPublicationsForSet(self, names):
		"""returns publications for set names in names.

		names must be a set.  If ivo_managed is in names and there is any
		publication at all, artificial VOSI publications are added.
		"""
		res = [pub for pub in self.publications if pub.sets & names]
		vosiSet = set(["ivo_managed"])

		if res and "ivo_managed" in names:
			res.extend((
				base.makeStruct(Publication, render="availability", sets=vosiSet,
					parent_=self),
				base.makeStruct(Publication, render="capabilities", sets=vosiSet,
					parent_=self),
				base.makeStruct(Publication, render="tableMetadata", sets=vosiSet,
					parent_=self),
			))
		return res

	def getURL(self, rendName, absolute=True, **kwargs):
		"""returns the full canonical access URL of this service together 
		with renderer.

		rendName is the name of the intended renderer in the registry
		of renderers.

		With absolute, a fully qualified URL is being returned.

		Further keyword arguments are translated into URL parameters in the
		query part.
		"""
		basePath = "%s%s/%s"%(base.getConfig("web", "nevowRoot"),
			self.rd.sourceId, self.id)
		if absolute:
			basePath = base.getConfig("web", "serverURL")+basePath
		res = renderers.getRenderer(rendName).makeAccessURL(basePath)

		if kwargs:
			res = res+"?"+urllib.urlencode(kwargs)
		return res


	# used by getBrowserURL; keep external higher than form as long as
	# we have mess like Potsdam CdC.
	_browserScores = {"form": 10, "external": 12, "fixed": 15,
		"custom": 3, "img.jpeg": 2, "static": 1}

	def getBrowserURL(self, fq=True):
		"""returns a published URL that's suitable for a web browser or None if
		no such URL can be guessed.

		If you pass fq=False, you will get a path rather than a URL.
		"""
		# There can be multiple candidates for browser URLs (like when a service
		# has both form, static, and external renderers).  If so, we select
		# by plain scores.
		browseables = []
		for rendName in self.allowed:
			if self.isBrowseableWith(rendName):
				browseables.append((self._browserScores.get(rendName, -1), rendName))
		if browseables:
			return self.getURL(max(browseables)[1], absolute=fq)
		else:
			return None
		
	def isBrowseableWith(self, rendName):
		"""returns true if rendering this service through rendName results 
		in something pretty in a web browser.
		"""
		try:
			return bool(renderers.getRenderer(rendName).isBrowseable(self))
		except base.NotFoundError: # renderer name not known
			return False

	def getTableSet(self):
		"""returns a list of table definitions that have something to do with
		this service.

		This is for VOSI-type queries.  Usually, that's just the core's
		queried table or an output table, except when there is a TAP renderer on
		the service.

		All this is a bit heuristic; but then again, there's no rigorous 
		definition for what's to be in a tables endpoint either.
		"""
		tables = []
		
		# output our own outputTable if it sounds reasonable; if so,
		# add the core's queried table, too, if it has one.
		if self.outputTable and self.outputTable.columns:
			tables.append(self.outputTable)
			tables.append(getattr(self.core, "queriedTable", None))

		else:
			# if our outputTable is no good, just use the one of the core
			qt = getattr(self.core, "queriedTable", None)
			if qt is None:
				qt = getattr(self.core, "outputTable", None)
			if qt is not None:
				tables.append(qt)

		# XXX TODO: This stinks big time.  It's because we got TAP factorization
		# wrong.  Sync and async should be renderers, and there should
		# be a core that then could say this kind of thing.  That's not
		# yet the case, so:
		if "tap" in self.allowed:
			# tap never has "native" tables, so start afresh
			tables = []

			mth = base.caches.getMTH(None)
			for tableName in mth.getTAPTables():
				try:
					tables.append(mth.getTableDefForTable(tableName))
				except:
					base.ui.notifyError("Failure trying to retrieve table definition"
						" for table %s.  Please fix the corresponding RD."%tableName)

		return [t for t in tables if t is not None and t.rd is not None]

	def declareServes(self, data):
		"""adds meta to self and data indicating that data is served by
		service.

		This is used by adql and the publish element on data.
		"""
		if data.registration:
			self.addMeta("serviceFor", base.makeMetaValue(
				base.getMetaText(data, "title", default="Anonymous"),
				name="serviceFor",
				ivoId=base.getMetaText(data, "identifier")))
			data.addMeta("servedBy", base.makeMetaValue(
				base.getMetaText(self, "title"),
				name="servedBy",
				ivoId=base.getMetaText(self, "identifier")))

			# Since this is always initiated by the data, the dependency
			# must show up in its RD to be properly added on publication
			# and to be removed when the data is removed.
			data.rd.addDependency(self.rd, data.rd)


	########################## Output field selection (ouch!)

	def _getVOTableOutputFields(self, queryMeta):
		"""returns a list of OutputFields suitable for a VOTable response 
		described by queryMeta.

		This is at least what's given for HTML (except where a displayHint
		of noxml is present), plus possibly additional stuff by verbLevel
		from an outputTable's parent.
		"""
		verbLevel = queryMeta.get("verbosity", 20)
		fields = [f for f in self.getHTMLOutputFields(queryMeta)
				if f.displayHint.get("noxml")!="true"]
		
		if verbLevel!="HTML":
			htmlNames = set(f.name for f in fields)

			for field in self.outputTable.parentTable:
				if field.name in htmlNames:
					continue
				if (field.displayHint.get("type")=="suppress" 
						or field.displayHint.get("noxml")=="true"):
					continue
				if field.verbLevel<=verbLevel:
					fields.append(field)

		return rscdef.ColumnList(fields)

	_allSet = set(["ALL"])

	def getHTMLOutputFields(self, queryMeta, ignoreAdditionals=False,
			raiseOnUnknown=True):
		"""returns a list of OutputFields suitable for an HTML response described
		by queryMeta.

		raiseOnUnknown is used by customwidgets to avoid exceptions because of
		bad additional fields during form construction (when they aren't
		properly caught).
		"""
		requireSet = queryMeta["columnSet"]
		res = rscdef.ColumnList()

		# add "normal" output fields
		if requireSet:
			res.extend([f for f in self.outputTable
					if f.sets==self._allSet or requireSet&f.sets])
		else:
			res.extend([f for f in self.outputTable
				if f.displayHint.get("type")!="suppress"])

		# add user-selected fields
		if not ignoreAdditionals and queryMeta["additionalFields"]:
			cofs = self.core.outputTable.columns
			try:
				for fieldName in queryMeta["additionalFields"]:
					col = cofs.getColumnByName(fieldName)
					if isinstance(col, outputdef.OutputField):
						res.append(col)
					else:
						res.append(outputdef.OutputField.fromColumn(col))
			except base.NotFoundError, msg:
				if raiseOnUnknown:
					raise base.ValidationError("The additional field %s you requested"
						" does not exist"%repr(msg.lookedFor), colName="_OUTPUT")
		return res

	def getCurOutputFields(self, queryMeta=None, raiseOnUnknown=True):
		"""returns a list of desired output fields for query meta.

		This is for both the core and the formatter to figure out the
		structure of the tables passed.

		If queryMeta is not None, both the format and the verbLevel given
		there can influence this choice.
		"""
		queryMeta = queryMeta or common.emptyQueryMeta
		format = queryMeta.get("format", "HTML")
		if format in self.htmlLikeFormats:
			return self.getHTMLOutputFields(queryMeta, raiseOnUnknown=raiseOnUnknown)
		else:
			return self._getVOTableOutputFields(queryMeta)

	def getAllOutputFields(self):
		"""Returns a sequence of all available output fields.

		This is mainly for the registry.  It basically asks the core
		what it has and returns that.

		Unfortunately, this does not reflect what the service actually
		does, but for the registry it's probably the most useful information.
		"""
		return self.core.outputTable.columns

	################### running and input computation.

	def getCoreFor(self, renderer):
		"""returns a core tailored for renderer.

		See svcs.core's module docstring. 
		
		The argument can be a renderer or a renderer name.
		"""
		if isinstance(renderer, basestring):
			renderer = renderers.getRenderer(renderer)

		# non-checked renderers use the core for info purposes only; don't
		# bother for those
		if not renderer.checkedRenderer:
			return self.core

		if renderer.name not in self._coresCache:
			res = self.core.adaptForRenderer(renderer)

			# this is a hack for the highly polymorpous datalink core
			if getattr(res, "nocache", False):
				return res

			self._coresCache[renderer.name] = res
		return self._coresCache[renderer.name]

	def getInputDDFor(self, core=None):
		"""returns an inputDD for renderer.

		If service has a custom inputDD, it will be used for all renderers;
		otherwise, this is an automatic inputDD for the core's inputTable.

		You can pass in a core adapted for a rendere; otherwise, the
		service's default core will be used.
		"""
		if core is None:
			core = self.core

		if self.inputDD:
			return self.inputDD
		else:
			if getattr(core, "nocache", False):
				return inputdef.makeAutoInputDD(core)

			if id(core) not in self._inputDDCache:
				self._inputDDCache[id(core)] = inputdef.makeAutoInputDD(core)
		return self._inputDDCache[id(core)]

	def getInputKeysFor(self, renderer):
		"""returns a sequence of input keys, adapted for certain renderers.

		The renderer argument may either be a renderer name, a renderer
		class or a renderer instance.

		This is the main interface for external entities to discover.
		service metadata.
		"""
		return (self.getInputDDFor(
			self.getCoreFor(renderer)).grammar.inputKeys
			)+self.serviceKeys

	def _hackInputTableFromPreparsed(self, core, args):
		"""returns an input table from dictionaries as produced by nevow formal.
		"""
		args = utils.CaseSemisensitiveDict(args)
		inputDD = self.getInputDDFor(core)
		inputTable = rsc.TableForDef(inputDD.makes[0].table)

		for ik in inputDD.grammar.iterInputKeys():
			if ik.name in args:
				if args[ik.name] is not None:
					inputTable.setParam(ik.name, args[ik.name])
			else:
				inputTable.setParam(ik.name, ik.value)

		return inputTable

	def _makeInputTableFor(self, core, args):
		"""returns an input table for core, filled from contextData.
		"""
		if isinstance(args, PreparsedInput) and not self.inputDD:
			return self._hackInputTableFromPreparsed(core, args)
		else:
			return rsc.makeData(self.getInputDDFor(core),
				parseOptions=rsc.parseValidating, forceSource=args
					).getPrimaryTable()

	def _runWithInputTable(self, core, inputTable, queryMeta):
		"""runs the core and formats an SvcResult.

		This is an internal method.
		"""
		coreRes = core.run(self, inputTable, queryMeta)
		res = SvcResult(coreRes, inputTable, queryMeta, self)
		return res

	def run(self, renderer, args, queryMeta=None):
		"""runs the service, returning an SvcResult.

		This is the main entry point for protocol renderers; args is
		a dict of lists as provided by request.args.

		Pass in queryMeta if convenient or if args is not simply request.args
		(but, e.g., nevow formal data).  Otherwise, it will be constructed
		from args.
		"""
		if queryMeta is None:
			queryMeta = common.QueryMeta.fromNevowArgs(args)

		core = self.getCoreFor(renderer)

		return self._runWithInputTable(core,
			self._makeInputTableFor(core, args),
			queryMeta)


	#################### meta and such

	def _meta_available(self):
# XXX TODO: have this ask the core
		return "true"

	def macro_tablesForTAP(self):
		# this is only used by tap.rd -- maybe it
		# should go there?
		from gavo.protocols import tap
		
		schemas = {}
		for qname in tap.getAccessibleTables():
			try:
				schema, name = qname.split(".")
			except: # weird name
				continue
			schemas.setdefault(schema, []).append(name)

		return ", ".join("%s from the %s schema"%(", ".join(tables), schema)
			for schema, tables in schemas.iteritems())
