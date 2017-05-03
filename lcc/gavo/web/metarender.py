"""
Renderers that take services "as arguments".
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import cgi
import urllib

from nevow import inevow
from nevow import loaders
from nevow import rend
from nevow import tags as T, entities as E
from nevow import url

from gavo import base
from gavo import registry
from gavo import rsc
from gavo import svcs
from gavo import utils
from gavo.protocols import creds
from gavo.web import common
from gavo.web import grend


class MetaRenderer(grend.CustomTemplateMixin, grend.ServiceBasedPage):
	"""Renderers that are allowed on all services.
	"""
	checkedRenderer = False

	@classmethod
	def isCacheable(self, segments, request):
		return True

	def data_otherServices(self, ctx, data):
		"""returns a list of dicts describing other services provided by the
		the describing RD.

		The class mixing this in needs to provide a describingRD attribute for
		this to work.  This may be the same as self.service.rd, and the
		current service will be excluded from the list in this case.
		"""
		res = []
		for svc in self.describingRD.services:
			if svc is not self.service:
				res.append({"infoURL": svc.getURL("info"),
					"title": base.getMetaText(svc, "title")})
		return res

	def render_sortOrder(self, ctx, data):
		request = inevow.IRequest(ctx)
		if "alphaOrder" in request.args:
			return ctx.tag["Sorted alphabetically. ",
				T.a(href=url.URL.fromRequest(request).remove("alphaOrder"))[
					"[Sort by DB column index]"]]
		else:
			return ctx.tag["Sorted by DB column index. ",
				T.a(href=url.URL.fromRequest(request).add("alphaOrder", "True"))[
					"[Sort alphabetically]"]]

	def render_rdInfoLink(self, ctx, data):
		# a link to the info to data's RD (i.e., data needs an rd attribute).
		return ctx.tag(href="/browse/"+data.rd.sourceId)[
			RDInfoPage.makePageTitle(data.rd)]

	def render_ifkey(self, keyName):
		def render(ctx, data):
			if data.has_key(keyName):
				return ctx.tag
			return ""
		return render


class RendExplainer(object):
	"""is a container for various functions having to do with explaining
	renderers on services.

	Use the explain(renderer, service) class method.
	"""

	@classmethod
	def _explain_form(cls, service):
		return T.invisible["allows access via an ",
			T.a(href=service.getURL("form"))["HTML form"]]

	@classmethod
	def _explain_fixed(cls, service):
		return T.invisible["a ",
			T.a(href=service.getURL("fixed"))["custom page"],
			", possibly with dynamic content"]
	
	@classmethod
	def _explain_soap(cls, service):

		def generateArguments():
			# Slightly obfuscated -- I need to get ", " in between the items.
			fieldIter = iter(service.getInputKeysFor("soap"))
			try:
				next = fieldIter.next()
				while True:
					desc = "%s/%s"%(next.name, next.type)
					if next.required:
						desc = T.strong[desc]
					yield desc
					next = fieldIter.next()
					yield ', '
			except StopIteration:
				pass

		return T.invisible["enables remote procedure calls; to use it,"
			" feed the WSDL URL "+
			service.getURL("soap")+"/go?wsdl"+
			" to your SOAP library; the function signature is"
			"  useService(",
			generateArguments(),
			").  See also our ", 
			T.a(render=T.directive("rootlink"), href="/static/doc/soaplocal.shtml")[
				"local soap hints"]]

	@classmethod
	def _explain_custom(cls, service):
		res = T.invisible["a custom rendering of the service, typically"
			" for interactive web applications."]
		if svcs.getRenderer("custom").isBrowseable(service):
			res["  See also the ", 
				T.a(href=service.getURL("custom"))["entry page"], "."]
		return res
	
	@classmethod
	def _explain_static(cls, service):
		return T.invisible["static (i.e. prepared) data or custom client-side"
			" code; probably used to access ancillary files here"]


	@classmethod
	def _explain_text(cls, service):
		return T.invisible["a text interface not intended for user"
			" applications"]

	@classmethod
	def _explain_siap_xml(cls, service):
		return T.invisible["a standard SIAP interface as defined by the"
			" IVOA to access collections of celestial images; SIAP clients"
			" use ", service.getURL("siap.xml"), " to access the service",
			T.invisible(render=T.directive("ifadmin"))[" -- ",
				T.a(href="http://nvo.ncsa.uiuc.edu/dalvalidate/SIAValidater?endpoint="+
					urllib.quote(service.getURL("siap.xml"))+
					"&RA=%s&DEC=%s&RASIZE=%s&DECSIZE=%s&FORMAT=ALL&"
					"format=html&show=fail&show=warn&show=rec&op=Validate"%(
						base.getMetaText(service, "testQuery.pos.ra", default="180"),
						base.getMetaText(service, "testQuery.pos.dec", default="60"),
						base.getMetaText(service, "testQuery.size.ra", default="3"),
						base.getMetaText(service, "testQuery.size.dec", default="3")))[
					"Validate"]]]

	@classmethod
	def _explain_scs_xml(cls, service):
		return T.invisible["a standard SCS interface as defined by the"
			" IVOA to access catalog-type data; SCS clients"
			" use ", service.getURL("scs.xml"), " to access the service",
			T.invisible(render=T.directive("ifadmin"))[" -- ",
				T.a(href="http://nvo.ncsa.uiuc.edu/dalvalidate/"
					"ConeSearchValidater?endpoint="+
					urllib.quote(service.getURL("scs.xml"))+
					"&RA=%s&DEC=%s&SR=%s&format=html&show=fail&show=warn&show=rec"
					"&op=Validate"%(
						base.getMetaText(service, "testQuery.ra", default="180"),
						base.getMetaText(service, "testQuery.dec", default="60"),
						base.getMetaText(service, "testQuery.sr", default="1")))[
					"Validate"]]]

	@classmethod
	def _explain_ssap_xml(cls, service):
		tqKeys = cgi.parse_qs(
			base.getMetaText(service, "ssap.testQuery", default=""))
		# validator php seems to insist on that key
		opts = ["batch=yes&"
			"service=http%3A%2F%2Fvoparis-validator.obspm.fr%2Fxml%2F111.xml%3F"]
		for standardKey, default in [
				("REQUEST", "queryData"), 
				("SIZE", ""),
				("POS", ""),
				("TIME", ""),
				("BAND", ""),
				("FORMAT", "ALL")]:
			opts.append("%s=%s"%(standardKey, 
				urllib.quote(tqKeys.pop(standardKey, [default])[0])))
		opts.append("addparams="+urllib.quote("\n".join(
			"%s=%s"%(k,urllib.quote(v[0])) for k,v in tqKeys.iteritems())))
		optStr = "&".join(opts)
		if optStr:
			optStr = optStr+"&"

		return T.invisible["a standard SSAP interface as defined by the"
			" IVOA to access spectral or time-series data; SSAP clients"
			" use ", service.getURL("ssap.xml"), " to access the service",
			T.invisible(render=T.directive("ifadmin"))[" -- ",
				T.a(href=
					"http://voparis-validator.obspm.fr/validator.php?"
					"spec=Simple+Spectral+Access+1.04&"
					"format=XHTML&%sserviceURL=%s"%(
						optStr,
						urllib.quote(service.getURL("ssap.xml"))))[
					"Validate"]]]

	@classmethod
	def _explain_tap(cls, service):
		return T.invisible["the interface to this site's Table Access Protocol"
			" service.  This protocol is best accessed using specialized clients"
			" or libraries. In such clients, you can find this service by its"
			" IVORN, ",
			T.code(render=T.directive("meta"))["identifier"], 
			", or access it by entering its base URL ",
			T.code[service.getURL("tap")],
			" directly.  Using an XSL-enabled web browser you can, in a pinch,"
			" also operate ",
			T.a(href=service.getURL("tap")+"/async")["the service"],
			" without a specialized client."]

	@classmethod
	def _explain_pubreg_xml(cls, service):
		return T.invisible["an interface for the OAI-PMH protocol, typically"
			" this site's publishing registry (but possibly some other"
			" registry-like thing). This endpoint is usually accessed"
			" by harvesters, but with an XML-enabled browser you can"
			" also try the access URL at ",
			T.a(href=service.getURL("pubreg.xml"))[service.getURL("pubreg.xml")],
			"."]

	@classmethod
	def _explain_qp(cls, service):
		return T.invisible["an interface that uses the last path element"
			" to query the column %s in the underlying table."%
			service.getProperty("queryField", "defunct")]

	@classmethod
	def _explain_upload(cls, service):
		return T.invisible["a ",
			T.a(href=service.getURL("upload"))["form-based interface"],
			" for uploading data"]

	@classmethod
	def _explain_mupload(cls, service):
		return T.invisible["an upload interface for use with custom"
			" upload programs.  These should access ",
			service.getURL("mupload")]
	
	@classmethod
	def _explain_img_jpeg(cls, service):
		return T.invisible["a ",
			T.a(href=service.getURL("img.jpeg"))["form-based interface"],
			" to generate jpeg images from the underlying data"]

	@classmethod
	def _explain_mimg_jpeg(cls, service):
		return T.invisible["an interface to image creation targeted at machines."
			"  The interface is at %s."%service.getURL("img.jpeg"),
			"  This is probably irrelevant to you."]

	@classmethod
	def _explain_dlget(cls, service):
		return T.invisible["a datalink interface letting specialized clients"
			" retrieve parts of datasets or discover related data.  You"
			" use this kind of service exclusively in combination with"
			" a pubdid, usually via a direct link."]

	@classmethod
	def _explain_dlmeta(cls, service):
		return T.invisible["a datalink interface for discovering access"
			" options (processed data, related datasets...) for a dataset."
			" You usually need a publisherDID to use this kind of service."
			" For special applications, the base URL of this service might"
			" still come handy: %s"%service.getURL("dlmeta")]

	@classmethod
	def _explain_dlasync(cls, service):
		return T.invisible["an asynchronous interface to retrieving"
			" processed data.  This needs a special client that presumably"
			" would first look at the dlmeta endpoint to discover what"
			" processing options are available."]

	@classmethod
	def _explain_api(cls, service):
		return T.invisible["an interface for operation with curl and"
			" similar low-level-tools.  The endpoint is at ",
			T.a(href=service.getURL("api"))[service.getURL("api")],
			"; as usual for DALI-conforming services, parameters"
			" an response structure is available by ",
			T.a(href=service.getURL("api")+"MAXREC=0")["querying with"
				" MAXREC=0"],
			"."]
			
	@classmethod
	def _explainEverything(cls, service):
		return T.invisible["a renderer with some custom access method that"
			" should be mentioned in the service description"]

	@classmethod
	def explain(cls, renderer, service):
		return getattr(cls, "_explain_"+renderer.replace(".", "_"), 
			cls._explainEverything)(service)


class ServiceInfoRenderer(MetaRenderer, utils.IdManagerMixin):
	"""A renderer showing all kinds of metadata on a service.

	This renderer produces the default referenceURL page.  To change its
	appearance, override the serviceinfo.html template.
	"""
	name = "info"
	
	customTemplate = svcs.loadSystemTemplate("serviceinfo.html")

	def __init__(self, *args, **kwargs):
		grend.ServiceBasedPage.__init__(self, *args, **kwargs)
		self.describingRD = self.service.rd
		self.footnotes = set()

	def render_title(self, ctx, data):
		return ctx.tag["Information on Service '%s'"%
			base.getMetaText(self.service, "title")]

	def render_notebubble(self, ctx, data):
		if not data["note"]:
			return ""
		id = data["note"].tag
		self.footnotes.add(data["note"])
		return ctx.tag(href="#note-%s"%id)["Note %s"%id]

	def render_footnotes(self, ctx, data):
		"""renders the footnotes as a definition list.
		"""
		return T.dl(class_="footnotes")[[
				T.xml(note.getContent(targetFormat="html"))
			for note in sorted(self.footnotes, key=lambda n: n.tag)]]

	def data_internalpath(self, ctx, data):
		return "%s/%s"%(self.service.rd.sourceId, self.service.id)

	def data_inputFields(self, ctx, data):
		res = [f.asInfoDict() for f in self.service.getInputKeysFor("form")+
				self.service.serviceKeys]
		res.sort(key=lambda val: val["name"].lower())
		return res

	def data_htmlOutputFields(self, ctx, data):
		res = [f.asInfoDict() for f in self.service.getCurOutputFields()]
		res.sort(key=lambda val: val["name"].lower())
		return res

	def data_votableOutputFields(self, ctx, data):
		queryMeta = svcs.QueryMeta({"_FORMAT": "VOTable", "_VERB": 3})
		res = [f.asInfoDict() for f in self.service.getCurOutputFields(queryMeta)]
		res.sort(key=lambda val: val["verbLevel"])
		return res

	def data_rendAvail(self, ctx, data):
		return [{"rendName": rend, 
				"rendExpl": RendExplainer.explain(rend, self.service)}
			for rend in self.service.allowed]

	def data_publications(self, ctx, data):
		res = [{"sets": ",".join(p.sets), "render": p.render} 
			for p in self.service.publications if p.sets]
		return sorted(res, key=lambda v: v["render"])

	def data_browserURL(self, ctx, data):
		return self.service.getBrowserURL()

	def data_service(self, ctx, data):
		return self.service

	defaultDocFactory = common.doctypedStan(
		T.html[
			T.head[
				T.title["Missing Template"]],
			T.body[
				T.p["Infos are only available with a serviceinfo.html template"]]
		])


class TableInfoRenderer(MetaRenderer):
	"""A renderer for displaying table information.

	It really doesn't use the underlying service, but conventionally,
	it is run on __system__/dc_tables/show.
	"""
	name = "tableinfo"
	customTemplate = svcs.loadSystemTemplate("tableinfo.html")

	def renderHTTP(self, ctx):
		if not hasattr(self, "table"):  
			# _retrieveTableDef did not run, i.e., no tableName was given
			raise svcs.UnknownURI(
				"You must provide a table name to this renderer.")
		self.setMetaParent(self.table)
		return super(TableInfoRenderer, self).renderHTTP(ctx)

	def _retrieveTableDef(self, tableName):
		try:
			self.tableName = tableName
			self.table = registry.getTableDef(tableName)
			self.describingRD = self.table.rd
		except base.NotFoundError, msg:
			raise base.ui.logOldExc(svcs.UnknownURI(str(msg)))

	def data_forADQL(self, ctx, data):
		return self.table.adql

	def data_fields(self, ctx, data):
		res = [f.asInfoDict() for f in self.table]
		for d in res:
			if d["note"]:
				d["noteKey"] = d["note"].tag
		if "alphaOrder" in inevow.IRequest(ctx).args:
			res.sort(key=lambda item: item["name"].lower())
		return res

	def render_title(self, ctx, data):
		return ctx.tag["Table information for '%s'"%self.tableName]
	
	def render_rdmeta(self, ctx, data):
		# rdmeta: Meta info at the table's rd (since there's ownmeta)
		metaKey = ctx.tag.children[0]
		ctx.tag.clear()
		htmlBuilder = common.HTMLMetaBuilder(self.describingRD)
		try:
			return ctx.tag[T.xml(self.describingRD.buildRepr(metaKey, htmlBuilder))]
		except base.NoMetaKey:
			return ""

	def render_ifrdmeta(self, metaName):
		if self.describingRD.getMeta(metaName, propagate=False):
			return lambda ctx, data: ctx.tag
		else:
			return lambda ctx, data: ""

	def data_tableDef(self, ctx, data):
		return self.table

	def locateChild(self, ctx, segments):
		if len(segments)!=1:
			return None, ()
		self._retrieveTableDef(segments[0])
		return self, ()

	defaultDocFactory = common.doctypedStan(
		T.html[
			T.head[
				T.title["Missing Template"]],
			T.body[
				T.p["Infos are only available with a tableinfo.html template"]]
		])


class TableNoteRenderer(MetaRenderer):
	"""A renderer for displaying table notes.

	It takes a schema-qualified table name and a note tag in the segments.

	This does not use the underlying service, so it could and will run on
	any service.  However, you really should run it on __system__/dc_tables/show,
	and there's a built-in vanity name tablenote for this.
	"""
	name = "tablenote"

	def renderHTTP(self, ctx):
		if not hasattr(self, "noteTag"):  
			# _retrieveTableDef did not run, i.e., no tableName was given
			raise svcs.UnknownURI(
				"You must provide table name and note tag to this renderer.")
		return super(TableNoteRenderer, self).renderHTTP(ctx)

	def _retrieveNote(self, tableName, noteTag):
		try:
			table = registry.getTableDef(tableName)
			self.setMetaParent(table)
			self.noteHTML = table.getNote(noteTag
				).getContent(targetFormat="html", macroPackage=table)
		except base.NotFoundError, msg:
			raise base.ui.logOldExc(svcs.UnknownURI(msg))
		self.noteTag = noteTag
		self.tableName = tableName

	def locateChild(self, ctx, segments):
		if len(segments)==2:
			self._retrieveNote(segments[0], segments[1])
		elif len(segments)==3: # segments[0] may be anything, 
			# but conventionally "inner"
			self._retrieveNote(segments[1], segments[2])
			self.docFactory = self.innerDocFactory
		else:
			return None, ()
		return self, ()

	def data_tableName(self, ctx, data):
		return self.tableName
	
	def data_noteTag(self, ctx, data):
		return self.noteTag
	
	def render_noteHTML(self, ctx, data):
		return T.xml(self.noteHTML)

	docFactory = common.doctypedStan(T.html[
		T.head[
			T.title["%s -- Note for table "%base.getConfig("web", "sitename"),
				T.invisible(render=rend.data, data=T.directive("tableName"))],
			T.invisible(render=T.directive("commonhead")),
			T.style["span.target {font-size: 180%;font-weight:bold}"],
		],
		T.body[
			T.invisible(render=T.directive("noteHTML"))]])

	innerDocFactory = loaders.stan(
		T.invisible(render=T.directive("noteHTML")))


class ExternalRenderer(grend.ServiceBasedPage):
	"""A renderer redirecting to an external resource.

	These try to access an external publication on the parent service
	and ask it for an accessURL.  If it doesn't define one, this will
	lead to a redirect loop.

	In the DC, external renderers are mainly used for registration of
	third-party browser-based services.
	"""
	name = "external"

	@classmethod
	def isBrowseable(self, service):
		return True # we probably need some way to say when that's wrong...

	def renderHTTP(self, ctx):
		# look for a matching publication in the parent service...
		for pub in self.service.publications:
			if pub.render==self.name:
				break
		else: # no publication, 404
			raise svcs.UnknownURI()
		raise svcs.WebRedirect(base.getMetaText(pub, "accessURL",
			macroPackage=self.service))


class RDInfoPage(grend.CustomTemplateMixin, grend.ResourceBasedPage):
	"""A page giving infos about an RD.

	This is not a renderer but a helper for RDInfoRenderer.
	"""
	customTemplate = svcs.loadSystemTemplate("rdinfo.html")

	def data_services(self, ctx, data):
		return sorted(self.rd.services, 
			key=lambda s: base.getMetaText(s, "title", default=s.id))
	
	def data_tables(self, ctx, data):
		return sorted((t for t in self.rd.tables if t.onDisk and not t.temporary),
			key=lambda t: t.id)

	def data_clientRdId(self, ctx, data):
		return self.rd.sourceId

	def _getDescriptionHTML(self, descItem):
		"""returns stan for the "description" of a service or a table.

		The RD's description is not picked up.
		"""
		iDesc = descItem.getMeta("description", propagate=False)
		if iDesc is None:
			return ""
		else:
			return T.div(class_="lidescription")[
				T.xml(iDesc.getContent("blockhtml", macroPackage=descItem))]

	def render_rdsvc(self, ctx, service):
		return ctx.tag[
			T.a(href=service.getURL("info"))[
				base.getMetaText(service, "title", default=service.id)],
				self._getDescriptionHTML(service)]
			
	def render_rdtable(self, ctx, tableDef):
		qName = tableDef.getQName()

		adqlNote = ""
		if tableDef.adql:
			adqlNote = T.span(class_="adqlnote")[" ",
				E.ndash, " queriable through ",
				T.a(href="/tap")["TAP"], " and ", 
				T.a(href="/adql")["ADQL"],
				" "]

		return ctx.tag[
			T.a(href="/tableinfo/%s"%qName)[qName],
			adqlNote,
			self._getDescriptionHTML(tableDef)]

	@classmethod
	def makePageTitle(cls, rd):
		"""returns a suitable title for the rd info page.

		This is a class method to allow other renderers to generate
		titles for link anchors.
		"""
		return "Information on resource '%s'"%base.getMetaText(
			rd, "title", default="%s"%rd.sourceId)

	def render_title(self, ctx, data):
		return ctx.tag[self.makePageTitle(self.rd)]

	defaultDocFactory =  common.doctypedStan(
		T.html[
			T.head[
				T.title["Missing Template"]],
			T.body[
				T.p["RD infos are only available with an rdinfo.html template"]]
		])


class RDInfoRenderer(grend.CustomTemplateMixin, grend.ServiceBasedPage):
	"""A renderer for displaying various properties about a resource descriptor.
	
	This renderer could really be attached to any service since
	it does not call it, but it usually lives on //services/overview.

	By virtue of builtin vanity, you can reach the rdinfo renderer
	at /browse, and thus you can access /browse/foo/q to view the RD infos.
	This is the form used by table registrations.
	"""
	name = "rdinfo"
	customTemplate = svcs.loadSystemTemplate("rdlist.html")

	def data_publishedRDs(self, ctx, data):
		td = base.caches.getRD("//services").getById("resources")
		with base.getTableConn() as conn:
			table = rsc.TableForDef(td, connection=conn)
			try:
				return [row["sourceRD"] for row in
					table.iterQuery([td.getColumnByName("sourceRD")], "", 
					distinct=True, limits=("ORDER BY sourceRD", {}))]
			finally:
				table.close()

	def locateChild(self, ctx, segments):
		rdId = "/".join(segments)
		if not rdId:
			raise svcs.WebRedirect("browse")
		clientRD = base.caches.getRD(rdId)
		return RDInfoPage(ctx, clientRD), ()

	defaultDocFactory =  common.doctypedStan(
		T.html[
			T.head[
				T.title["Missing Template"]],
			T.body[
				T.p["The RD list is only available with an rdlist.html template"]]
		])


class LogoutRenderer(MetaRenderer):
	"""logs users out.

	With a valid authorization header, this emits a 401 unauthorized,
	without one, it displays a logout page.
	"""
	name = "logout"

	openRenderer = True

	def renderHTTP(self, ctx):
		request = inevow.IRequest(ctx)
		if creds.hasCredentials(
				request.getUser(), request.getPassword(), None):
			# valid credentials: Ask again to make the browser discard them
			raise svcs.Authenticate()
		else:
			return MetaRenderer.renderHTTP(self, ctx)

	defaultDocFactory =  common.doctypedStan(
		T.html[
			T.head[
				T.title["Logged out"]],
			T.body[
				T.h1["Logged out"],
				T.p["Your browser no longer has valid credentials for this site."
					"  Close this window or continue at the ",
					T.a(href=base.makeAbsoluteURL("/"))["root page"],
					"."]]])

	

class ResourceRecordMaker(rend.Page):
	"""A page that returns resource records for internal services.

	This is basically like OAI-PMH getRecord, except we're using rd/id/svcid
	from our path.
	"""
	def renderHTTP(self, ctx):
		raise svcs.UnknownURI("What resource record do you want?")

	def locateChild(self, ctx, segments):
		from gavo.registry import builders

		rdParts, svcId = segments[:-1], segments[-1]
		rdId = "/".join(rdParts)
		try:
			resob = base.caches.getRD(rdId).getById(svcId)
		except base.NotFoundError:
			raise svcs.UnknownURI("The resource %s#%s is unknown at this site."%(
				rdId, svcId))

		return common.TypedData(
			utils.xmlrender(builders.getVORMetadataElement(resob),
				prolog="<?xml version='1.0'?>"
					"<?xml-stylesheet href='/static/xsl/oai.xsl' type='text/xsl'?>",
				),
			"application/xml"), ()



