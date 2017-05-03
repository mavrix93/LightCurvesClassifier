"""
Default error displays for the data center and error helper code.

Everything in here must render synchronuosly.

You probably should not construct anything in this module directly
but rather just raise the appropriate exceptions from svcs.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import urlparse

from nevow import inevow
from nevow import rend
from nevow import tags as T
from twisted.internet import defer
from twisted.python import failure
from twisted.python import log
from zope.interface import implements

from gavo import base
from gavo import svcs
from gavo import utils
from gavo.base import config
from gavo.web import common


class ErrorPage(rend.Page, common.CommonRenderers):
	"""A base for error handling pages.

	The idea is that you set the "handles" class attribute to 
	the exception you handle.  The exception has to match exactly, i.e.,
	no isinstancing is done.

	You also must set status to the HTTP status code the error should
	return.

	All error pages have a failure attribute that's a twisted failure
	with all the related mess (e.g., tracebacks).

	You have the status and message data methods.
	"""
	handles = None
	status = 500
	titleMessage = "Unspecified Error"

	_footer = [
		T.hr,
		T.address[T.a(href="mailto:%s"%config.getMeta(
				"contact.email").getContent())[
			config.getMeta("contact.email").getContent()]]]

	def __init__(self, error):
		self.failure = error

	def data_status(self, ctx, data):
		return str(self.status)

	def data_message(self, ctx, data):
		return self.failure.getErrorMessage()

	def render_message(self, ctx, data):
		return ctx.tag(class_="errmsg")[self.failure.getErrorMessage()]

	def render_hint(self, ctx, data):
		if (hasattr(self.failure.value, "hint"),
				self.failure.value.hint):
			return ctx.tag[T.strong["Hint: "], 
				self.failure.value.hint]
		return ""

	def render_rdlink(self, ctx, data):
		if hasattr(self.failure.value, "rd") and self.failure.value.rd:
			rdURL = base.makeAbsoluteURL("/browse/%s"%
				self.failure.value.rd.sourceId)
			return T.p(class_="rdbacklink")["Also see the ",
				T.a(href=rdURL)["resources provided by this RD"],
				"."]
		return ""
	
	def render_titlemessage(self, ctx, data):
		return ctx.tag["%s -- %s"%(
			base.getConfig("web", "sitename"), self.titleMessage)]

	def renderHTTP(self, ctx):
		request = inevow.IRequest(ctx)
		request.setResponseCode(self.status)
		return rend.Page.renderHTTP(self, ctx)


class NotFoundPage(ErrorPage):
	handles = svcs.UnknownURI
	status = 404
	titleMessage = "Not Found"

	def renderHTTP_notFound(self, ctx):
		return self.renderHTTP(ctx)

	docFactory = common.doctypedStan(T.html[
		T.head(render=T.directive("commonhead"))[
			T.title(render=T.directive("titlemessage"))],
		T.body[
			T.img(src="/static/img/logo_medium.png", style="position:absolute;"
				"right:0pt"),
			T.h1["Resource Not Found (404)"],
			T.p["We're sorry, but the resource you requested could not be located."],
			T.p(render=T.directive("message")),
			T.p["If this message resulted from following a link from ",
				T.strong["within the data center"],
				", you have discovered a bug, and we would be"
				" extremely grateful if you could notify us."],
			T.p["If you got here following an ",
				T.strong["external link"],
				", we would be"
				" grateful for a notification as well.  We will ask the"
				" external operators to fix their links or provide"
				" redirects as appropriate."],
			T.p["In either case, you may find whatever you were looking"
				" for by inspecting our ",
				T.a(href="/")["list of published services"], "."],
			T.p(render=T.directive("rdlink")),
			ErrorPage._footer
		]])


class OtherNotFoundPage(NotFoundPage):
	handles = base.NotFoundError


class RDNotFoundPage(NotFoundPage):
	handles = base.RDNotFound


class ForbiddenPage(ErrorPage):
	handles = svcs.ForbiddenURI
	status = 403
	titleMessage = "Forbidden"

	docFactory = common.doctypedStan(T.html[
		T.head(render=T.directive("commonhead"))[
			T.title(render=T.directive("titlemessage"))],
		T.body[
			T.img(src="/static/img/logo_medium.png", style="position:absolute;"
				"right:0pt"),
			T.h1["Access denied (403)"],
			T.p["We're sorry, but the resource you requested is forbidden."],
			T.p(render=T.directive("message")),
			T.p["This usually means you tried to use a renderer on a service"
				" that does not support it.  If you did not come up with the"
				" URL in question yourself, complain fiercely to the %s staff."%
					base.getConfig("web", "sitename")],
			T.p(render=T.directive("rdlink")),
			ErrorPage._footer,
		]])


class RedirectPage(ErrorPage):
	handles = svcs.WebRedirect
	status = 301
	titleMessage = "Redirect"

	def renderHTTP(self, ctx):
		request = inevow.IRequest(ctx)
		# add request arguments if they are not already included in the
		# URL we're redirecting to:
		self.destURL = self.failure.value.dest
		if '?' not in self.destURL:
			args = urlparse.urlparse(request.uri).query
			if args:
				self.destURL = self.failure.value.dest+"?"+args
		request.setHeader("location", str(self.destURL))
		return ErrorPage.renderHTTP(self, ctx)
	
	def render_destLink(self, ctx, data):
		return ctx.tag(href=self.destURL)
	
	docFactory = common.doctypedStan(T.html[
		T.head(render=T.directive("commonhead"))[
			T.title(render=T.directive("titlemessage"))],
		T.body[
			T.img(src="/static/img/logo_medium.png", style="position:absolute;"
				"right:0pt"),
			T.h1["Moved permanently (301)"],
			T.p["The resource you requested is available from a ",
				T.a(render=T.directive("destLink"))[
			 		"different URL"],
				"."],
			T.p["You should not see this page -- either your browser or"
				" our site is broken.  Complain."],
			ErrorPage._footer,
		]])


class AuthenticatePage(ErrorPage):
	handles = svcs.Authenticate
	status = 401
	titleMessage = "Authentication Required"

	def renderHTTP(self, ctx):
		request = inevow.IRequest(ctx)
		request.setHeader('WWW-Authenticate', 
			'Basic realm="%s"'%str(self.failure.value.realm))
		return ErrorPage.renderHTTP(self, ctx)
	
	docFactory = common.doctypedStan(T.html[
		T.head(render=T.directive("commonhead"))[
			T.title(render=T.directive("titlemessage"))],
		T.body[
			T.p["The resource you are trying to access is protected."
				"  Please enter your credentials (by reloading this page), contact"
				" the data center staff or go back to ",
				T.a(href="/", render=T.directive("rootlink"))["the root page"],
				"."]]])


class BadMethodPage(ErrorPage):
	handles = svcs.BadMethod
	status = 405
	titleMessage = "Bad Method"

	docFactory = common.doctypedStan(T.html[
		T.head(render=T.directive("commonhead"))[
			T.title(render=T.directive("titlemessage"))],
		T.body[
			T.img(src="/static/img/logo_medium.png", style="position:absolute;"
				"right:0pt"),
			T.h1["Bad Method (405)"],
			T.p["You just tried to use some HTTP method to access this resource"
				" that this resource does not support.  This probably means that"
				" this resource is for exclusive use for specialized clients."],
			T.p["You may find whatever you were really looking"
				" for by inspecting our ",
				T.a(href="/")["list of published services"],
				"."],
			ErrorPage._footer,
		]])


class NotAcceptable(ErrorPage):
	handles = base.DataError
	status = 406
	titleMessage = "Not Acceptable"

	docFactory = common.doctypedStan(T.html[
		T.head(render=T.directive("commonhead"))[
			T.title(render=T.directive("titlemessage"))],
		T.body[
			T.img(src="/static/img/logo_medium.png", style="position:absolute;"
				"right:0pt"),
			T.h1["Not Acceptable (406)"],
			T.p["The server cannot generate the data you requested."
				"  The associated message is:"],
			T.p(render=T.directive("message")),
			ErrorPage._footer,
		]])


class ErrorDisplay(ErrorPage):
	handles = base.ReportableError
	status = 500
	titleMessage = "Error"

	docFactory = common.doctypedStan(T.html[
		T.head(render=T.directive("commonhead"))[
			T.title(render=T.directive("titlemessage"))],
		T.body[
			T.img(src="/static/img/logo_medium.png", style="position:absolute;"
				"right:0pt"),
			T.h1["Server-side Error (500)"],
			T.p(render=T.directive("message")),
			T.p["This usually means we've fouled up, and there's no"
				" telling whether we've realized that already.  So, chances are"
				" we'd be grateful if you told us at the address given below."
				" Thanks."],
			T.p(render=T.directive("hint")),
			ErrorPage._footer,
		]])
# HTML mess for last-resort type error handling.
errorTemplate = (
		'<body><div style="position:fixed;left:4px;top:4px;'
		'visibility:visible;overflow:visible !important;'
		'max-width:600px !important;z-index:500">'
		'<div style="border:2px solid red;'
		'width:400px !important;background:white">'
		'%s'
		'</div></div></body></html>')

def _formatFailure(failure):
	return errorTemplate%(
		"<h1>Internal Error</h1><p>A(n)"
		" %s exception occurred.  The"
		" accompanying message is: '%s'</p>"
		"<p>If you are seeing this, it is always a bug in our code"
		" or the data descriptions, and we would be extremely grateful"
		" for a report at"
		" %s</p>"%(failure.value.__class__.__name__,
			common.escapeForHTML(failure.getErrorMessage()),
			config.getMeta("contact.email").getContent()))


class InternalServerErrorPage(ErrorPage):
	"""A catch-all page served when no other error page seemed responsible.
	"""
	handles = base.Error  # meaningless, no isinstance done here
	status = 500
	titleMessage = "Uncaught Exception"

	def data_excname(self, ctx, data):
		log.err(self.failure, _why="Uncaught exception")
		return self.failure.value.__class__.__name__

	def renderInnerException(self, ctx):
		"""called when rendering already has started.

		We don't know where we're sitting, so we try to break out as well
		as we can.
		"""
		request = inevow.IRequest(ctx)
		request.setResponseCode(500)  # probably too late, but log still profits.
		data = _formatFailure(self.failure)
		if isinstance(data, unicode):
			data = data.encode("utf-8", "ignore")
		request.write(data)
		request.finishRequest(False)
		return ""

	def renderHTTP(self, ctx):
		request = inevow.IRequest(ctx)
		base.ui.notifyFailure(self.failure)
		base.ui.notifyInfo("Arguments of failed request: %s"%
			repr(request.args)[:2000])
		if getattr(self.failure.value, "hint", None):
			base.ui.notifyDebug("Exception hint: %s"%self.failure.value.hint)
		if request.startedWriting:
			# exception happened while rendering a page.
			return self.renderInnerException(ctx)
		else:
			return ErrorPage.renderHTTP(self, ctx)

	docFactory = common.doctypedStan(T.html[
		T.head(render=T.directive("commonhead"))[
			T.title(render=T.directive("titlemessage"))],
		T.body[
			T.img(src="/static/img/logo_medium.png", style="position:absolute;"
				"right:0pt"),
			T.h1["Server Error (500)"],
			T.p["Your action has caused a(n) ",
				T.span(render=str, data=T.directive("excname")),
				" exception to occur.  As additional info, the failing code"
				" gave:"],
			T.p(render=T.directive("message")),
			T.p["This is always a bug in our software, and we would really"
				" be grateful for a report to the contact address below,"
				" preferably with a description of what you were trying to do,"
				" including any data pieces if applicable.  Thanks."],
			ErrorPage._footer,
		]])


def _writePanicInfo(ctx, failure, secErr=None):
	"""write some panic-type stuff for failure and finishes the request.
	"""
	request = inevow.IRequest(ctx)
	request.setResponseCode(500)
	base.ui.notifyFailure(failure)
	base.ui.notifyInfo("Arguments were %s"%request.args)
		# write out some HTML and hope
		# for the best (it might well turn up in the middle of random output)
	request.write(
		"<html><head><title>Severe Error</title></head><body>")
	try:
		request.write(_formatFailure(failure))
	except:
		request.write("<h1>Ouch</h1><p>There has been an error that in"
			" addition breaks the toplevel error catching code.  Complain.</p>")
	base.ui.notifyError("Error while processing failure: %s"%secErr)
	request.write("</body></html>")
	request.finishRequest(False)


getErrorPage = utils.buildClassResolver(
	baseClass=ErrorPage, 
	objects=globals().values(),
	instances=False, 
	key=lambda obj: obj.handles, 
	default=InternalServerErrorPage)


def getDCErrorPage(error):
	"""returns stuff for root.ErrorCatchingNevowSite.
	"""
# This should be replaced by remembering DCExceptionHandler when
# some day we fix nevow.
	if error is None:
		error = failure.Failure()
	return getErrorPage(error.value.__class__)(error)


def _finishErrorProcessing(ctx, error):
	"""finishes ctx's request.
	"""
# this is also intended as a hook when something weird happens during
# error processing.  When everything's fine, you should end up here.
	request = inevow.IRequest(ctx)
	request.finishRequest(False)
	return ""


class DCExceptionHandler(object):
	"""The toplevel exception handler.
	"""
# Since something here is broken in nevow, this isn't really used.
	implements(inevow.ICanHandleException, inevow.ICanHandleNotFound)

	def renderHTTP_exception(self, ctx, error):
		try:
			handler = getDCErrorPage(error)
			return defer.maybeDeferred(handler.renderHTTP, ctx
				).addCallback(lambda ignored: _finishErrorProcessing(ctx, error)
				).addErrback(lambda secErr: _writePanicInfo(ctx, error, secErr))
		except:
			base.ui.notifyError("Error while handling %s error:"%error)
			_writePanicInfo(ctx, error)

	def renderHTTP_notFound(self, ctx):
		try:
			raise svcs.UnknownURI("locateChild returned None")
		except svcs.UnknownURI:
			return NotFoundPage(failure.Failure())

	def renderInlineException(self, ctx, error):
		# We can't really do that.  Figure out how to break out of this.
		log.err(error, _why="Inline exception")
		return ('<div style="border: 1px dashed red; color: red; clear: both">'
			'[[ERROR]]</div>')
