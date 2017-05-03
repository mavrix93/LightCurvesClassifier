"""
User-defined renderers.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.

import imp

from nevow import url

from gavo import svcs
from gavo.web import grend


class CustomRenderer(grend.ServiceBasedPage):
	"""A renderer defined in a python module.
	
	To define a custom renderer write a python module and define a
	class MainPage inheriting from gavo.web.ServiceBasedPage.

	This class basically is a nevow resource, i.e., you can define
	docFactroy, locateChild, renderHTTP, and so on.

	To use it, you have to define a service with the resdir-relative path
	to the module in the customPage attribute and probably a nullCore.  You
	also have to allow the custom renderer (but you may have other renderers,
	e.g., static).

	If the custom page is for display in web browsers, define a
	class method isBrowseable(cls, service) returning true.  This is
	for the generation of links like "use this service from your browser"
	only; it does not change the service's behaviour with your renderer.

	There should really be a bit more docs on this, but alas, there's
	none as yet.
	"""
	name = "custom"

	def __init__(self, ctx, service):
		grend.ServiceBasedPage.__init__(self, ctx, service)
		if not service.customPage:
			raise svcs.UnknownURI("No custom page defined for this service.")
		pageClass, self.reloadInfo = service.customPageCode
		self.realPage = pageClass(ctx, service)

	@classmethod
	def isBrowseable(self, service):
		return getattr(service, "customPageCode", None
			) and service.customPageCode[0].isBrowseable(service)

	def _reload(self, ctx):
		mod = imp.load_module(*self.reloadInfo)
		pageClass = mod.MainPage
		self.service.customPageCode = (pageClass, self.reloadInfo)
		return url.here.curdir()

	def renderHTTP(self, ctx):
		return self.realPage.renderHTTP(ctx)
	
	def locateChild(self, ctx, segments):
		return self.realPage.locateChild(ctx, segments)
