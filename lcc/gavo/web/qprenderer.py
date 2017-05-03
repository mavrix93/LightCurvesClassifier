"""
A renderer that queries a single field in a service.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from nevow import inevow
from nevow import rend
from nevow import tags as T
from twisted.internet import defer

from gavo import base
from gavo import svcs
from gavo.svcs import streaming
from gavo.web import common
from gavo.web import grend


class VOTableResource(rend.Page):
# A quick hack to support VOTable responses.
# Kill this in favour of serviceresults.
	def __init__(self, res):
		rend.Page.__init__(self)
		self.res = res
	
	def renderHTTP(self, ctx):
		request = inevow.IRequest(ctx)
		if self.res.queryMeta.get("Overflow"):
			fName = "truncated_votable.xml"
		else:
			fName = "votable.xml"
		request.setHeader("content-type", base.votableType)
		request.setHeader('content-disposition', 
			'attachment; filename=%s'%fName)
		return streaming.streamVOTable(request, self.res)


class QPRenderer(grend.HTMLResultRenderMixin, 
		grend.CustomTemplateMixin,
		grend.ServiceBasedPage):
	"""The Query Path renderer extracts a query argument from the query path.

	Basically, whatever segments are left after the path to the renderer
	are taken and fed into the service.  The service must cooperate by
	setting a queryField property which is the key the parameter is assigned
	to.

	QPRenderers cannot do forms, of course, but they can nicely share a
	service with the form renderer.

	To adjust the results' appreance, you can override resultline (for when
	there's just one result row) and resulttable (for when there is more
	than one result row) templates.
	"""
	name = "qp"
	queryValue = None

	@classmethod
	def isCacheable(self, segments, request):
		return False  # That's the default, but let's be sure here...

	def renderHTTP(self, ctx):
		if not self.queryValue:
			raise svcs.UnknownURI("This page is a root page for a"
				" query-based service.  You have to give a valid value in the"
				" path.")
		data = {self.service.getProperty("queryField"): self.queryValue}
		return self.runServiceWithFormalData(data, ctx
			).addCallback(self._formatOutput, ctx
			).addErrback(self._handleError, ctx)
	
	def _formatOutput(self, res, ctx):
# XXX TODO: We need a sensible common output framework, and quick.
# Then do away with the quick VOTable hack
		if res.queryMeta["format"]=="VOTable":
			return VOTableResource(res)
		nMatched = res.queryMeta.get("Matched", 0)
		if nMatched==0:
			raise svcs.UnknownURI("No record matching %s."%(
				self.queryValue))
		elif nMatched==1:
			self.customTemplate = self.getTemplate("resultline")
		else:
			self.customTemplate = self.getTemplate("resulttable")
		self.result = res
		return defer.maybeDeferred(super(QPRenderer, self).renderHTTP, ctx
			).addErrback(self._handleError, ctx)

	def _handleError(self, failure, ctx):
		# all errors are translated to 404s
		failure.printTraceback()
		raise svcs.UnknownURI("The query initiated by your URL failed,"
			" yielding a message '%s'."%failure.getErrorMessage())

	def locateChild(self, ctx, segments):
		# if we're here, we are the responsible resource and just stuff
		# the remaining segments into the query value
		self.queryValue = "/".join(segments)
		return self, ()

	def getTemplate(self, resultFormat):
		if resultFormat in self.service.templates:
			return self.service.getTemplate(resultFormat)
		return common.doctypedStan(
			T.html[
				T.head(render=T.directive("commonhead"))[
					T.title(render=T.directive("meta"))['title'],],
				T.body(render=T.directive("withsidebar"))[
					T.h1(render=T.directive("meta"))['title'],
					T.div(class_="result", data=T.directive("result")) [
						T.invisible(render=T.directive(resultFormat))]]])
