"""
A renderer for TAP, both sync and async.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from __future__ import with_statement

import os
from cStringIO import StringIO

from nevow import inevow
from nevow import rend
from twisted.internet import threads

from gavo import base
from gavo import svcs
from gavo import utils
from gavo.protocols import tap
from gavo.protocols import taprunner
from gavo.protocols import uws
from gavo.protocols import uwsactions
from gavo.svcs import streaming
from gavo.web import asyncrender
from gavo.web import common
from gavo.web import grend
from gavo.web import vosi


@utils.memoized
def getTAPVersion():
	return base.caches.getRD(tap.RD_ID).getProperty("TAP_VERSION")


class TAPQueryResource(rend.Page):
	"""the resource executing sync TAP queries.

	While not really going through UWS, this does create a UWS job and
	tears it down later.
	"""
	def __init__(self, service, ctx):
		self.service = service
		rend.Page.__init__(self)

	def _doRender(self, ctx):
		jobId = tap.workerSystem.getNewIdFromRequest(
			inevow.IRequest(ctx), self.service)
		try:
			with tap.workerSystem.changeableJob(jobId) as job:
				job.change(executionDuration=
					base.getConfig("async", "defaultExecTimeSync"))
			taprunner.runTAPJob(jobId)

			job = tap.workerSystem.getJob(jobId)
			if job.phase==uws.COMPLETED:
				# This is TAP, so there's exactly one result
				res = job.getResults()[0]
				name, type = res["resultName"], res["resultType"]
				# hold on to the result fd so its inode is not lost when we delete
				# the job.
				f = open(os.path.join(job.getWD(), name))
				return (f, type)
			elif job.phase==uws.ERROR:
				exc = job.error
				raise base.Error(exc["msg"], hint=exc["hint"])
			elif job.phase==uws.ABORTED:
				raise uws.UWSError("Job was manually aborted.  For synchronous"
					" jobs, this probably means the operators killed it.",
					jobId)
			else:
				raise uws.UWSError("Internal error.  Invalid UWS phase.", jobId)
		finally:
			tap.workerSystem.destroy(jobId)

	def renderHTTP(self, ctx):
		try:
			return threads.deferToThread(self._doRender, ctx
				).addCallback(self._formatResult, ctx
				).addErrback(self._formatError)
		except base.Error, ex:
			base.ui.notifyExceptionMutation(None)
			return uwsactions.ErrorResource(ex)

	def _formatError(self, failure):
		base.ui.notifyFailure(failure)
		return uwsactions.ErrorResource(failure.value)

	def _formatResult(self, res, ctx):
		request = inevow.IRequest(ctx)
		f, type = res

		def writeTable(outputFile):
			utils.cat(f, outputFile)

		request.setHeader("content-type", str(type))
		# if request has an accumulator, we're testing.
		if hasattr(request, "accumulator"):
			writeTable(request)
			return ""
		else:
			return streaming.streamOut(writeTable, request)


def getSyncResource(ctx, service, segments):
	if segments:
		raise svcs.UnknownURI("No resources below sync")
	request = common.getfirst(ctx, "request", base.Undefined)
	if request=="doQuery":
		return TAPQueryResource(service, ctx)
	elif request=="getCapabilities":
		return vosi.VOSICapabilityRenderer(ctx, service)
	return uwsactions.ErrorResource({
			"type": "ParameterError",
			"msg": "Invalid REQUEST: '%s'"%request,
			"hint": "Only doQuery and getCapabilities supported here"})


class _FakeUploadedFile(object):
# File uploads without filenames are args containing a string.
# This class lets them work as uploaded files in _saveUpload.
	def __init__(self, name, content):
		self.filename = name
		self.file = StringIO(content)

# TODO: we should probably define different renderers for sync,
# async.  The renderer shouldn't have to dispatch
# like that.

class TAPRenderer(grend.ServiceBasedPage):
	"""A renderer speaking all of TAP (including sync, async, and VOSI).

	Basically, this just dispatches to the sync and async resources.
	"""
	name = "tap"
	urlUse = "base"

	def renderHTTP(self, ctx):
		# The root resource  redirects to an info on TAP
		raise svcs.WebRedirect(self.service.getURL("info", absolute=False))

	def gatherUploadFiles(self, request):
		"""creates a files attribute on request, containing all uploaded
		files.

		The upload files are removed from args, which is good since we
		don't want to serialize those in the parameters dictionary.

		This method inspects all upload parameters and converts the
		referenced arguments to cgi-like files as necessary.  Missing
		uploads will be noticed here, and the request will be rejected.

		Of course, all that hurts if someone manages to upload from REQUEST --
		but that's their fault then.
		"""
		request.files = {}
		for uploadSpec in request.args.get("upload", []):
			for tableName, upload in tap.parseUploadString(uploadSpec):
				if upload.startswith("param:"):
					paramName = upload[6:]
					if paramName not in request.args or not request.args[paramName]:
						raise base.ReportableError("No parameter for upload"
							" table %s"%tableName)

					item = request.args.pop(paramName)[0]
					# fix if it doesn't already look like a file
					if getattr(item, "file", None) is None:
						item = _FakeUploadedFile(
							"unnamed_inline_upload_%s"%paramName, item)
					request.files[paramName] = item

	def locateChild(self, ctx, segments):
		request = inevow.IRequest(ctx)
		uwsactions.lowercaseProtocolArgs(request.args)

		if not segments[-1]: # trailing slashes are forbidden here
			if len(segments)==1: # root resource; don't redirect, it would be a loop
				return self, ()
			raise svcs.WebRedirect(
				self.service.getURL("tap")+"/"+"/".join(segments[:-1]))

		try:
			self.gatherUploadFiles(request)
			if (getTAPVersion()!=
					utils.getfirst(request.args, "version", getTAPVersion())):
				return uwsactions.ErrorResource({
					"msg": "Version mismatch; this service only supports"
						" TAP version %s."%getTAPVersion(),
					"type": "ValueError",
					"hint": ""}), ()
			if segments:
				if segments[0]=='sync':
					res = getSyncResource(ctx, self.service, segments[1:])
				elif segments[0]=='async':
					res = asyncrender.getAsyncResource(
						ctx, tap.WORKER_SYSTEM, "tap", self.service, segments[1:])
				elif segments[0]=='availability':
					res = vosi.VOSIAvailabilityRenderer(ctx, self.service)
				elif segments[0]=='capabilities':
					res = vosi.VOSICapabilityRenderer(ctx, self.service)
				elif segments[0]=='tables':
					res = vosi.VOSITablesetRenderer(ctx, self.service)
				elif segments[0]=='examples':
					from gavo.web import examplesrender
					res = examplesrender.Examples(ctx, self.service)
				else:
					raise svcs.UnknownURI("Bad TAP path %s"%"/".join(segments))
				return res, ()
		except svcs.UnknownURI:
			raise
		except base.Error, ex:
			# see flagError in protocols.uws for the reason for the next if
			if not isinstance(ex, (base.ValidationError, uws.JobNotFound)):
				base.ui.notifyError("TAP error")
			return uwsactions.ErrorResource(ex), ()
		raise common.UnknownURI("Bad TAP path %s"%"/".join(segments))
