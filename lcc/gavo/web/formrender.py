"""
The form renderer is the standard renderer for web-facing services.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import types

from nevow import context
from nevow import flat
from nevow import inevow
from nevow import loaders
from nevow import rend
from nevow import tags as T
from twisted.internet import defer, reactor
from twisted.python.components import registerAdapter

from gavo import base
from gavo import svcs
from gavo.base import typesystems
from gavo.imp import formal
from gavo.imp.formal import iformal
from gavo.svcs import customwidgets
from gavo.svcs import streaming
from gavo.web import common
from gavo.web import grend
from gavo.web import serviceresults


def _getDeferredImmediate(deferred, 
		default="(non-ready deferreds not supported here)"):
	"""returns the value of deferred if it's already in, default otherwise.
	"""
	resultHolder = [default]

	def grabResult(res):
		resultHolder[0] = res

	# adding a callback to a ready deferred immediately calls the callback
	deferred.addCallback(grabResult)
	return resultHolder[0]


def _flattenStan(stan, ctx):
	"""helps streamStan.
	"""
# this is basically ripped from nevow's iterflatten
	rest = [iter([flat.partialflatten(ctx, stan)])]
	while rest:
		gen = rest.pop()
		for item in gen:
			if isinstance(item, str):
				yield item
			elif isinstance(item, unicode):
				yield item.encode("utf-8")
			else:
				# something iterable is coming up.  Suspend the current
				# generator and start iterating something else.
				rest.append(gen)
				if isinstance(item, (list, types.GeneratorType)):
					rest.append(iter(item))
				elif isinstance(item, defer.Deferred):
					# we actually cannot do deferreds that need to wait;
					# those shouldn't be necessary with forms.
					# Instead, grab the result immediately and go ahead with it.
					rest.append(iter(_getDeferredImmediate(item)))
				else:
					rest.append(flat.partialflatten(ctx, item))
				break


def iterStanChunked(stan, ctx, chunkSize):
	"""yields strings made from stan.

	This is basically like iterflatten, but it doesn't accumulate as much
	material in strings.  We need this here since stock nevow iterflatten
	will block the server thread of extended periods of time (say, several
	seconds) on large HTML tables.

	Note that deferreds are not really supported (i.e., if you pass in
	deferreds, they must already be ready).
	"""
	accu, curBytes = [], 0
	for chunk in _flattenStan(stan, ctx):
		accu.append(chunk)
		curBytes += len(chunk)
		if curBytes>chunkSize:
			yield "".join(accu)
			accu, curBytes = [], 0
	yield "".join(accu)
	

def streamStan(stan, ctx, destFile):
	"""writes strings made from stan to destFile.
	"""
	for chunk in iterStanChunked(stan, ctx, 50000):
		destFile.write(chunk)


def _iterWithReactor(iterable, finished, destFile):
	"""push out chunks coming out of iterable to destFile using a chain of
	deferreds.

	This is being done to yield to the reactor now and then.
	"""
	try:
		destFile.write(iterable.next())
	except StopIteration:
		finished.callback('')
	except:
 		finished.errback()
 	else:
	 	reactor.callLater(0, _iterWithReactor, iterable, finished, destFile)


def deliverYielding(stan, ctx, request):
	"""delivers rendered stan to request, letting the reactor schedule
	now and then.
	"""
	stanChunks = iterStanChunked(stan, ctx, 50000)
	finished = defer.Deferred()
	_iterWithReactor(stanChunks, finished, request)
	return finished


class ToFormalConverter(typesystems.FromSQLConverter):
	"""is a converter from SQL types to Formal type specifications.

	The result of the conversion is a tuple of formal type and widget factory.
	"""
	typeSystem = "Formal"
	simpleMap = {
		"smallint": (formal.Integer, formal.TextInput),
		"integer": (formal.Integer, formal.TextInput),
		"int": (formal.Integer, formal.TextInput),
		"bigint": (formal.Integer, formal.TextInput),
		"real": (formal.Float, formal.TextInput),
		"float": (formal.Float, formal.TextInput),
		"boolean": (formal.Boolean, formal.Checkbox),
		"double precision": (formal.Float, formal.TextInput),
		"double": (formal.Float, formal.TextInput),
		"text": (formal.String, formal.TextInput),
		"unicode": (formal.String, formal.TextInput),
		"char": (formal.String, formal.TextInput),
		"date": (formal.Date, formal.widgetFactory(formal.DatePartsInput,
			twoCharCutoffYear=50, dayFirst=True)),
		"time": (formal.Time, formal.TextInput),
		"timestamp": (formal.Date, formal.widgetFactory(formal.DatePartsInput,
			twoCharCutoffYear=50, dayFirst=True)),
		"vexpr-float": (formal.String, customwidgets.NumericExpressionField),
		"vexpr-date": (formal.String, customwidgets.DateExpressionField),
		"vexpr-string": (formal.String, customwidgets.StringExpressionField),
		"vexpr-mjd": (formal.String, customwidgets.DateExpressionField),
		"pql-string": (formal.String, formal.TextInput),
		"pql-int": (formal.String, formal.TextInput),
		"pql-float": (formal.String, formal.TextInput),
		"pql-date": (formal.String, formal.TextInput),
		"file": (formal.File, None),
		"raw": (formal.String, formal.TextInput),
	}

	def mapComplex(self, type, length):
		if type in self._charTypes:
			return formal.String, formal.TextInput

sqltypeToFormal = ToFormalConverter().convert


def _getFormalType(inputKey):
	return sqltypeToFormal(inputKey.type)[0](required=inputKey.required)


def _getWidgetFactory(inputKey):
	if not hasattr(inputKey, "_widgetFactoryCache"):
		widgetFactory = inputKey.widgetFactory
		if widgetFactory is None:
			if inputKey.isEnumerated():
				widgetFactory = customwidgets.EnumeratedWidget(inputKey)
			else:
				widgetFactory = sqltypeToFormal(inputKey.type)[1]
		if isinstance(widgetFactory, basestring):
			widgetFactory = customwidgets.makeWidgetFactory(widgetFactory)
		inputKey._widgetFactoryCache = widgetFactory
	return inputKey._widgetFactoryCache


def getFieldArgsForInputKey(inputKey):
	# infer whether to show a unit and if so, which
	unit = ""
	if inputKey.type!="date":  # Sigh.
		unit = inputKey.inputUnit or inputKey.unit or ""
		if unit:
			unit = " [%s]"%unit
	label = inputKey.getLabel()

	res = {
		"label": label,
		"name": inputKey.name,
		"type": _getFormalType(inputKey),
		"widgetFactory": _getWidgetFactory(inputKey),
		"label": label+unit,
		"description": inputKey.description,
		"cssClass": inputKey.getProperty("cssClass", None),}

	if inputKey.values and inputKey.values.default:
		res["default"] = unicode(inputKey.values.default)
	if inputKey.value:
		res["default"] = unicode(inputKey.value)
	if inputKey.hasProperty("defaultForForm"):
		res["default"] = inputKey.getProperty("defaultForForm")

	return res


class MultiField(formal.Group):
	"""A "widget" containing multiple InputKeys (i.e., formal Fields) in
	a single line.
	"""


class MultiFieldFragment(rend.Fragment):
	"""A fragment for rendering MultiFields.
	"""
	docFactory = loaders.stan(
		T.div(class_=T.slot("class"), render=T.directive("multifield"))[
			T.label(for_=T.slot('id'))[T.slot('label')],
			T.div(class_="multiinputs", id=T.slot('id'), 
				render=T.directive("childFields")),
			T.div(class_='description')[T.slot('description')],
			T.slot('message')])

	def __init__(self, multiField):
		rend.Fragment.__init__(self)
		self.multiField = multiField

	def render_childFields(self, ctx, data):
		formData = iformal.IFormData(ctx)
		formErrors = iformal.IFormErrors(ctx, None)

		for field in self.multiField.items:
			widget = field.makeWidget()
			if field.type.immutable:
				render = widget.renderImmutable
			else:
				render = widget.render
			cssClass = " ".join(s for s in (field.cssClass, "inmulti") if s) 
			ctx.tag[
				T.span(class_=cssClass)[
					render(ctx, field.key, formData, formErrors)(
						class_=cssClass, title=field.description or "")]]
		return ctx.tag

	def _getMessageElement(self, ctx):
		errors = []
		formErrors = iformal.IFormErrors(ctx, None)
		if formErrors is not None:
			for field in self.multiField.items:
				err = formErrors.getFieldError(field.key)
				if err is not None:
					errors.append(err.message)
		if errors:
			return T.div(class_='message')["; ".join(errors)]
		else:
			return ''

	def render_multifield(self, ctx, data):
		ctx.tag.fillSlots('description', self.multiField.description or "")
		ctx.tag.fillSlots('label', self.multiField.label or "")
		ctx.tag.fillSlots('id', "multigroup-"+self.multiField.key)
		errMsg = self._getMessageElement(ctx)
		ctx.tag.fillSlots('message', errMsg)
		if errMsg:
			ctx.tag.fillSlots('class', 'field error')
		else:
			ctx.tag.fillSlots('class', 'field')
		return ctx.tag


registerAdapter(MultiFieldFragment, MultiField, inevow.IRenderer)


class FormMixin(formal.ResourceMixin):
	"""A mixin to produce input forms for services and display
	errors within these forms.
	"""
	parameterStyle = "form"

	def _handleInputErrors(self, failure, ctx):
		"""goes as an errback to form handling code to allow correction form
		rendering at later stages than validation.
		"""
		if isinstance(failure.value, formal.FormError):
			self.form.errors.add(failure.value)
		elif isinstance(failure.value, base.ValidationError) and isinstance(
				failure.value.colName, basestring):
			try:
				# Find out the formal name of the failing field...
				failedField = failure.value.colName
				# ...and make sure it exists
				self.form.items.getItemByName(failedField)
				self.form.errors.add(formal.FieldValidationError(
					str(failure.getErrorMessage()), failedField))
			except KeyError: # Failing field cannot be determined
				self.form.errors.add(formal.FormError("Problem with input"
					" in the internal or generated field '%s': %s"%(
						failure.value.colName, failure.getErrorMessage())))
		else:
			return failure
		return self.form.errors

	def _addDefaults(self, ctx, form):
		"""adds defaults from request arguments.
		"""
		if ctx is None:  # no request context, no arguments
			return
		args = inevow.IRequest(ctx).args

		# do remainig work in function as this can be recursive
		def process(container):
			for item in container.items:
				if isinstance(item, formal.Group):
					process(item)
				else:
					try:
						form.data[item.key] = item.makeWidget().processInput(
							ctx, item.key, args, item.default)
					except:  # don't fail on junky things in default arguments
						pass

		process(form)
			
	def _addInputKey(self, form, container, inputKey):
		"""adds a form field for an inputKey to the form.
		"""
		container.addField(**getFieldArgsForInputKey(inputKey))

	def _groupQueryFields(self, inputTable):
		"""returns a list of "grouped" param names from inputTable.

		The idea here is that you can define "groups" in your input table.
		Each such group can contain paramRefs.  When the input table is rendered
		in HTML, the grouped fields are created in a formal group.  To make this
		happen, they may need to be resorted.  This happens in this function.

		The returned list contains strings (parameter names), groups (meaning
		"start a new group") and None (meaning end the current group).

		This is understood and used by _addQueryFields.
		"""
		groupedKeys = {}
		for group in inputTable.groups:
			for ref in group.paramRefs:
				groupedKeys[ref.key] = group

		inputKeySequence, addedNames = [], set()
		for inputKey in inputTable.params:
			thisName = inputKey.name

			if thisName in addedNames:
				# part of a group and added as such
				continue

			newGroup = groupedKeys.get(thisName)
			if newGroup is None:
				# not part of a group
				inputKeySequence.append(thisName)
				addedNames.add(thisName)
			else:
				# current key is part of a group: add it and all others in the group
				# enclosed in group/None.
				inputKeySequence.append(newGroup)
				for ref in groupedKeys[inputKey.name].paramRefs:
					inputKeySequence.append(ref.key)
					addedNames.add(ref.key)
				inputKeySequence.append(None)
		return inputKeySequence

	def _addQueryFieldsForInputTable(self, form, inputTable):
		"""generates input fields form the parameters of inputTable, taking
		into account grouping if necessary.
		"""
		containers = [form]
		for item in self._groupQueryFields(inputTable):
			if item is None:  # end of group
				containers.pop()

			elif isinstance(item, basestring):  # param reference
				self._addInputKey(form, containers[-1], 
					inputTable.params.getColumnByName(item))

			else: 
				# It's a new group -- if the group has a "style" property and
				# it's "compact", use a special container form formal.
				if item.getProperty("style", None)=="compact":
					groupClass = MultiField
				else:
					groupClass = formal.Group

				containers.append(
					form.add(groupClass(item.name, description=item.description,
						label=item.getProperty("label", None),
						cssClass=item.getProperty("cssClass", None))))

	def _addQueryFields(self, form):
		"""adds the inputFields of the service to form, setting proper defaults
		from the field or from data.
		"""
		if self.service.inputDD:
			# the service has a custom inputDD; all we have is the input keys.
			for item in self.service.getInputKeysFor(self):
				self._addInputKey(form, form, item)
		else:
			# we have an inputTable.  Handle groups and other fancy stuff
			self._addQueryFieldsForInputTable(form,
				self.service.getCoreFor(self).inputTable)

	def _addMetaFields(self, form, queryMeta):
		"""adds fields to choose output properties to form.
		"""
		try:
			if self.service.core.wantsTableWidget():
				form.addField("_DBOPTIONS", svcs.FormalDict,
					formal.widgetFactory(svcs.DBOptions, self.service, queryMeta),
					label="Table")
		except AttributeError: # probably no wantsTableWidget method on core
			pass

	def _getFormLinks(self):
		"""returns stan for widgets building GET-type strings for the current 
		form content.
		"""
		return T.div(class_="formLinks")[
				T.a(href="", class_="resultlink", onmouseover=
						"this.href=makeResultLink(getEnclosingForm(this))")
					["[Result link]"],
				" ",
				T.a(href="", class_="resultlink", onmouseover=
						"this.href=makeBookmarkLink(getEnclosingForm(this))")[
					T.img(src=base.makeSitePath("/static/img/bookmark.png"), 
						class_="silentlink", title="Link to this form", alt="[bookmark]")
				],
			]

	def form_genForm(self, ctx=None, data=None):
		queryMeta = svcs.QueryMeta.fromContext(ctx)
		form = formal.Form()
		self._addQueryFields(form)
		self._addMetaFields(form, queryMeta)
		self._addDefaults(ctx, form)

		if (self.name=="form" 
				and not hasattr(self.service.core, "HACK_RETURNS_DOC")):
			form.addField("_OUTPUT", formal.String, 
				formal.widgetFactory(serviceresults.OutputFormat, 
				self.service, queryMeta),
				label="Output format")

		form.addAction(self.submitAction, label="Go")
		form.actionMaterial = self._getFormLinks()
		self.form = form
		return form
	
	def _realSubmitAction(self, ctx, form, data):
		"""helps submitAction by doing the real work.

		It is here so we can add an error handler in submitAction.
		"""
		# TODO: There's significant overlap here with 
		# grend.runServiceWithFormalData; refactor?
		queryMeta = svcs.QueryMeta.fromContext(ctx)
		queryMeta["formal_data"] = data
		if (self.service.core.outputTable.columns and 
				not self.service.getCurOutputFields(queryMeta)):
			raise base.ValidationError("These output settings yield no"
				" output fields", "_OUTPUT")
		if queryMeta["format"]=="HTML":
			resultWriter = self
		else:
			resultWriter = serviceresults.getFormat(queryMeta["format"])
		if resultWriter.compute:
			d = self.runService(svcs.PreparsedInput(data), queryMeta)
		else:
			d = defer.succeed(None)
		return d.addCallback(resultWriter._formatOutput, ctx)

	def submitAction(self, ctx, form, data):
		"""executes the service.

		This is a callback for the formal form.
		"""
		return defer.maybeDeferred(self._realSubmitAction, ctx, form, data
			).addErrback(self._handleInputErrors, ctx)


class Form(FormMixin, 
		grend.CustomTemplateMixin,
		grend.HTMLResultRenderMixin, 
		grend.ServiceBasedPage):
	"""The "normal" renderer within DaCHS for web-facing services.

	It will display a form and allow outputs in various formats.

	It also does error reporting as long as that is possible within
	the form.
	"""
	name = "form"
	runOnEmptyInputs = False
	compute = True

	def __init__(self, ctx, service):
		grend.ServiceBasedPage.__init__(self, ctx, service)
		if "form" in self.service.templates:
			self.customTemplate = self.service.getTemplate("form")

		# enable special handling if I'm rendering fixed-behaviour services
		# (i.e., ones that never have inputs) XXX TODO: Figure out where I used this and fix that to use the fixed renderer (or whatever)
		if not self.service.getInputKeysFor(self):
			self.runOnEmptyInputs = True
		self.queryResult = None

	@classmethod
	def isBrowseable(self, service):
		return True

	@classmethod
	def isCacheable(self, segments, request):
		return segments==()

	def renderHTTP(self, ctx):
		if self.runOnEmptyInputs:
			inevow.IRequest(ctx).args[formal.FORMS_KEY] = ["genForm"]
		return FormMixin.renderHTTP(self, ctx)

	def _formatOutput(self, res, ctx):
		"""actually delivers the whole document.

		This is basically nevow's rend.Page._renderHTTP, changed to
		provide less blocks.
		"""
		request = inevow.IRequest(ctx)

		if isinstance(res.original, tuple):
			# core returned a complete document (mime and string)
			mime, payload = res.original
			request.setHeader("content-type", mime)
			request.setHeader('content-disposition', 
				'attachment; filename=result%s'%common.getExtForMime(mime))
			return streaming.streamOut(lambda f: f.write(payload), 
				request)

		self.result = res
		if "response" in self.service.templates:
			self.customTemplate = self.service.getTemplate("response")

		ctx = context.PageContext(parent=ctx, tag=self)
		self.rememberStuff(ctx)
		doc = self.docFactory.load(ctx)
		ctx =  context.WovenContext(ctx, T.invisible[doc])

		return deliverYielding(doc, ctx, request)

	defaultDocFactory = svcs.loadSystemTemplate("defaultresponse.html")


class DocFormRenderer(FormMixin, grend.ServiceBasedPage,
		grend.HTMLResultRenderMixin):
	"""A renderer displaying a form and delivering core's result as
	a document.
	
	The core must return a pair of mime-type and content; on errors,
	the form is redisplayed.

	This is mainly useful with custom cores doing weird things.  This
	renderer will not work with dbBasedCores and similar.
	"""
	name="docform"
	# I actually don't know the result type, since it's determined by the
	# core; I probably should have some way to let the core tell me what
	# it's going to return.
	resultType = "application/octet-stream"  
	compute = True

	@classmethod
	def isBrowseable(cls, service):
		return True

	def _formatOutput(self, data, ctx):
		request = inevow.IRequest(ctx)
		mime, payload = data.original
		request.setHeader("content-type", mime)
		request.write(payload)
		return ""

	docFactory = svcs.loadSystemTemplate("defaultresponse.html")
