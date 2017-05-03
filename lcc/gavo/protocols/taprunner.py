"""
Execution of UWS (right now, TAP only) requests.

This mainly intended to be exec'd (through some wrapper) by the queue
runner in the main server thread.  The jobs executed have to be in
the database and have to have a job directory.

Primarily for testing an alternative interface rabRun exists that takes that
takes jobid, and parameters.

The tap runner takes the job to EXECUTING shortly before sending the
query to the DB server.  When done, the job's state is one of COMPLETED, 
ABORTED or ERROR.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from __future__ import with_statement

import datetime
import sys
import time

from gavo import base
from gavo import formats
from gavo import rsc
from gavo import rscdesc #noflake: cache registration
from gavo import svcs
from gavo import utils
from gavo import votable
from gavo.base import valuemappers
from gavo.formats import csvtable #noflake: format registration
from gavo.formats import jsontable #noflake: format registration
from gavo.formats import votableread
from gavo.formats import votablewrite
from gavo.protocols import adqlglue
from gavo.protocols import tap
from gavo.protocols import uws


# set to true by the signal handler
EXIT_PLEASE = False


# The following would point to executors for other languages at some point.
SUPPORTED_LANGS = {
	'ADQL': None,
	'ADQL-2.0': None,
}


# The pid of the worker db backend.  This is used in the signal handler
# when it tries to kill the running query.
_WORKER_PID = None


def normalizeTAPFormat(rawFmt):
	format = rawFmt.lower()
	try:
		return tap.FORMAT_CODES[format][0]
	except KeyError:
		raise base.ValidationError(
			"Unsupported format '%s'."%format, colName="FORMAT",
			hint="Legal format codes include %s"%(", ".join(tap.FORMAT_CODES)))


def _parseTAPParameters(jobId, parameters):
	"""gets and checks TAP parameters like version, request, and such.

	The function returns a tuple of query and maxrec.
	"""
	rd = base.caches.getRD("__system__/tap")
	version = rd.getProperty("TAP_VERSION")
	try:
		if parameters.get("version", version)!=version:
			raise uws.UWSError("Version mismatch.  This service only supports"
				" TAP version %s"%version, jobId)
		if parameters["request"]!="doQuery":
			raise uws.UWSError("This service only supports REQUEST=doQuery", jobId)
		if parameters["lang"] not in SUPPORTED_LANGS:
			raise uws.UWSError("This service only supports LANG=ADQL", jobId)
		query = parameters["query"].decode("utf-8")
	except KeyError, key:
		raise base.ui.logOldExc(base.ValidationError(
			"Required parameter %s missing."%key, key))

	try:
		maxrec = min(base.getConfig("async", "hardMAXREC"),
			int(parameters["maxrec"]))
	except ValueError:
		raise base.ui.logOldError(
			uws.UWSError("Invalid MAXREC literal '%s'."%parameters["maxrec"]))
	except KeyError:
		maxrec = base.getConfig("async", "defaultMAXREC")
	return query, maxrec


def _makeDataFor(resultTable):
	"""returns an rsc.Data instance containing resultTable and some
	additional metadata.
	"""
	resData = rsc.wrapTable(resultTable)
	resData.addMeta("info", base.makeMetaValue("Query successful",
		name="info", infoName="QUERY_STATUS", infoValue="OK"))
	resData.addMeta("_type", "results")
	# setLimit is the effective maximum number of rows returned
	# as determined by adqlglue.morphADQL (or similar functions)
	resData.setLimit = getattr(resultTable.tableDef, "setLimit", None)
	return resData


def writeResultTo(format, res, outF):
	# special-case votable formats to handle overflow conditions and such
	if format.startswith("votable"):
		# the following duplicates a mapping from votablewrite; that's
		# bad, and I should figure out a way to teach formats.format
		# whatever is needed to let it do what we're doing here.  Meanwhile:
		enc = {
			"votable": "binary",
			"votableb2": "binary2",
			"votabletd": "td",
		}.get(format, "td")

		oe = None
		if getattr(res, "setLimit", None) is not None:
			oe = votable.OverflowElement(res.setLimit,
				votable.V.INFO(name="QUERY_STATUS", value="OVERFLOW"))
		ctx = votablewrite.VOTableContext(
			tablecoding=enc,
			acquireSamples=False, 
			overflowElement=oe)
		votablewrite.writeAsVOTable(res, outF, ctx)
	else:
		formats.formatData(format, res, outF, acquireSamples=False)


def runTAPQuery(query, timeout, connection, tdsForUploads, maxrec):
	"""executes a TAP query and returns the result in a data instance.
	"""
# Some of this replicates functionality from adqlglue.  We should probably
# move the implementation there to what's done here.
	try:
		pgQuery, tableTrunk = adqlglue.morphADQL(query,
			tdsForUploads=tdsForUploads, externalLimit=maxrec)
		base.ui.notifyInfo("Sending to postgres: %s"%repr(pgQuery))
		
		result = rsc.QueryTable(tableTrunk.tableDef, pgQuery, connection)
		# XXX Hack: this is a lousy fix for postgres' seqscan love with
		# limit.  See if we still want this with newer postgres...
		result.configureConnection([("enable_seqscan", False)])
		result.setTimeout(timeout)
	except:
		adqlglue.mapADQLErrors(*sys.exc_info())

	# copy over info metas as applicable (result will receive more info
	# metas later that will then obscure infos from tableTrunk)
	for infoMeta in tableTrunk.iterMeta("info"):
		result.addMeta("info", infoMeta)
	result.setMetaParent(tableTrunk)

	return result


def _ingestUploads(uploads, connection):
	tds = []
	for destName, src in uploads:
		if isinstance(src, tap.LocalFile):
			srcF = open(src.fullPath)
		else:
			try:
				srcF = utils.urlopenRemote(src)
			except IOError, ex:
				raise base.ui.logOldExc(
					base.ValidationError("Upload '%s' cannot be retrieved"%(
					src), "UPLOAD", hint="The I/O operation failed with the message: "+
					str(ex)))
		if valuemappers.needsQuoting(destName):
			raise base.ValidationError("'%s' is not a valid table name on"
				" this site"%destName, "UPLOAD", hint="It either contains"
				" non-alphanumeric characters or conflicts with an ADQL"
				" reserved word.  Quoted table names are not supported"
				" at this site.")
		uploadedTable = votableread.uploadVOTable(destName, srcF, connection,
				nameMaker=votableread.AutoQuotedNameMaker())
		if uploadedTable is not None:
			tds.append(uploadedTable.tableDef)
		srcF.close()
	return tds


def _noteWorkerPID(conn):
	"""stores conn's worker PID in _WORKER_PID.
	"""
	global _WORKER_PID
	curs = conn.cursor()
	curs.execute("SELECT pg_backend_pid()")
	_WORKER_PID = curs.fetchall()[0][0]
	curs.close()


def _hangIfMagic(jobId, parameters, timeout):
# Test intrumentation. There are more effective ways to DoS me.
	if parameters.get("query")=="JUST HANG around":
		time.sleep(timeout)
		with tap.workerSystem.changeableJob(jobId) as job:
			job.change(phase=uws.COMPLETED,
				endTime=datetime.datetime.utcnow())
		sys.exit()


def getQTableFromJob(parameters, jobId, queryProfile, timeout):
	"""returns a QueryTable for a TAP job.
	"""
	query, maxrec = _parseTAPParameters(jobId, parameters)
	connectionForQuery = base.getDBConnection(queryProfile)
	try:
		_noteWorkerPID(connectionForQuery)
	except: # Don't fail just because we can't kill workers
		base.ui.notifyError(
			"Could not obtain PID for the worker, job %s"%jobId)
	tdsForUploads = _ingestUploads(parameters.get("upload", ""), 
		connectionForQuery)

	base.ui.notifyInfo("taprunner executing %s"%query)
	return runTAPQuery(query, timeout, connectionForQuery,
		tdsForUploads, maxrec)


def runTAPJobNoState(parameters, jobId, queryProfile, timeout):
	"""executes a TAP job defined by parameters and writes the
	result to the job's working directory.
	
	This does not do state management.  Use runTAPJob if you need it.
	"""
	_hangIfMagic(jobId, parameters, timeout)
	# The following makes us bail out if a bad format was passed -- no
	# sense spending the CPU on executing the query then, so we get the
	# format here.
	defaultFormat = "votable"
	if base.getConfig("ivoa", "votDefaultEncoding")=="td":
		defaultFormat = "votable/td"

	format = normalizeTAPFormat(parameters.get("format", defaultFormat))

	res = _makeDataFor(getQTableFromJob(
		parameters, jobId, queryProfile, timeout))

	try:
		job = tap.workerSystem.getJob(jobId)
		destF = job.openResult(
			formats.getMIMEFor(format, job.parameters.get("format")), "result")
		writeResultTo(format, res, destF)
		destF.close()
	except Exception:
		# DB errors can occur here since we're streaming directly from
		# the database.
		svcs.mapDBErrors(*sys.exc_info())
	# connectionForQuery closed by QueryTable


def runTAPJob(jobId, queryProfile="untrustedquery"):
	"""executes a TAP job defined by parameters and job id.
	"""
	with tap.workerSystem.changeableJob(jobId) as job:
		# actually, job should already be in executing when we see this,
		# but it should be ok for clients to let us set it
		job.change(phase=uws.EXECUTING,
			startTime=datetime.datetime.utcnow())
		timeout = job.executionDuration
		parameters = job.parameters
	try:
		runTAPJobNoState(parameters, jobId, queryProfile, timeout)
	except Exception, ex:
		base.ui.notifyError("While executing TAP job %s: %s"%(jobId, ex))
		tap.workerSystem.changeToPhase(jobId, uws.ERROR, ex)
	else:
		tap.workerSystem.changeToPhase(jobId, uws.COMPLETED, None)


############### CLI


def setINTHandler(jobId):
	"""installs a signal handler that pushes our job to aborted on SIGINT.
	"""
	import signal

	def handler(signo, frame):
		global EXIT_PLEASE
		EXIT_PLEASE = True

	signal.signal(signal.SIGINT, handler)


def _killWorker(jobId):
	"""tries to kill the postgres worker for this job.
	"""
	with tap.workerSystem.changeableJob(jobId) as wjob:
		wjob.change(phase=uws.ABORTED)

	if _WORKER_PID:
		base.ui.notifyInfo("Trying to abort %s, wpid %s"%(
			jobId, _WORKER_PID))
		with base.getAdminConn() as conn:
			curs = conn.cursor()
			curs.execute("SELECT pg_cancel_backend(%d)"%_WORKER_PID)
			curs.close()


def joinInterruptibly(t, jobId):
	while True: 
		t.join(timeout=0.5)
		if not t.isAlive():
			return
		if EXIT_PLEASE:
			_killWorker(jobId)
			sys.exit(2)



def _runInThread(target, jobId):
	# The standalone tap runner must run the query in a thread since
	# it must be able to react to a SIGINT.
	import threading
	t = threading.Thread(target=target)
	t.setDaemon(True)
	t.start()
	try:
		joinInterruptibly(t, jobId)
	except (SystemExit, Exception):
		# give us the thread a chance to quit cleanly
		t.join(1)
		raise


def parseCommandLine():
	from optparse import OptionParser
	parser = OptionParser(usage="%prog <jobid>",
		description="runs the TAP job with <jobid> from the UWS table.")
	opts, args = parser.parse_args()
	if len(args)!=1:
		parser.print_help(file=sys.stderr)
		sys.exit(1)
	return opts, args[0]


def main():
	"""causes the execution of the job with jobId sys.argv[0].
	"""
	# there's a problem in CLI behaviour in that if anything goes wrong in 
	# main, a job that may have been created will remain QUEUED forever.
	# There's little we can do about that, though, since we cannot put
	# a job into ERROR when we don't know its id or cannot get it from the DB.
	try:
		base.DEBUG = False
		opts, jobId = parseCommandLine()
		setINTHandler(jobId)
		try:
			_runInThread(lambda: runTAPJob(jobId), jobId)
			base.ui.notifyInfo("taprunner for %s finished"%jobId)
		except SystemExit:
			pass
		except uws.JobNotFound: # someone destroyed the job before I was done
			errmsg = "Giving up non-existing TAP job %s."%jobId
			sys.stderr.write(errmsg+"\n")
			base.ui.notifyInfo(errmsg)
		except Exception, ex:
			base.ui.notifyError("taprunner %s major failure"%jobId)
			# try to push job into the error state -- this may well fail given
			# that we're quite hosed, but it's worth the try
			with tap.workerSystem.changeableJob(jobId) as wjob:
				wjob.changeToPhase(uws.ERROR, ex)
			raise
	finally:
		pass
