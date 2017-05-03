"""
Renderers supporting upload cores.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from nevow import inevow
from nevow import loaders
from nevow import tags as T

from gavo import base
from gavo.web import formrender


class Uploader(formrender.Form):
	"""A renderer allowing for updates to individual records using file upload.

	This renderer exposes a form with a file widget.	It is likely that
	the interface will change.
	"""

	name = "upload"

	def render_uploadInfo(self, ctx, data):
		if data is None:
			return T.invisible()
		else:
			for key, val in data.original.getPrimaryTable().rows[0].iteritems():
				ctx.tag.fillSlots(key, str(val))
			return ctx.tag

	docFactory = loaders.stan(T.html[
		T.head[
			T.title["Upload"],
			T.invisible(render=T.directive("commonhead")),
		],
		T.body(render=T.directive("withsidebar"))[
			T.h1(render=T.directive("meta"))["title"],
			T.p(class_="procMessage", data=T.directive("result"), 
					render=T.directive("uploadInfo"))[
				T.slot(name="nAffected"),
				" record(s) modified."
			],
			T.invisible(render=T.directive("form genForm"))
		]
	])


class MachineUploader(Uploader):
	"""A renderer allowing for updates to individual records using file 
	uploads.

	The difference to Uploader is that no form-redisplay will be done.
	All errors are reported through HTTP response codes and text strings.
	It is likely that this renderer will change and/or go away.
	"""

	name = "mupload"

	def _handleInputErrors(self, failure, ctx):
		request = inevow.IRequest(ctx)
		request.setResponseCode(500)
		request.setHeader("content-type", "text/plain;charset=utf-8")
		request.write(failure.getErrorMessage().encode("utf-8"))
		base.ui.notifyFailure(failure)
		return ""

	def _notifyNonModified(self, data, ctx):
		request = inevow.IRequest(ctx)
		request.setResponseCode(400)
		request.setHeader("content-type", "text/plain;charset=utf-8")
		request.write(("Uploading %s did not change data database.\nThis"
			" usually happens when the file already existed for an insert"
			" or did not exist for an update.\n"%(
			data.inputTable.getParamDict()["File"][0],
			)).encode("utf-8"))
		return ""

	def _formatOutput(self, data, ctx):
		numAffected = data.original.getPrimaryTable().rows[0]["nAffected"]
		if numAffected==0:
			return self._notifyNonModified(data, ctx)
		request = inevow.IRequest(ctx)
		request.setResponseCode(200)
		request.setHeader("content-type", "text/plain;charset=utf-8")
		request.write(("%s uploaded, %d records modified\n"%(
			data.inputTable.getParamDict()["File"][0],
			numAffected)).encode("utf-8"))
		return ""
