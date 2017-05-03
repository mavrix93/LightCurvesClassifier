"""
Renderers and helpers for asynchronous services.

For TAP (which was the first prototype of these), there's a separate
module using some of this; on the long run, it should probably be
integrated here.
"""

from nevow import inevow
from nevow import rend
from twisted.internet import threads

from gavo import base
from gavo import svcs
from gavo import utils
from gavo.protocols import uws
from gavo.protocols import uwsactions


class UWSRedirect(rend.Page):
	"""a redirection for UWS (i.e., 303).

	The DC-global redirects use a 302 status, munge redirection URLs, and 
	we don't want any HTML payload here anyway.

	The locations used here are relative to baseURL, which essentially
	has to be the the full absolute URL of the endpoint (i.e., 
	service/renderer).  As a special service, for TAP async is being
	added as long as the renderer isn't fixed to not do dispatching.
	"""
	def __init__(self, baseURL, location):
		# TODO: Temporary hack as long as TAP isn't modernized to use
		# an async renderer: fix the redirect to TAP's async endpoint if
		# baseURL is the TAP renderer:
		if baseURL.endswith("tap"):
			baseURL = baseURL+"/async"

		if location:
			self.location = str(
				"%s/%s"%(baseURL, location))
		else:
			self.location = str(baseURL)

	def renderHTTP(self, ctx):
		req = inevow.IRequest(ctx)
		req.code = 303
		req.setHeader("location", self.location)
		req.setHeader("content-type", "text/plain")
		req.write("Go here: %s\n"%self.location)
		return ""


class MethodAwareResource(rend.Page):
	"""is a rend.Page with behaviour depending on the HTTP method.
	"""
	def __init__(self, workerSystem, renderer, service):
		self.workerSystem, self.service = workerSystem, service
		self.renderer = renderer
		rend.Page.__init__(self)

	def _doBADMETHOD(self, ctx, request):
		raise svcs.BadMethod(request.method)

	def renderHTTP(self, ctx):
		request = inevow.IRequest(ctx)
		# TODO: check if these can block -- and at least think really hard
		# if they can all be made non-blocking sanely.
		handlingMethod = getattr(self, "_do"+request.method, self._doBADMETHOD)
		return threads.deferToThread(handlingMethod, ctx, request
			).addCallback(self._deliverResult, request
			).addErrback(self._deliverError, request)


class UWSErrorMixin(object):
	def _deliverError(self, failure, request):
		if not isinstance(failure.value, uws.JobNotFound):
			base.ui.notifyFailure(failure)
		request.setHeader("content-type", "text/xml")
		return uwsactions.ErrorResource(failure.value)


class JoblistResource(MethodAwareResource, UWSErrorMixin):
	"""The web resource corresponding to async root.

	GET yields a job list, POST creates a job.
	"""
	def _doGET(self, ctx, request):
		res = uwsactions.getJobList(self.workerSystem)
		return res
	
	def _doPOST(self, ctx, request):
		jobId = self.workerSystem.getNewIdFromRequest(request, self.service)
		return UWSRedirect(self.service.getURL(
			self.renderer), str(jobId))

	def _deliverResult(self, res, request):
		request.setHeader("content-type", "text/xml")
		return res


class JobResource(rend.Page, UWSErrorMixin):
	"""The web resource corresponding to async requests for jobs.
	"""
	def __init__(self, workerSystem, renderer, service, segments):
		self.service, self.segments = service, segments
		self.workerSystem, self.renderer = workerSystem, renderer

	def renderHTTP(self, ctx):
		request = inevow.IRequest(ctx)
		return threads.deferToThread(
			uwsactions.doJobAction, self.workerSystem, request, self.segments
		).addCallback(self._deliverResult, request
		).addErrback(self._redirectAsNecessary, ctx
		).addErrback(self._deliverError, request)

	def _redirectAsNecessary(self, failure, ctx):
		failure.trap(svcs.WebRedirect)
		return UWSRedirect(self.service.getURL(self.renderer),
			failure.value.rawDest)

	def _deliverResult(self, result, request):
		if hasattr(result, "renderHTTP"):  # it's a finished resource
			return result
		# content-type is set by uwsaction._JobActions.dispatch
		request.write(utils.xmlrender(result).encode("utf-8"))
		return ""
	

def getAsyncResource(ctx, workerSystem, renderer, service, segments):
	if segments:
		return JobResource(workerSystem, renderer, service, segments)
	else:
		return JoblistResource(workerSystem, renderer, service)
