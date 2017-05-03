"""
Basic Code for Renderers.

Renderers are frontends for services.  They provide the glue to
somehow acquire input (typically, nevow contexts) and then format
the result for the user.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import os

from nevow import tags as T
from nevow import loaders
from nevow import inevow
from nevow import rend
from nevow import url

from twisted.internet import threads
from twisted.python import log
from zope.interface import implements

from gavo import base
from gavo import svcs
from gavo.protocols import creds
from gavo.web import common
from gavo.web import htmltable


__docformat__ = "restructuredtext en"


class RDBlocked(Exception):
	"""is raised when a ResourceDescriptor is blocked due to maintanence
	and caught by the root resource..
	"""


########## Useful mixins for Renderers

class GavoRenderMixin(common.CommonRenderers, base.MetaMixin):
	"""A mixin with renderers useful throughout the data center.

	Rendering of meta information:

	* <tag n:render="meta">METAKEY</tag> or
	* <tag n:render="metahtml">METAKEY</tag>

	Rendering the sidebar --
	<body n:render="withsidebar">.  This will only work if the renderer
	has a service attribute that's enough of a service (i.e., carries meta
	and knows how to generate URLs).

	Conditional rendering:

	* ifmeta
	* imownmeta
	* ifdata
	* ifnodata
	* ifslot
	* ifnoslot
	* ifadmin

	Obtaining system info

	* rd <rdId> -- makes the referenced RD the current data (this is
	  not too useful right now, but it lets you check of the existence
	  of RDs already)
	"""
	_sidebar = svcs.loadSystemTemplate("sidebar.html")

	# macro package to use when expanding macros.  Just set this
	# in the constructor as necessary (ServiceBasedRenderer has the
	# service here)
	macroPackage = None

	def _initGavoRender(self):
		# call this to initialize this mixin.
		base.MetaMixin.__init__(self)

	def _doRenderMeta(self, ctx, raiseOnFail=False, plain=False, 
			carrier=None):
		if carrier is None:
			carrier = self

		metaKey = "(inaccessible)"
		try:
			metaKey = ctx.tag.children[0].strip()
			htmlBuilder = common.HTMLMetaBuilder(self.macroPackage)

			if plain:
				ctx.tag.clear()
				return ctx.tag[base.getMetaText(carrier, metaKey, raiseOnFail=True,
					macroPackage=self.macroPackage)]

			else:
				ctx.tag.clear()
				return ctx.tag[T.xml(carrier.buildRepr(metaKey, htmlBuilder,
					raiseOnFail=True))]

		except base.NoMetaKey:
			if raiseOnFail:
				raise
			return T.comment["Meta item %s not given."%metaKey]
		except Exception, ex:
			msg = "Meta %s bad (%s)"%(metaKey, str(ex))
			base.ui.notifyError(msg)
			return T.comment[msg]

	def data_meta(self, metaKey):
		"""returns the value for the meta key metaName on this service.
		"""
		def get(ctx, data):
			return self.getMeta(metaKey)
		return get
	
	def render_meta(self, ctx, data):
		"""replaces a meta key with a plain text rendering of the metadata
		in the service.
		"""
		return self._doRenderMeta(ctx, plain=True)
	
	def render_metahtml(self, ctx, data):
		"""replaces a meta key with an html rendering of the metadata in
		the serivce.
		"""
		return self._doRenderMeta(ctx)

	def render_datameta(self, ctx, data):
		"""replaces the meta key in the contents with the corresponding
		meta key's HTML rendering.
		"""
		return self._doRenderMeta(ctx, carrier=data)
	
	def render_ifmeta(self, metaName, propagate=True):
		"""renders its children if there is metadata for metaName.
		"""
		# accept direct parent as "own" meta as well.
		if propagate:
			hasMeta = self.getMeta(metaName) is not None
		else:
			hasMeta = (self.getMeta(metaName, propagate=False) is not None
				or self.getMetaParent().getMeta(metaName, propagate=False) is not None)
		if hasMeta:
			return lambda ctx, data: ctx.tag
		else:
			return lambda ctx, data: ""

	def render_ifownmeta(self, metaName):
		"""renders its children if there is metadata for metaName in
		the service itself.
		"""
		return self.render_ifmeta(metaName, propagate=False)
	
	def render_ifdata(self, ctx, data):
		if data:
			return ctx.tag
		else:
			return ""

	def render_ifnodata(self, ctx, data):
		if not data:
			return ctx.tag
		else:
			return ""

	def render_ifslot(self, slotName):
		"""renders the children for slotName is present and true.

		This will not work properly if the slot values come from a deferred.
		"""
		def render(ctx, data):
			try:
				if ctx.locateSlotData(slotName):
					return ctx.tag
				else:
					return ""
			except KeyError:
				return ""
		return render

	def render_ifnoslot(self, slotName):
		"""renders if slotName is missing or not true.

		This will not work properly if the slot values come from a deferred.
		"""
		# just repeat the code from ifslot -- this is called frequently,
		# and additional logic just is not worth it.
		def render(ctx, data):
			try:
				if not ctx.locateSlotData(slotName):
					return ctx.tag
				else:
					return ""
			except KeyError:
				return ""
		return render

	def render_ifadmin(self, ctx, data):
		# NOTE: use of this renderer is *not* enough to protect critical operations
		# since it does not check if the credentials are actually provided.
		# Use this only hide links that will give 403s (or somesuch) for
		# non-admins anyway (and the like).
		if inevow.IRequest(ctx).getUser()=="gavoadmin":
			return ctx.tag
		else:
			return ""

	def render_explodableMeta(self, ctx, data):
		metaKey = ctx.tag.children[0]
		title = ctx.tag.attributes.get("title", metaKey.capitalize())
		try:
			return T.div(class_="explodable")[
				T.h4(class_="exploHead")[
					T.a(onclick="toggleCollapsedMeta(this)", 
						class_="foldbutton")[title+" >>"],
				],
				T.div(class_="exploBody")[
					self._doRenderMeta(ctx, raiseOnFail=True)]]
		except base.MetaError:
			return ""

	def render_intro(self, ctx, data):
		"""returns something suitable for inclusion above the form.

		The renderer tries, in sequence, to retrieve a meta called _intro,
		the description meta, or nothing.
		"""
		for key in ["_intro", "description"]:
			if self.service.getMeta(key, default=None) is not None:
				introKey = key
				break
		else:
			introKey = None
		if introKey is None:
			return ctx.tag[""]
		else:
			return ctx.tag[T.xml(self.buildRepr(introKey, 
				common.HTMLMetaBuilder(self.macroPackage),
				raiseOnFail=False))]

	def render_authinfo(self, ctx, data):
		request = inevow.IRequest(ctx)
		svc = getattr(self, "service", None)

		if svc and request.getUser():
			anchorText = "Log out %s"%request.getUser()
			targetURL = svc.getURL("logout", False)
			explanation = " (give an empty user name in the dialog popping up)"
		else:
			targetURL = url.URL.fromString("/login").add("nextURL", 
				str(url.URL.fromContext(ctx)))
			anchorText = "Log in"
			explanation = ""

		return ctx.tag[T.a(href=str(targetURL))[
			anchorText], explanation]

	def render_prependsite(self, ctx, data):
		"""prepends a site id to the body.

		This is intended for titles and similar; it puts the string in
		[web]sitename in front of anything that already is in ctx.tag.
		"""
		ctx.tag.children = [base.getConfig("web", "sitename")]+ctx.tag.children
		return ctx.tag
		
	def render_withsidebar(self, ctx, data):
		oldChildren = ctx.tag.children
		ctx.tag.children = []
		return ctx.tag(class_="container")[
			self._sidebar,
			T.div(id="body")[
				T.a(name="body"),
				oldChildren
			],
		]

	def data_rd(self, rdId):
		"""returns the RD referenced in the body (or None if the RD is not there)
		"""
		try:
			return base.caches.getRD(rdId)
		except base.NotFoundError:
			return None


class HTMLResultRenderMixin(object):
	"""is a mixin with render functions for HTML tables and associated 
	metadata within other pages.

	This is primarily used for the Form renderer.
	"""
	result = None

	def render_resulttable(self, ctx, data):
		if hasattr(data, "child"):
			return htmltable.HTMLTableFragment(data.child(ctx, "table"), 
				data.queryMeta)
		else:
			# a FormError, most likely
			return ""

	def render_resultline(self, ctx, data):
		if hasattr(data, "child"):
			return htmltable.HTMLKeyValueFragment(data.child(ctx, "table"), 
				data.queryMeta)
		else:
			# a FormError, most likely
			return ""

	def render_parpair(self, ctx, data):
		if data is None or data[1] is None or "__" in data[0]:
			return ""
		return ctx.tag["%s: %s"%data]

	def render_ifresult(self, ctx, data):
		if self.result.queryMeta.get("Matched", 1)!=0:
			return ctx.tag
		else:
			return ""
	
	def render_ifnoresult(self, ctx, data):
		if self.result.queryMeta.get("Matched", 1)==0:
			return ctx.tag
		else:
			return ""

	def render_servicestyle(self, ctx, data):
		"""enters custom service styles into ctx.tag.

		They are taken from the service's customCSS property.
		"""
		if self.service and self.service.getProperty("customCSS", False):
			return ctx.tag[self.service.getProperty("customCSS")]
		return ""

	def data_result(self, ctx, data):
		return self.result

	def _makeParPair(self, key, value, fieldDict):
		title = key
		if key in fieldDict:
			title = fieldDict[key].getLabel()
			if fieldDict[key].type=="file":
				value = "File upload '%s'"%value[0]
			else:
				value = unicode(value)
		return title, value

	__suppressedParNames = set(["submit"])

	def data_queryseq(self, ctx, data):
		if not self.result:
			return []

		if self.service:
			fieldDict = dict((f.name, f) 
				for f in self.service.getInputKeysFor(self))
		else:
			fieldDict = {}
	
		s = [self._makeParPair(k, v, fieldDict) 
			for k, v in self.result.queryMeta.getQueryPars().iteritems()
			if k not in self.__suppressedParNames and not k.startswith("_")]
		s.sort()
		return s

	def render_flotplot(self, ctx, data):
		"""adds an onClick attribute opening a flot plot.

		This is evaluates the _plotOptions meta.  This should be a javascript
		dictionary literal with certain plot options.  More on this in
		the reference documentation on the _plotOptions meta.
		"""
		plotOptions = base.getMetaText(self.service, "_plotOptions")
		if plotOptions is not None:
			args = ", %s"%plotOptions
		else:
			args = ""
		return ctx.tag(onclick="openFlotPlot($('table.results')%s)"%args)

	def render_param(self, format):
		"""returns the value of the data.getParam(content) formatted as a python
		string.

		Undefined params and NULLs give N/A.
		"""
		def renderer(ctx, data):
			parName = ctx.tag.children[0].strip()
			ctx.tag.clear()
			try:
				val = data.getParam(parName)
				if val is None:
					return ctx.tag["N/A"]

				return ctx.tag[format%val]
			except base.NotFoundError:
				return ctx.tag["N/A"]
		return renderer



class CustomTemplateMixin(object):
	"""is a mixin providing for customized templates.

	This works by making docFactory a property first checking if
	the instance has a customTemplate attribute evaluating to true.
	If it has and it is referring to a string, its content is used
	as an absolute path to a nevow XML template.  If it has and
	it is not a string, it will be used as a template directly
	(it's already "loaded"), else defaultDocFactory attribute of
	the instance is used.
	"""
	customTemplate = None

	def getDocFactory(self):
		if not self.customTemplate:
			return self.defaultDocFactory
		elif isinstance(self.customTemplate, basestring):
			if not os.path.exists(self.customTemplate):
				return self.defaultDocFactory
			return loaders.xmlfile(self.customTemplate)
		else:
			return self.customTemplate
	
	docFactory = property(getDocFactory)



############# nevow Resource derivatives used here.


class GavoPage(rend.Page, GavoRenderMixin):
	"""a base class for all "pages" (i.e. things talking to the web) within
	DaCHS.
	"""


class ResourceBasedPage(GavoPage):
	"""A base for renderers based on RDs.

	It is constructed with the resource descriptor and leaves it
	in the rd attribute.

	The preferredMethod attribute is used for generation of registry records
	and currently should be either GET or POST.  urlUse should be one
	of full, base, post, or dir, in accord with VOResource.

	Renderers with fixed result types should fill out resultType.

	The makeAccessURL class method is called by service.getURL; it
	receives the service's base URL and must return a mogrified string
	that corresponds to an endpoint this renderer will operate on (this
	could be used to make a Form renderer into a ParamHTTP interface by
	attaching ?__nevow_form__=genForm&, and the soap renderer does
	nontrivial things there).

	Within DaCHS, this class is mainly used as a base for ServiceBasedRenderer,
	since almost always only services talk to the world.  However,
	we try to fudge render and data functions such that the sidebar works.
	"""
	implements(inevow.IResource)

	preferredMethod = "GET"
	urlUse = "full"
	resultType = None
	# parameterStyle is a hint for inputKeys how to transform themselves
	# "clear" keeps types, "form" gives vizier-like expressions
	# "vo" gives parameter-like expressions.
	parameterStyle = "clear"
	name = None

	def __init__(self, ctx, rd):
		rend.Page.__init__(self)
		self.rd = rd
		self.setMetaParent(rd)
		self.macroPackage = rd
		if hasattr(self.rd, "currently_blocked"):
			raise RDBlocked()
		self._initGavoRender()

	@classmethod
	def isBrowseable(self, service):
		"""returns True if this renderer applied to service is usable using a
		plain web browser.
		"""
		return False

	@classmethod
	def isCacheable(self, segments, request):
		"""should return true if the content rendered will only change
		when the associated RD changes.

		request is a nevow request object.  web.root.ArchiveService already
		makes sure that you only see GET request without arguments and
		without a user, so you do not need to check this.
		"""
		return False

	@classmethod
	def makeAccessURL(cls, baseURL):
		"""returns an accessURL for a service with baseURL to this renderer.
		"""
		return "%s/%s"%(baseURL, cls.name)

	def data_rdId(self, ctx, data):
		return self.rd.sourceId

	def data_serviceURL(self, type):
		# for RD's that's simply the rdinfo.
		return lambda ctx, data: base.makeSitePath("/browse/%s"%self.rd.sourceId)


_IGNORED_KEYS = set(["__nevow_form__", "_charset_", "submit", "nextURL"])

def _formatRequestArgs(args):
	r"""formats nevow request args for logging.

	Basically, long objects (ones with len, and len>100) are truncated.

	>>> _formatRequestArgs({"x": range(2), "y": [u"\u3020"], "submit": ["Ok"]})
	"{'x': [0,1,],'y': [u'\\u3020',],}"
	>>> _formatRequestArgs({"hokus": ["Pokus"*300]})
	"{'hokus': [<data starting with 'PokusPokusPokusPokusPokusPokus'>,],}"
	>>> _formatRequestArgs({"no": []})
	'{}'
	"""
	res = ["{"]
	for key in sorted(args):
		valList = args[key]
		if not valList or key in _IGNORED_KEYS:
			continue
		res.append("%s: ["%repr(key))
		for value in valList:
			try:
				if len(value)>100:
					res.append("<data starting with %s>,"%repr(value[:30]))
				else:
					res.append(repr(value)+",")
			except TypeError:  # no len on value
				res.append(repr(value)+",")
		res.append("],")
	res.append("}")
	return "".join(res)


class ServiceBasedPage(ResourceBasedPage):
	"""the base class for renderers turning service-based info into
	character streams.

	You will need to provide some way to give rend.Page nevow templates,
	either by supplying a docFactory or (usually preferably) mixing in
	CustomTemplateMixin -- or just override renderHTTP to make do
	without templates.

	The class overrides nevow's child and render methods to allow the
	service to define render_X and data_X methods, too.

	You can set an attribute checkedRenderer=False for renderers that
	are "generic" and do not need to be enumerated in the allowed
	attribute of the underlying service ("meta renderers").

	You can set a class attribute openRenderer=True to make a renderer
	work even on restricted services (which make sense for stuff like logout
	and maybe for metadata inspection).
	"""

	checkedRenderer = True
	openRenderer = False

	def __init__(self, ctx, service):
		ResourceBasedPage.__init__(self, ctx, service.rd)

		self.service = service
		request = inevow.IRequest(ctx)
		if not self.openRenderer and service.limitTo:
			if not creds.hasCredentials(request.getUser(), request.getPassword(),
					service.limitTo):
				raise svcs.Authenticate()

		if self.checkedRenderer and self.name not in self.service.allowed:
			raise svcs.ForbiddenURI(
				"The renderer %s is not allowed on this service."%self.name,
				rd=self.service.rd)
		self.setMetaParent(self.service)
		self.macroPackage = self.service

		# Set to true when we notice we need to fix the service's output fields
		self.fieldsChanged = False 

		self._logRequestArgs(request)
		self._fillServiceDefaults(request.args)

	def _logRequestArgs(self, request):
		"""leaves the actual arguments of a request in the log.
		"""
		try:
			if request.args:
				# even if there are args, don't log them if only boring ones
				# were given
				fmtArgs = _formatRequestArgs(request.args)
				if fmtArgs!='{}':
					log.msg("# Processing starts: %s %s"%(request.path, 
						fmtArgs))
		except: # don't fail because of logging problems
			base.ui.notifyError("Formatting of request args failed.")

	def _fillServiceDefaults(self, args):
		"""a hook to enter default parameters based on the service.
		"""
		if self.service.hasProperty("defaultSortKey"):
			if "_DBOPTIONS_ORDER" not in args:
				args["_DBOPTIONS_ORDER"] = self.service.getProperty(
					"defaultSortKey").split(",")

	def processData(self, rawData, queryMeta=None):
		"""calls the actual service.

		This will run in the current thread; you will ususally
		want to use runService from the main nevow event loop unless you know
		the service is quick or actually works asynchronously.
		"""
		return self.service.run(self, rawData, queryMeta)
	
	def runService(self, rawData, queryMeta=None):
		"""takes raw data and returns a deferred firing the service result.

		This will process everything in a thread.
		"""
		return threads.deferToThread(self.processData, rawData, queryMeta)

	def runServiceWithFormalData(self, rawData, context):
		"""runs 
		"""
		queryMeta = svcs.QueryMeta.fromContext(context)
		queryMeta["formal_data"] = rawData
		return self.runService(svcs.PreparsedInput(rawData), queryMeta)

	def data_serviceURL(self, renderer):
		"""returns a relative URL for this service using the renderer.

		This is ususally used like this:

		<a><n:attr name="href" n:data="serviceURL info" n:render="data">x</a>
		"""
		def get(ctx, data):
			return self.service.getURL(renderer, absolute="False")
		return get

	def renderer(self, ctx, name):
		"""returns a nevow render function named name.

		This overrides the method inherited from nevow's RenderFactory to
		add a lookup in the page's service service.
		"""
		if name in self.service.nevowRenderers:
			return self.service.nevowRenderers[name]
		return rend.Page.renderer(self, ctx, name)

	def child(self, ctx, name):
		"""returns a nevow data function named name.

		In addition to nevow's action, this also looks methods up in the
		service.
		"""
		if name in self.service.nevowDataFunctions:
			return self.service.nevowDataFunctions[name]
		return rend.Page.child(self, ctx, name)

	def renderHTTP(self, ctx):
		return rend.Page.renderHTTP(self, ctx)

	def locateChild(self, ctx, segments):
		# By default, ServiceBasedPages have no directory-like resources.
		# So, if some overzealous entity added a slash, just redirect.
		# Do not upcall to this if you override locateChild.
		if segments==("",):
			raise svcs.WebRedirect(url.URL.fromContext(ctx))
		else:
			return ResourceBasedPage.locateChild(self, ctx, segments)

if __name__=="__main__":
	import doctest, grend
	doctest.testmod(grend)
