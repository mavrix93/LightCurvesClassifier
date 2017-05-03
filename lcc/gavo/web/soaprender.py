"""
SOAP rendering and related classes.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from nevow import inevow

from twisted.web import soap

from gavo import base
from gavo import svcs
from gavo.web import grend
from gavo.web import wsdl


class SOAPProcessor(soap.SOAPPublisher):
	"""A helper to the SOAP renderer.

	It's actually a nevow resource ("page"), so whatever really has
	to do with SOAP (as opposed to returning WSDL) is done by this.
	"""
	def __init__(self, ctx, service, runServiceFromArgs):
		self.ctx, self.service = ctx, service
		self.runServiceFromArgs = runServiceFromArgs
		soap.SOAPPublisher.__init__(self)

	def _gotResult(self, result, request, methodName):
# We want SOAP docs that actually match what we advertize in the WSDL.
# So, I override SOAPPublisher's haphazard SOAPpy-based formatter.
		if result is None:  # Error has occurred.  This callback shouldn't be
			# called at all, but for some reason it is, and I can't be bothered
			# now to figure out why.
			return ""
		response = wsdl.serializePrimaryTable(result.original, self.service)
		self._sendResponse(request, response)
	
	def _gotError(self, failure, request, methodName):
		failure.printTraceback()
		try:
			self._sendResponse(request, 
				wsdl.formatFault(failure.value, self.service), status=500)
		except:
			base.ui.logError("Error while writing SOAP error:")

	def soap_useService(self, *args):
		try:
			return self.runServiceFromArgs(self.ctx, args)
		except Exception, exc:
			return self._formatError(exc)

	def _formatError(self, exc):
		request = inevow.IRequest(self.ctx)
		self._sendResponse(request, wsdl.formatFault(exc, self.service), 
			status=500)


class SOAPRenderer(grend.ServiceBasedPage):
	"""A renderer that receives and formats SOAP messages.

	This is for remote procedure calls.  In particular, the renderer takes
	care that you can obtain a WSDL definition of the service by
	appending ?wsdl to the access URL.
	"""
	name="soap"
	preferredMethod = "POST"
	urlUse = "full"

	@classmethod
	def makeAccessURL(cls, baseURL):
		return baseURL+"/soap/go"
	
	def runServiceFromArgs(self, ctx, args):
		"""starts the service.

		This being called back from the SOAPProcessor, and args is the
		argument tuple as given from SOAP.
		"""
		inputPars = dict(zip(
			[f.name for f in self.service.getInputKeysFor(self)],
			args))
		return self.runServiceWithFormalData(inputPars, ctx)

	def renderHTTP(self, ctx):
		"""returns the WSDL for service.

		This is only called when there's a ?wsdl arg in the request,
		otherwise locateChild will return the SOAPProcessor.
		"""
		request = inevow.IRequest(ctx)
		if not hasattr(self.service, "_generatedWSDL"):
			queryMeta = svcs.QueryMeta.fromContext(ctx)
			self.service._generatedWSDL = wsdl.makeSOAPWSDLForService(
				self.service, queryMeta).render()
		request.setHeader("content-type", "text/xml")
		return self.service._generatedWSDL

	def locateChild(self, ctx, segments):
		request = inevow.IRequest(ctx)
		if request.uri.endswith("?wsdl"): # XXX TODO: use parsed headers here
			return self, ()
		if request.method!='POST': 
			# SOAP only makes sense when data is posted; with no data,
			# twisted generates ugly tracebacks, and we may as well do
			# something sensible, like... redirect to the service's info
			# page
			raise svcs.WebRedirect(self.service.getURL("info"))
		return SOAPProcessor(ctx, self.service, self.runServiceFromArgs), ()
