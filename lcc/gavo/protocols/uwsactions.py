"""
Manipulating UWS jobs through a REST interface.

The result documents are defined through the schema uws-1.0.xsd.

Instead of returning XML, they can also raise WebRedirect exceptions.
However, these are caught in JobResource._redirectAsNecessary and appended
to the base URL auf the TAP service, so you must only give URIs relative
to the TAP service's root URL.

This UWS system should adapt to concrete UWSes; the UWS in use is passed
into the top-level functions (doJobAction , getJobList)
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from __future__ import with_statement

import os

from nevow import inevow
from nevow import rend
from nevow import static

from gavo import base
from gavo import svcs
from gavo import utils
from gavo.protocols import uws
from gavo.utils import stanxml
from gavo.votable import V


UWSNamespace = 'http://www.ivoa.net/xml/UWS/v1.0'
XlinkNamespace = "http://www.w3.org/1999/xlink"
stanxml.registerPrefix("uws", UWSNamespace,
	stanxml.schemaURL("uws-1.0.xsd"))
stanxml.registerPrefix("xlink", XlinkNamespace,
	stanxml.schemaURL("xlink.xsd"))


# Sadly, TAP protocol keys need to be case insensitive (spec, 2.3.10)
# The code here assumes all keys to be in lowercase, and this function
# forces this.  You should call it as soon as possible when processing
# requests.
#
# Note that non-protocol keys are not case-normalized, since there's always
# the hope for sane protocols that don't have crazy case-folding rules.
# UWS parameters are lower-cased, too, right now, though (in 
# set/getSerializedPar, by a different mechanism).
#
# XXX TODO: there are TAP keys in here, too.  Come up with a way
# to have worker systems say which keys they want case insensitive
_CASE_INSENSITIVE_KEYS = set(["request", "version", "lang", "query", 
	"format", "maxrec", "runid", "upload", "action", "phase",
	"executionduration", "destruction",])

def lowercaseProtocolArgs(args):
	for key in args:
		if key.lower()==key:
			continue
		if key.lower() in _CASE_INSENSITIVE_KEYS:
			content = args.pop(key)
			args[key.lower()] = content


class UWS(object):
	"""the container for elements from the uws namespace.
	"""
	class UWSElement(stanxml.Element):
		_prefix = "uws"

	@staticmethod
	def makeRoot(ob):
		ob._additionalPrefixes = stanxml.xsiPrefix
		ob._mayBeEmpty = True
		return ob

	class job(UWSElement): pass
	class jobs(UWSElement):
		_mayBeEmpty = True

	class parameters(UWSElement): pass

	class destruction(UWSElement): pass
	class endTime(stanxml.NillableMixin, UWSElement): pass
	class executionDuration(UWSElement): pass
	class jobId(UWSElement): pass
	class jobInfo(UWSElement): pass
	class message(UWSElement): pass
	class ownerId(stanxml.NillableMixin, UWSElement): pass
	class phase(UWSElement): pass
	class quote(stanxml.NillableMixin, UWSElement): pass
	class runId(UWSElement): pass
	class startTime(stanxml.NillableMixin, UWSElement): pass
	
	class detail(UWSElement):
		_a_href = None
		_a_type = None
		_name_a_href = "xlink:href"
		_name_a_type = "xlink:type"
	
	class errorSummary(UWSElement):
		_a_type = None  # transient | fatal
		_a_hasDetail = None

	class message(UWSElement): pass

	class jobref(UWSElement):
		_additionalPrefixes = frozenset(["xlink"])
		_a_id = None
		_a_href = None
		_a_type = None
		_name_a_href = "xlink:href"
		_name_a_type = "xlink:type"

	class parameter(UWSElement):
		_a_byReference = None
		_a_id = None
		_a_isPost = None

	class result(UWSElement):
		_additionalPrefixes = frozenset(["xlink"])
		_mayBeEmpty = True
		_a_id = None
		_a_href = None
		_a_type = None
		_name_a_href = "xlink:href"
		_name_a_type = "xlink:type"

	class results(UWSElement):
		_mayBeEmpty = True


def getJobList(workerSystem):
	result = UWS.jobs()
	for jobId, phase in workerSystem.getIdsAndPhases():
		result[
			UWS.jobref(id=jobId, href=workerSystem.getURLForId(jobId))[
				UWS.phase[phase]]]
	return stanxml.xmlrender(result, workerSystem.joblistPreamble)


def getErrorSummary(job):
# all our errors are fatal, and for now .../error yields the same thing
# as we include here, so we hardcode the attributes.
	errDesc = job.error
	if not errDesc:
		return None
	msg = errDesc["msg"]
	if errDesc["hint"]:
		msg = msg+"\n\n -- Hint: "+errDesc["hint"]
	return UWS.errorSummary(type="fatal", hasDetail="false")[
		UWS.message[msg]]


def getParametersElement(job):
	"""returns a UWS.parameters element for job.
	"""
	res = UWS.parameters()
	for key, value in job.iterSerializedPars():
		if isinstance(value, uws.ParameterRef):
			res[UWS.parameter(id=key, byReference=True)[value.url]]
		else:
			res[UWS.parameter(id=key)[str(value)]]
	return res


class JobActions(object):
	"""A collection of "actions" performed on UWS jobs.

	Their names are the names of the child resources of UWS jobs.  The basic UWS
	actions are built in.  When constructing those, you can pass in as many
	additional JobAction subclasses as you want.  Set their names to
	one of UWS standard actions to override UWS behaviour if you think
	that's wise.
	"""
	_standardActions = {}

	def __init__(self, *additionalActions):
		self.actions = {}
		self.actions.update(self._standardActions)
		for actionClass in additionalActions:
			self.actions[actionClass.name] = actionClass()

	@classmethod
	def addStandardAction(cls, actionClass):
		cls._standardActions[actionClass.name] = actionClass()

	def dispatch(self, action, job, request, segments):
		try:
			resFactory = self.actions[action]
		except KeyError:
			raise base.ui.logOldExc(
				svcs.UnknownURI("Invalid UWS action '%s'"%action))
		request.setHeader("content-type", resFactory.mime)
		return resFactory.getResource(job, request, segments)
		

class JobAction(object):
	"""an action done to a job.

	It defines methods do<METHOD> that are dispatched through JobActions.

	It must have a name corresponding to the child resource names from
	the UWS spec.
	"""
	name = None
	mime = "text/xml"

	def getResource(self, job, request, segments):
		if segments:
			raise svcs.UnknownURI("Too many segments")
		try:
			handler = getattr(self, "do"+request.method)
		except AttributeError:
			raise base.ui.logOldExc(svcs.BadMethod(request.method))
		return handler(job, request)


class ErrorResource(rend.Page):
	"""A TAP error message.

	These are constructed with errInfo, which is either an exception or
	a dictionary containing at least type, msg, and hint keys.  Optionally, 
	you can give a numeric httpStatus.
	"""
	def __init__(self, errInfo, httpStatus=400):
		if isinstance(errInfo, Exception):
			errInfo = {
				"msg": unicode(errInfo),
				"type": errInfo.__class__.__name__,
				"hint": getattr(errInfo, "hint", None)}
		if errInfo["type"]=="JobNotFound":
			httpStatus = 404
		self.errMsg, self.httpStatus = errInfo["msg"], httpStatus
		self.hint = errInfo["hint"]

	def renderHTTP(self, ctx):
		request = inevow.IRequest(ctx)
		request.setHeader("content-type", "text/xml")
		request.setResponseCode(self.httpStatus)
		doc = V.VOTABLE[
			V.RESOURCE(type="results") [
				V.INFO(name="QUERY_STATUS", value="ERROR")[
						self.errMsg]]]
		if self.hint:
			doc[V.INFO(name="HINT", value="HINT")[
				self.hint]]
		return doc.render()


class ErrorAction(JobAction):
	name = "error"
	mime = "text/plain"

	def doGET(self, job, request):
		if job.error is None:
			return ""
		return ErrorResource(job.error, httpStatus=200)

	doPOST = doGET
JobActions.addStandardAction(ErrorAction)


class StartTimeAction(JobAction):
# This an extension over plain UWS allowing users to retrieve when
# their job started.  In the DaCHS' TAP implementation, this lets 
# you discern whether the taprunner is already processing an EXECUTING
# job (startTime!=NULL) or whether it's still coming up (else)
	name = "startTime"
	mime = "text/plain"

	def doGET(self, job, request):
		if job.startTime is None:
			return "NULL"
		else:
			return utils.formatISODT(job.startTime)

	doPOST = doGET
JobActions.addStandardAction(StartTimeAction)


class ParameterAction(JobAction):
	name = "parameters"

	def doGET(self, job, request):
		request.setHeader("content-type", "text/xml")
		return UWS.makeRoot(getParametersElement(job))
	
	def doPOST(self, job, request):
		with job.getWritable() as wjob:
			for key in request.args:
				wjob.setSerializedPar(key, utils.getfirst(request.args, key, None))
		raise svcs.WebRedirect(job.jobId)

JobActions.addStandardAction(ParameterAction)

class PhaseAction(JobAction):
	name = "phase"
	mime = "text/plain"
	timeout = 10  # this is here for testing

	def doPOST(self, job, request):
		newPhase = utils.getfirst(request.args, "phase", None)
		if newPhase=="RUN":
			job.uws.changeToPhase(job.jobId, uws.QUEUED, timeout=self.timeout)
		elif newPhase=="ABORT":
			job.uws.changeToPhase(job.jobId, uws.ABORTED, timeout=self.timeout)
		else:
			raise base.ValidationError("Bad phase: %s"%newPhase, "phase")
		raise svcs.WebRedirect(job.jobId)
	
	def doGET(self, job, request):
		request.setHeader("content-type", "text/plain")
		return job.phase
JobActions.addStandardAction(PhaseAction)


class _SettableAction(JobAction):
	"""Abstract base for ExecDAction and DestructionAction.
	"""
	mime = "text/plain"

	def doPOST(self, job, request):
		raw = utils.getfirst(request.args, self.name.lower(), None)
		if raw is None:  # with no parameter, fall back to GET
			return self.doGET(job, request)
		try:
			val = self.deserializeValue(raw)
		except ValueError:  
			raise base.ui.logOldExc(uws.UWSError("Invalid %s value: %s."%(
				self.name.upper(), repr(raw)), job.jobId))
		with job.getWritable() as wjob:
			args = {self.attName: val}
			wjob.change(**args)
		raise svcs.WebRedirect(job.jobId)

	def doGET(self, job, request):
		request.setHeader("content-type", "text/plain")
		return self.serializeValue(getattr(job, self.attName))


class ExecDAction(_SettableAction):
	name = "executionduration"
	attName = 'executionDuration'
	serializeValue = str
	deserializeValue = float
JobActions.addStandardAction(ExecDAction)


class DestructionAction(_SettableAction):
	name = "destruction"
	attName = "destructionTime"
	serializeValue = staticmethod(utils.formatISODT)
	deserializeValue = staticmethod(utils.parseISODT)
JobActions.addStandardAction(DestructionAction)


class QuoteAction(JobAction):
	name = "quote"
	mime = "text/plain"

	def doGET(self, job, request):
		request.setHeader("content-type", "text/plain")
		if job.quote is None:
			quote = ""
		else:
			quote = str(job.quote)
		return quote
	
JobActions.addStandardAction(QuoteAction)


class OwnerAction(JobAction):
	# we do not support auth yet, so this is a no-op.
	name = "owner"
	mime = "text/plain"

	def doGET(self, job, request):
		request.setHeader("content-type", "text/plain")
		if job.owner is None:
			request.write("NULL")
		else:
			request.write(job.owner)
		return ""

JobActions.addStandardAction(OwnerAction)


def _getResultsElement(job):
	baseURL = job.getURL()+"/results/"
	return UWS.results[[
			UWS.result(id=res["resultName"], href=baseURL+res["resultName"])
		for res in job.getResults()]]


class ResultsAction(JobAction):
	"""Access result (Extension: and other) files in job directory.
	"""
	name = "results"

	def getResource(self, job, request, segments):
		if not segments:
			return JobAction.getResource(self, job, request, segments)

		# first try a "real" UWS result from the job
		if len(segments)==1:
			try:
				fName, resultType = job.getResult(segments[0])
				res = static.File(fName)
				res.type = str(resultType)
				res.encoding = None
				return res
			except base.NotFoundError: # segments[0] does not name a result
				pass                     # fall through to other files

		# if that doesn't work, try to return some other file from the
		# job directory.  This is so we can deliver uploads.
		filePath = os.path.join(job.getWD(), *segments)
		if not os.path.exists(filePath):
			raise svcs.UnknownURI("File not found")
		return static.File(filePath, defaultType="application/octet-stream")

	def doGET(self, job, request):
		return _getResultsElement(job)

JobActions.addStandardAction(ResultsAction)


def _serializeTime(element, dt):
	if dt is None:
		return element()
	return element[utils.formatISODT(dt)]


class RootAction(JobAction):
	"""Actions for async/jobId.
	"""
	name = ""
	def doDELETE(self, job, request):
		job.uws.destroy(job.jobId)
		raise svcs.WebRedirect("")

	def doPOST(self, wjob, request):
		# (Extension to let web browser delete jobs)
		if utils.getfirst(request.args, "action", None)=="DELETE":
			self.doDELETE(wjob, request)
		else:
			raise svcs.BadMethod("POST")

	def doGET(self, job, request):
		tree = UWS.makeRoot(UWS.job[
			UWS.jobId[job.jobId],
			UWS.runId[job.runId],
			UWS.ownerId[job.owner],
			UWS.phase[job.phase],
			_serializeTime(UWS.startTime, job.startTime),
			_serializeTime(UWS.endTime, job.endTime),
			UWS.executionDuration[str(job.executionDuration)],
			UWS.destruction[utils.formatISODT(job.destructionTime)],
			getParametersElement(job),
			_getResultsElement(job),
			getErrorSummary(job)])
		return stanxml.xmlrender(tree, job.uws.jobdocPreamble)
				

JobActions.addStandardAction(RootAction)


def doJobAction(workerSystem, request, segments):
	"""handles the async UI of UWS.

	Depending on method and segments, it will return various XML strings
	and may cause certain actions.

	Segments must be a tuple with at least one element, the job id.
	"""
	jobId, segments = segments[0], segments[1:]
	if not segments:
		action = ""
	else:
		action, segments = segments[0], segments[1:]
	return workerSystem.jobActions.dispatch(action, 
		workerSystem.getJob(jobId), request, segments)
