"""
A UWS-based interface to datalink
"""

from __future__ import with_statement

import cPickle as pickle
import datetime

from .. import base
from .. import rscdesc #noflake: cache registration
from . import products
from . import uws
from . import uwsactions


class DLTransitions(uws.ProcessBasedUWSTransitions):
	"""The transition function for datalink jobs.
	"""
	def __init__(self):
		uws.ProcessBasedUWSTransitions.__init__(self, "DL")

	def queueJob(self, newState, wjob, ignored):
		uws.ProcessBasedUWSTransitions.queueJob(self, newState, wjob, ignored)
		return self.startJob(uws.EXECUTING, wjob, ignored)

	def getCommandLine(self, wjob):
		return "gavo", ["gavo", "dlrun", "--", str(wjob.jobId)]


class ServiceIdParameter(uws.JobParameter):
	"""A fully qualified id of the DaCHS service to execute the datalink
	request.
	"""

class ArgsParameter(uws.JobParameter):
	"""all parameters passed to the datalink job as a request.args dict.

	The serialised representation is the pickled dict.  Pickle is ok as
	the string never leaves our control (the network serialisation is
	whatever comes in via the POST).
	"""
	@staticmethod
	def _deserialize(pickled):
		return pickle.loads(pickled)
	
	@staticmethod
	def _serialize(args):
		return pickle.dumps(args)


class DLJob(uws.UWSJobWithWD):
	"""a UWS job performing some datalink data preparation.

	In addition to UWS parameters, it has

	* serviceid -- the fully qualified id of the service that will process
	  the request
	* datalinkargs -- the parameters (in request.args form) of the
	  datalink request.
	"""
	_jobsTDId = "//datalink#datalinkjobs"
	_transitions = DLTransitions()

	_parameter_serviceid = ServiceIdParameter
	_parameter_datalinkargs = ArgsParameter


class DLUWS(uws.UWS):
	"""the worker system for datalink jobs.
	"""
	joblistPreamble = ("<?xml-stylesheet href='/static"
		"/xsl/dlasync-joblist-to-html.xsl' type='text/xsl'?>")
	jobdocPreamble = ("<?xml-stylesheet href='/static/xsl/"
		"dlasync-job-to-html.xsl' type='text/xsl'?>")

	_baseURLCache = None

	def __init__(self):
		uws.UWS.__init__(self, DLJob, uwsactions.JobActions())

	@property
	def baseURL(self):
		return base.makeAbsoluteURL("datalinkuws")

	def getURLForId(self, jobId):
		"""returns a fully qualified URL for the job with jobId.
		"""
		return "%s/%s"%(self.baseURL, jobId)

	def getParamsFromRequest(self, wjob, request, service):
		"""stores datalinkargs from request and the service from service.
		"""
		wjob.setPar("datalinkargs", request.args)
		wjob.setPar("serviceid", service.getFullId())


DL_WORKER = DLUWS()


####################### CLI

def parseCommandLine():
	from gavo.imp import argparse
	parser = argparse.ArgumentParser(description="Run an asynchronous datalink"
		" job (used internally)")
	parser.add_argument("jobId", type=str, help="UWS id of the job to run")
	return parser.parse_args()


def main():
	args = parseCommandLine()
	jobId = args.jobId
	try:
		job = DL_WORKER.getJob(jobId)
		with job.getWritable() as wjob:
			wjob.change(phase=uws.EXECUTING, startTime=datetime.datetime.utcnow())

		service = base.resolveCrossId(job.parameters["serviceid"])
		args = job.parameters["datalinkargs"]
		data = service.run("dlget", args).original

		# Unfortunately, datalink cores can in principle return all kinds
		# of messy things that may not even be representable in plain files
		# (e.g., nevow resources returning redirects).  We hence only
		# handle (mime, payload) and (certain) Product instances here
		# and error out otherwise.
		if isinstance(data, tuple):
			mime, payload = data
			with job.openResult(mime, "result") as destF:
				destF.write(payload)

		elif isinstance(data, products.ProductBase):
			# We could run renderHTTP and grab the content-type from there
			# (which probably would be better all around).  For now, don't
			# care:
			with job.openResult("application/octet-stream", "result") as destF:
				for chunk in data.iterData():
					destF.write(chunk)

		else:
			raise NotImplementedError("Cannot handle a service %s result yet."%
				repr(data))
		
		with job.getWritable() as wjob:
			wjob.change(phase=uws.COMPLETED)

	except SystemExit:
		pass
	except uws.JobNotFound:
		base.ui.notifyInfo("Giving up non-existing datalink job %s."%jobId)
	except Exception, ex:
		base.ui.notifyError("Datalink runner %s major failure"%jobId)
		# try to push job into the error state -- this may well fail given
		# that we're quite hosed, but it's worth the try
		DL_WORKER.changeToPhase(jobId, uws.ERROR, ex)
		raise
