"""
Infrastructure pages.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import datetime
import os

import pkg_resources
from nevow import inevow
from nevow import rend
from nevow import static
from nevow import url
from twisted.web import http

from gavo import base
from gavo import registry
from gavo import svcs
from gavo import utils
from gavo.web import caching
from gavo.web import common
from gavo.web import grend


class ReloadPage(grend.GavoRenderMixin, rend.Page):
	"""A page to clear some caches.

	Right now, we don't use it (e.g., it's not reachable from the web).  There's
	gavo serve reload and reloads of individual RDs, so there may not be much of
	a niche for this.

	If it ever gets resurrected, we probably should use user.server._reload
	as the implementation.
	"""
	modsToReload = []

	def __init__(self, ctx):
		rend.Page.__init__(self)
		self.modulesReloaded = []
	
	def data_reloadedModules(self, ctx, data):
		return self.modulesReloaded

	def renderHTTP(self, ctx):
		return common.runAuthenticated(ctx, "admin", self._reload, ctx)

	def _reloadModules(self):
		for modPath in self.modsToReload:
			parts = modPath.split(".")
			exec "from %s import %s;reload(%s)"%(".".join(parts[:-1]), parts[-1],
				parts[-1])
			self.modulesReloaded.append(modPath)

	def _reload(self, ctx):
		base.caches.clearCaches()
		self._reloadModules()
		return self._renderHTTP(ctx)
	
	docFactory = svcs.loadSystemTemplate("reloaded.html")


class LoginPage(rend.Page, grend.GavoRenderMixin):
	"""a page that logs people in or out.

	You should usually give a nextURL parameter in the context, the page
	the user is returned to afte login.

	If the user is already authenticated, this will do a logout (by
	sending a 403).
	"""
	def __init__(self, ctx):
		rend.Page.__init__(self)
		self.request = inevow.IRequest(ctx)
		self.nextURL = self.request.args.get("nextURL", ["/"])[0]

	def render_nextURL(self, ctx, data):
		return ctx.tag(href=self.nextURL)

	def render_iflogged(self, ctx, data):
		if self.request.getUser():
			return ctx.tag
		return ""
	
	def render_ifnotlogged(self, ctx, data):
		if not self.request.getUser():
			return ctx.tag
		return ""

	def data_loggedUser(self, ctx, data):
		return self.request.getUser()

	def renderHTTP(self, ctx):
		relogging = base.parseBooleanLiteral(utils.getfirst(
			self.request.args, "relog", default="False"))
		if self.request.getUser():  # user is logged in...
			if relogging: # ...and wants to log out: show login dialog...
				raise svcs.Authenticate()
			else:   # ...and has just logged in: forward to destination
				return url.URL.fromContext(ctx).click(self.nextURL)
		else:  # user is not logged in
			if relogging:  #...but was and has just logged out: forward to dest
				return url.URL.fromContext(ctx).click(self.nextURL)
			else: # ... and wants to log in.
				raise svcs.Authenticate()

	docFactory = svcs.loadSystemTemplate("loginout.html")


def _replaceConfigStrings(srcPath, registry):
	src = open(srcPath).read().decode("utf-8")
	src = src.replace("__site_path__", base.getConfig("web", "nevowRoot"))
	src = src.replace("__site_url__", os.path.join(
		base.getConfig("web", "serverURL")+base.getConfig("web", "nevowRoot")))
	return src.encode("utf-8")


class TemplatedPage(grend.CustomTemplateMixin, grend.ServiceBasedPage):
	"""a "server-wide" template.

	For now, they all are based on the dc root service.
	"""
	checkedRenderer = False
	def __init__(self, ctx, fName):
		self.customTemplate = fName
		grend.ServiceBasedPage.__init__(self, ctx,
			base.caches.getRD(registry.SERVICELIST_ID
			).getById("root"))
		self.setMeta("dateUpdated", 
			utils.formatISODT(
				datetime.datetime.fromtimestamp(os.path.getmtime(fName))))


def expandTemplate(ctx, fName):
	"""renders fName as a template on the root service.
	"""
	return TemplatedPage(ctx, fName)


class StaticFile(rend.Page):
	"""a file from the file system, served pretty directly.

	Since these really are static files that are not supposed to change
	for e.g., admins, we can cache very aggressively.

	The cache is bound to the servicelist RD ID and thus will be cleared
	on a server reload.
	"""
	defaultType = "application/octet-stream"

	magicMimes = {
		"text/nevow-template": expandTemplate,
	}

	def __init__(self, fName):
		self.fName = fName

	def getMimeType(self):
		ext = os.path.splitext(self.fName)[-1]
		return static.File.contentTypes.get(ext, self.defaultType)

	def renderPlain(self, request):
		static.FileTransfer(
			open(self.fName), os.path.getsize(self.fName), request)

	def renderHTTP(self, ctx):
		request = inevow.IRequest(ctx)
		rd = base.caches.getRD(registry.SERVICELIST_ID)

		modStamp = max(rd.loadedAt, os.path.getmtime(self.fName))
		if request.setLastModified(modStamp) is http.CACHED:
			return ''
		cache = base.caches.getPageCache(rd.sourceId)
		cachedRes = cache.get(self.fName)
		if cachedRes is not None and cachedRes.creationStamp>modStamp:
			return cachedRes
		caching.instrumentRequestForCaching(request,
			caching.enterIntoCacheAs(self.fName, cache))
		if not os.path.isfile(self.fName):
			raise svcs.ForbiddenURI("Only plain files are served here")

		mime = self.getMimeType()
		if mime in self.magicMimes:
			return self.magicMimes[mime](ctx, self.fName)
		else:
			request.setHeader("content-type", mime)
			self.renderPlain(request)
		return request.deferred


class StaticServer(rend.Page):
	"""is a server for various static files.

	This is basically like static.File, except

		- we don't do directory listings
		- we don't bother with ranges
		- we look for each file in a user area and then in the system area.
	"""
	def __init__(self):
		rend.Page.__init__(self)
		self.userPath = utils.ensureOneSlash(
			os.path.join(base.getConfig("webDir"), "nv_static"))
		self.systemPath = utils.ensureOneSlash(
			pkg_resources.resource_filename('gavo', "resources/web"))

	def renderHTTP(self, ctx):
		raise svcs.UnknownURI("What did you expect here?")

	def locateChild(self, ctx, segments):
		relPath = "/".join(segments)
		path = self.userPath+relPath
		if os.path.exists(path):
			return StaticFile(path), ()
		path = self.systemPath+relPath
		if os.path.exists(path):
			return StaticFile(path), ()
		raise svcs.UnknownURI("No matching file,"
			" neither built-in nor user-provided")
	processors = {
		".shtml": _replaceConfigStrings,
	}


class RobotsTxt(rend.Page):
	"""A page combining some built-in robots.txt material with etc/robots.txt
	if it exists.
	"""
	builtin = utils.fixIndentation("""
		Disallow: /login
		Disallow: /seffe
		""", "")

	def _getContent(self):
		content = self.builtin
		try:
			with open(os.path.join(base.getConfig("webDir"), "robots.txt")) as f:
				content = content+"\n"+f.read()
		except IOError:
			pass
		return content

	def renderHTTP(self, ctx):
		request = inevow.IRequest(ctx)
		request.setHeader("content-type", "text/plain")
		return self._getContent()

	def locateChild(self, segments):
		return None
