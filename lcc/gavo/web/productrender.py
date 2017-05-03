"""
Code dealing with product (i.e., fits file) delivery.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from nevow import inevow

from gavo import base
from gavo import svcs
from gavo.protocols import products
from gavo.web import grend


class ProductRenderer(grend.ServiceBasedPage):
	"""The renderer used for delivering products.

	This will only work with a ProductCore since the resulting
	data set has to contain products.Resources.  Thus, you probably
	will not use this in user RDs.
	"""
	name = "get"
	pathFromSegments = ""

	def renderHTTP(self, ctx):
		request = inevow.IRequest(ctx)
		try:
			data = {"accref": 
				products.RAccref.fromRequest(self.pathFromSegments, request)}
		except base.NotFoundError:
			raise base.ui.logOldExc(svcs.UnknownURI("No product specified"))

		# deferring here and going to all the trouble of running a core
		# is probably overkill; currently, the main thing that'd require
		# handwork is figuring out authentication in parallel with what
		# needs to be done for tar files.  We should do better, indded.
		return self.runServiceWithFormalData(data, ctx
			).addCallback(self._deliver, ctx)
	
	def _deliver(self, result, ctx):
		doPreview = result.queryMeta.ctxArgs.get("preview")
		product = result.original.getPrimaryTable().rows[0]['source']
		request = inevow.IRequest(ctx)

		# TODO: figure out a good way to see whether what we've got already is a
		# preview.
		if doPreview and not "Preview" in product.__class__.__name__:
			return products.PreviewCacheManager.getPreviewFor(product
				).addCallback(self._deliverPreview, product, request
				).addErrback(self._deliverPreviewFailure, request)

		else:
			return product

	def _deliverPreview(self, content, product, request):
		previewMime = product.pr["preview_mime"] or "image/jpeg"
		request.setHeader("content-type", str(previewMime))
		request.setHeader("content-length", len(content))
		return content
	
	def _deliverPreviewFailure(self, failure, request):
		failure.printTraceback()
		data = "Not an image (preview generation failed, please report)"
		request.setResponseCode(500)
		request.setHeader("content-type", "text/plain")
		request.setHeader("content-length", str(len(data)))
		return data

	def locateChild(self, ctx, segments):
		if segments:
			self.pathFromSegments = "/".join(segments)
		return self, ()
