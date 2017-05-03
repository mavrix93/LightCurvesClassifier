"""
An interface to querying TAP servers (i.e., a TAP client).
"""

#c Copyright 2008-2016, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import httplib
import socket
import time
import traceback
import urllib
import urlparse
from cStringIO import StringIO
from email.Message import Message
from email.MIMEMultipart import MIMEMultipart
from xml import sax

from gavo import utils
from gavo.votable import parser
from gavo.votable.model import VOTable as V


# Ward against typos
PENDING = "PENDING"
QUEUED = "QUEUED"
EXECUTING = "EXECUTING"
COMPLETED = "COMPLETED"
ERROR = "ERROR"
ABORTED = "ABORTED"
UNKNOWN = "UNKNOWN"


debug = False


class Error(utils.Error):
	"""The base class for all TAP-related exceptions.
	"""


class ProtocolError(Error):
	"""is raised when the remote server violated the local assumptions.
	"""


class WrongStatus(ProtocolError):
	"""is raised when request detects the server returned an invalid
	status.

	These are constructed with the status returnd (available as
	foundStatus) data payload of the response (available as payload).
	"""
	def __init__(self, msg, foundStatus, payload, hint=None):
		ProtocolError.__init__(self, msg, hint)
		self.args = [msg, foundStatus, payload, hint]
		self.payload, self.foundStatus = payload, foundStatus


class RemoteError(Error):
	"""is raised when the remote size signals an error.

	The content of the remote error document can be retrieved in the 
	remoteMessage attribute.
	"""
	def __init__(self, remoteMessage):
		self.remoteMessage = remoteMessage
		Error.__init__(self, 
			"Remote: "+remoteMessage,
			hint="This means that"
			" something in your query was bad according to the server."
			"  Details may be available in the Exceptions' remoteMessage"
			" attribute")
		self.args = [remoteMessage]

	def __str__(self):
		return self.remoteMessage


class RemoteAbort(Error):
	"""is raised by certain check functions when the remote side has aborted
	the job.
	"""
	def __init__(self):
		Error.__init__(self, "Aborted")
		self.args = []
	
	def __str__(self):
		return "The remote side has aborted the job"


class NetworkError(Error):
	"""is raised when a generic network error happens (can't connect,...)
	"""


class _FormData(MIMEMultipart):
	"""is a container for multipart/form-data encoded messages.

	This is usually used for file uploads.
	"""
	def __init__(self):
		MIMEMultipart.__init__(self, "form-data")
		self.set_param("boundary", "========== bounda r y 930 ")
		self.epilogue = ""
	
	def addFile(self, paramName, fileName, data):
		"""attaches the contents of fileName under the http parameter name
		paramName.
		"""
		msg = Message()
		msg.set_type("application/octet-stream")
		msg["Content-Disposition"] = "form-data"
		msg.set_param("name", paramName, "Content-Disposition")
		msg.set_param("filename", fileName, "Content-Disposition")
		msg.set_payload(data)
		self.attach(msg)

	def addParam(self, paramName, paramVal):
		"""adds a form parameter paramName with the (string) value paramVal
		"""
		msg = Message()
		msg["Content-Disposition"] = "form-data"
		msg.set_param("name", paramName, "Content-Disposition")
		msg.set_payload(paramVal)
		self.attach(msg)

	def forHTTPUpload(self):
		"""returns a string serialisation of this message suitable for HTTP
		upload.

		This is as_string, except we're introducing crlfs when it seems
		the line separator is just an lf.
		"""
		data = self.as_string()
		if not "\r\n" in data:
			data = data.replace("\n", "\r\n")
		return data

	@classmethod
	def fromDict(cls, dict):
		self = cls()
		for key, value in dict.iteritems():
			self.addParam(key, value)
		return self
		

def _getErrorInfo(votString):
	"""returns the message from a TAP error VOTable.

	if votString is not a TAP error VOTable, it is returned verbatim.

	TODO: For large responses, this may take a while.  It's probably
	not worth it in such cases.  Or at all.  Maybe we should  hunt
	for the INFO somewhere else?
	"""
	try:
		for el in parser.parseString(votString, watchset=[V.INFO]):
			if isinstance(el, V.INFO):
				if el.name=="QUERY_STATUS" and el.value=="ERROR":
					return el.text_
			else:
				# it's data, which we want to skip quickly
				for _ in el: pass
	except Exception:
		# votString's not a suitable VOTable, fall through to return votString
		pass
	return votString


def _makeFlatParser(parseFunc):
	"""returns a "parser" class for _parseWith just calling a function on a string.

	_parseWith is designed for utils.StartEndParsers, but it's convenient
	to use it when there's no XML in the responses as well.

	So, this class wraps a simple function into a StartEndParser-compatible
	form.
	"""
	class FlatParser(object):
		def parseString(self, data):
			self.result = parseFunc(data)
		def getResult(self):
			return self.result
	return FlatParser


def _parseWith(parser, data):
	"""uses the utils.StartEndParser-compatible parser to parse the string data.
	"""
	try:
		parser.parseString(data)
		return parser.getResult()
	except (ValueError, IndexError, sax.SAXParseException):
		if debug:
			traceback.print_exc()
			f = open("server_response", "w")
			f.write(data)
			f.close()
		raise ProtocolError("Malformed response document.", hint=
			"If debug was enabled, you will find the server response in"
			" the file server_response.")


class _PhaseParser(utils.StartEndHandler):
	"""A parser accepting both plain text and XML replies.

	Of course, the XML replies are against the standard, but -- ah, well.
	"""
	def _end_phase(self, name, attrs, content):
		self.result = content
	
	def parseString(self, data):
		if data.strip().startswith("<"): # XML :-)
			utils.StartEndHandler.parseString(self, data)
		else:
			self.result = str(data).strip()
	
	def getResult(self):
		return self.result


class _QuoteParser(utils.StartEndHandler):
	quote = None
	def parseDate(self, literal):
		val = None
		if literal and literal!="NULL":
			val = utils.parseISODT(literal)
		return val

	def _end_quote(self, name, attrs, content):
		self.quote = self.parseDate(content.strip())

	def parseString(self, data):
		data = data.strip()
		if data.startswith("<"): # XML :-)
			utils.StartEndHandler.parseString(self, data)
		else:
			self.quote = self.parseDate(data)

	def getResult(self):
		return self.quote


class _CaselessDictionary(dict):
	"""A dictionary that only has lower-case keys but treats keys in any
	capitalization as equivalent.
	"""
	def __contains__(self, key):
		dict.__contains__(self, key.lower())
	
	def __getitem__(self, key):
		return dict.__getitem__(self, key.lower())
	
	def __setitem__(self, key, value):
		dict.__setitem__(self, key.lower(), value)
	
	def __delitem__(self, key):
		dict.__delitem__(self, key.lower())
	

class _ParametersParser(utils.StartEndHandler):
	def _initialize(self):
		self.parameters = _CaselessDictionary()

	def _end_parameter(self, name, attrs, content):
		self.parameters[attrs["id"]] = content
	
	def getResult(self):
		return self.parameters


class _ResultsParser(utils.StartEndHandler):
	def _initialize(self):
		self.results = []

	def _end_result(self, name, attrs, content):
		attrs = self.getAttrsAsDict(attrs)
		self.results.append(UWSResult(attrs["href"],
			attrs.get("id"), attrs.get("type", "simple")))
	
	def getResult(self):
		return self.results


class _InfoParser(_ParametersParser, _ResultsParser):
	def _initialize(self):
		self.info = {}
		_ParametersParser._initialize(self)
		_ResultsParser._initialize(self)
	
	def _end_jobId(self, name, attrs, content):
		self.info[name] = content
	
	_end_phase = _end_jobId
	
	def _end_executionDuration(self, name, attrs, content):
		self.info[name] = float(content)
	
	def _end_destruction(self, name, attrs, content):
		self.info[name] = utils.parseISODT(content)
	
	def _end_job(self,name, attrs, content):
		self.info["results"] = self.results
		self.info["parameters"] = self.parameters
	
	def getResult(self):
		return self.info
	


class _AvailabilityParser(utils.StartEndHandler):
# VOSI
	available = None
	def _end_available(self, name, attrs, content):
		content = content.strip()
		if content=="true":
			self.available = True
		elif content=="false":
			self.available = False

	def getResult(self):
		return self.available


def _pruneAttrNS(attrs):
	return dict((k.split(":")[-1], v) for k,v in attrs.items())


class _CapabilitiesParser(utils.StartEndHandler):
# VOSI; each capability is a dict with at least a key interfaces.
# each interface is a dict with key type (namespace prefix not expanded; 
# change that?), accessURL, and use.
	def __init__(self):
		utils.StartEndHandler.__init__(self)
		self.capabilities = []

	def _start_capability(self, name, attrs):
		self.curCap = {"interfaces": []}
		self.curCap["standardID"] = attrs.get("standardID")

	def _end_capability(self, name, attrs, content):
		self.capabilities.append(self.curCap)
		self.curCap = None

	def _start_interface(self, name, attrs):
		attrs = _pruneAttrNS(attrs)
		self.curInterface = {"type": attrs["type"], "role": attrs.get("role")}

	def _end_interface(self,name, attrs, content):
		self.curCap["interfaces"].append(self.curInterface)
		self.curInterface = None

	def _end_accessURL(self, name, attrs, content):
		self.curInterface["accessURL"] = content.strip()
		self.curInterface["use"] = attrs.get("use")
	
	def getResult(self):
		return self.capabilities


class _TablesParser(utils.StartEndHandler):
# VOSI
	def __init__(self):
		utils.StartEndHandler.__init__(self)
		self.tables = []
		self.curCol = None
	
	def _start_table(self, name, attrs):
		self.tables.append(V.TABLE())
	
	def _start_column(self, name, attrs):
		self.curCol = V.FIELD()

	def _end_column(self, name, attrs, content):
		self.tables[-1][self.curCol]
		self.curCol = None

	def _end_description(self, attName, attrs, content):
		if self.getParentTag()=="table":
			destObj = self.tables[-1]
		elif self.getParentTag()=="column":
			destObj = self.curCol
		else:
			# name/desc of something else -- ignore
			return
		destObj[V.DESCRIPTION[content]]

	def _endColOrTableAttr(self, attName, attrs, content):
		if self.getParentTag()=="table":
			destObj = self.tables[-1]
		elif self.getParentTag()=="column":
			destObj = self.curCol
		else:
			# name/desc of something else -- ignore
			return
		destObj(**{str(attName): content.strip()})
	
	_end_name = _endColOrTableAttr
	
	def _endColAttr(self, attName, attrs, content):
		self.curCol(**{str(attName): content.strip()})

	_end_unit = _end_ucd = _endColAttr
	
	def _end_dataType(self, attName, attrs, content):
		self.curCol(datatype=content.strip())
		if attrs.has_key("arraysize"):
			self.curCol(arraysize=attrs["arraysize"])

	def getResult(self):
		return self.tables


class UWSResult(object):
	"""a container type for a result returned by an UWS service.

	It exposes id, href, and type attributes.
	"""
	def __init__(self, href, id=None, type=None):
		self.href, self.id, self.type = href, id, type


class LocalResult(object):
	def __init__(self, data, id, type):
		self.data, self.id, self.type = data, id, type


def _canUseFormEncoding(params):
	"""returns true if userParams can be transmitted in a 
	x-www-form-urlencoded payload.
	"""
	for val in params.values():
		if not isinstance(val, basestring):
			return False
	return True


def request(host, path, data="", customHeaders={}, method="GET",
		expectedStatus=None, followRedirects=False, setResponse=None,
		timeout=None):
	"""returns a HTTPResponse object for an HTTP request to path on host.

	This function builds a new connection for every request.

	On the returned object, you cannot use the read() method.	Instead
	any data returned by the server is available in the data attribute.

	data usually is a byte string, but you can also pass a dictionary
	which then will be serialized using _FormData above.

	You can set followRedirects to True.  This means that the 
	303 "See other" codes that many UWS action generate will be followed 
	and the document at the other end will be obtained.  For many
	operations this will lead to an error; only do this for slightly
	broken services.

	In setResponse, you can pass in a callable that is called with the
	server response body as soon as it is in.  This is for when you want
	to store the response even if request raises an error later on
	(i.e., for sync querying).
	"""
	headers = {"connection": "close",
		"user-agent": "Python TAP library http://soft.g-vo.org/subpkgs"}

	if not isinstance(data, basestring):
		if _canUseFormEncoding(data):
			data = urllib.urlencode(data)
			headers["Content-Type"] = "application/x-www-form-urlencoded"

		else:
			form = _FormData.fromDict(data)
			data = form.forHTTPUpload()
			headers["Content-Type"] = form.get_content_type()+'; boundary="%s"'%(
					form.get_boundary())
	headers["Content-Length"] = len(data)
	headers.update(customHeaders)

	try:
		try:
			conn = httplib.HTTPConnection(host, timeout=timeout)
		except TypeError: # probably python<2.6, no timeout support
			conn = httplib.HTTPConnection(host)
		conn.request(method, path, data, headers)
	except (socket.error, httplib.error), ex:
		raise NetworkError("Problem connecting to %s (%s)"%
			(host, str(ex)))

	resp = conn.getresponse()
	resp.data = resp.read()
	if setResponse is not None:
		setResponse(resp.data)
	conn.close()

	if ((followRedirects and resp.status==303)
			or resp.status==301
			or resp.status==302):
		parts = urlparse.urlparse(resp.getheader("location"))
		assert parts.scheme=="http"
		return request(parts.netloc, parts.path+'?'+parts.query, 
			data, customHeaders, method, expectedStatus, 
			followRedirects=followRedirects-1)

	if expectedStatus is not None:
		if resp.status!=expectedStatus:
			raise WrongStatus("Expected status %s, got status %s"%(
				expectedStatus, resp.status), resp.status, resp.data)
	return resp


def _makeAtomicValueGetter(methodPath, parser):
# This is for building ADQLTAPJob's properties (phase, etc.)
	def getter(self):
		destURL = self.jobPath+methodPath
		response = request(self.destHost, destURL, expectedStatus=200)
		return _parseWith(parser(), response.data)
	return getter


def _makeAtomicValueSetter(methodPath, serializer, parameterName):
# This is for building ADQLTAPJob's properties (phase, etc.)
	def setter(self, value):
		destURL = self.jobPath+methodPath
		request(self.destHost, destURL, 
			{parameterName: serializer(value)}, method="POST",
			expectedStatus=303)
	return setter


class _WithEndpoint(object):
	"""A helper class for classes constructed with an ADQL endpoint.
	"""
	def _defineEndpoint(self, endpointURL):
		self.endpointURL = endpointURL.rstrip("/")
		parts = urlparse.urlsplit(self.endpointURL)
		assert parts.scheme=="http"
		self.destHost = parts.hostname
		if parts.port:
			self.destHost = "%s:%s"%(self.destHost, parts.port)
		self.destPath = parts.path
		if self.destPath.endswith("/"):
			self.destPath = self.destPath[:-1]


class ADQLTAPJob(_WithEndpoint):
	"""A facade for an ADQL-based async TAP job.

	Construct it with the URL of the async endpoint and a query.

	Alternatively, you can give the endpoint URL and a jobId as a
	keyword parameter.  This only makes sense if the service has
	handed out the jobId before (e.g., when a different program takes
	up handling of a job started before).
	"""
	def __init__(self, endpointURL, query=None, jobId=None, lang="ADQL", 
			userParams={}, timeout=None):
		self._defineEndpoint(endpointURL)
		self.timeout = timeout
		self.destPath = utils.ensureOneSlash(self.destPath)+"async"
		if query is not None:
			self.jobId, self.jobPath = None, None
			self._createJob(query, lang, userParams)
		elif jobId is not None:
			self.jobId = jobId
		else:
			raise Error("Must construct ADQLTAPJob with at least query or jobId")
		self._computeJobPath()
	
	def _computeJobPath(self):
		self.jobPath = "%s/%s"%(self.destPath, self.jobId)

	def _createJob(self, query, lang, userParams):
		params = {
			"REQUEST": "doQuery",
			"LANG": lang,
			"QUERY": query}
		for k,v in userParams.iteritems():
			params[k] = str(v)
		response = request(self.destHost, self.destPath, params,
			method="POST", expectedStatus=303, timeout=self.timeout)
		# The last part of headers[location] now contains the job id
		try:
			self.jobId = urlparse.urlsplit(
				response.getheader("location", "")).path.split("/")[-1]
		except ValueError:
			raise utils.logOldExc(
				ProtocolError("Job creation returned invalid job id"))

	def delete(self, usePOST=False):
		"""removes the job on the remote side.

		usePOST=True can be used for servers that do not support the DELETE
		HTTP method (a.k.a. "are broken").
		"""
		if self.jobPath is not None:
			if usePOST:
				request(self.destHost, self.jobPath, method="POST",
					data={"ACTION": "DELETE"}, expectedStatus=303, 
					timeout=self.timeout)
			else:
				request(self.destHost, self.jobPath, method="DELETE",
					expectedStatus=303, timeout=self.timeout)

	def start(self):
		"""asks the remote side to start the job.
		"""
		request(self.destHost, self.jobPath+"/phase", 
			{"PHASE": "RUN"}, method="POST", expectedStatus=303, 
			timeout=self.timeout)

	def abort(self):
		"""asks the remote side to abort the job.
		"""
		request(self.destHost, self.jobPath+"/phase", 
			{"PHASE": "ABORT"}, method="POST", expectedStatus=303,
			timeout=self.timeout)

	def raiseIfError(self):
		"""raises an appropriate error message if job has thrown an error or
		has been aborted.
		"""
		phase = self.phase
		if phase==ERROR:
			raise RemoteError(self.getErrorFromServer())
		elif phase==ABORTED:
			raise RemoteAbort()

	def waitForPhases(self, phases, pollInterval=1, increment=1.189207115002721,
			giveUpAfter=None):
		"""waits for the job's phase to become one of the set phases.

		This method polls.  Initially, it does increases poll times
		exponentially with increment until it queries every two minutes.

		The magic number in increment is 2**(1/4.).

		giveUpAfter, if given, is the number of iterations this method will
		do.  If none of the desired phases have been found until then,
		raise a ProtocolError.
		"""
		attempts = 0
		while True:
			curPhase = self.phase 
			if curPhase in phases:
				break
			time.sleep(pollInterval)
			pollInterval = min(120, pollInterval*increment)
			attempts += 1
			if giveUpAfter:
				if attempts>giveUpAfter:
					raise ProtocolError("None of the states in %s were reached"
						" in time."%repr(phases),
					hint="After %d attempts, phase was %s"%(attempts, curPhase))

	def run(self, pollInterval=1):
		"""runs the job and waits until it has finished.

		The function raises an exception with an error message gleaned from the
		server.
		"""
		self.start()
		self.waitForPhases(set([COMPLETED, ABORTED, ERROR]))
		self.raiseIfError()

	executionDuration = property(
		_makeAtomicValueGetter("/executionduration", _makeFlatParser(float)),
		_makeAtomicValueSetter("/executionduration", str, "EXECUTIONDURATION"))

	destruction = property(
		_makeAtomicValueGetter("/destruction", _makeFlatParser(utils.parseISODT)),
		_makeAtomicValueSetter("/destruction", 
			lambda dt: dt.strftime("%Y-%m-%dT%H:%M:%S.000"), "DESTRUCTION"))

	def makeJobURL(self, jobPath):
		return self.endpointURL+"/async/%s%s"%(self.jobId, jobPath)

	def _queryJobResource(self, path, parser):
		# a helper for phase, quote, etc.
		response = request(self.destHost, self.jobPath+path,
			expectedStatus=200, timeout=self.timeout)
		return _parseWith(parser, response.data)

	@property
	def info(self):
		"""returns a dictionary of much job-related information.
		"""
		return self._queryJobResource("", _InfoParser())

	@property
	def phase(self):
		"""returns the phase the job is in according to the server.
		"""
		return self._queryJobResource("/phase", _PhaseParser())

	@property
	def quote(self):
		"""returns the estimate the server gives for the run time of the job.
		"""
		return self._queryJobResource("/quote", _QuoteParser())

	@property
	def owner(self):
		"""returns the owner of the job.
		"""
		return self._queryJobResource("/owner", _makeFlatParser(str)())

	@property
	def parameters(self):
		"""returns a dictionary mapping passed parameters to server-provided
		string representations.

		To set a parameter, use the setParameter function.  Changing the
		dictionary returned here will have no effect.
		"""
		return self._queryJobResource("/parameters", _ParametersParser())

	@property
	def allResults(self):
		"""returns a list of UWSResult instances.
		"""
		return self._queryJobResource("/results", _ResultsParser())

	def getResultURL(self, simple=True):
		"""returns the URL of the ADQL result table.
		"""
		if simple:
			return self.makeJobURL("/results/result")
		else:
			return self.allResults[0].href

	def openResult(self, simple=True):
		"""returns a file-like object you can read the default TAP result off.

		To have the embedded VOTable returned, say
		votable.load(job.openResult()).

		If you pass simple=False, the URL will be taken from the
		service's result list (the first one given there).  Otherwise (the
		default), results/result is used.
		"""
		return urllib.urlopen(self.getResultURL())

	def setParameter(self, key, value):
		request(self.destHost, self.jobPath+"/parameters",
			data={key: value}, method="POST", expectedStatus=303,
			timeout=self.timeout)

	def getErrorFromServer(self):
		"""returns the error message the server gives, verbatim.
		"""
		data = request(self.destHost, self.jobPath+"/error",
			expectedStatus=200, followRedirects=True,
			timeout=self.timeout).data
		return _getErrorInfo(data)

	def addUpload(self, name, data):
		"""adds uploaded tables, either from a file or as a remote URL.

		You should not try to change UPLOAD yourself (e.g., using setParameter).

		Data is either a string (i.e. a URI) or a file-like object (an upload).
		"""
		uploadFragments = []
		form = _FormData()
		if isinstance(data, basestring): # a URI
			assert ',' not in data
			assert ';' not in data
			uploadFragments.append("%s,%s"%(name, data))

		else: # Inline upload, data is a file
			uploadKey = utils.intToFunnyWord(id(data))
			form.addFile(uploadKey, uploadKey, data.read())
			uploadFragments.append("%s,param:%s"%(name, uploadKey))

		form.addParam("UPLOAD", ";".join(uploadFragments))
		request(self.destHost, self.jobPath+"/parameters", method="POST",
			data=form.forHTTPUpload(), expectedStatus=303, 
			customHeaders={"content-type": 
				form.get_content_type()+'; boundary="%s"'%(form.get_boundary())})


class ADQLSyncJob(_WithEndpoint):
	"""A facade for a synchronous TAP Job.

	This really is just a very glorified urllib.urlopen.  Maybe some
	superficial parallels to ADQLTAPJob are useful.

	You can construct it, add uploads, and then start or run the thing.
	Methods that make no sense at all for sync jobs ("phase") silently
	return some more or less sensible fakes.
	"""
	def __init__(self, endpointURL, query=None, jobId=None, lang="ADQL", 
			userParams={}, timeout=None):
		self._defineEndpoint(endpointURL)
		self.query, self.lang = query, lang
		self.userParams = userParams.copy()
		self.result = None
		self._errorFromServer = None
		self.timeout = timeout
	
	def postToService(self, params):
		return request(self.destHost, self.destPath+"/sync", params,
			method="POST", followRedirects=3, expectedStatus=200,
			setResponse=self._setErrorFromServer, timeout=self.timeout)

	def delete(self, usePOST=None):
		# Nothing to delete
		pass
	
	def abort(self):
		"""does nothing.

		You could argue that this could come from a different thread and we
		could try to interrupt the ongoing request.  Well, if you want it,
		try it yourself or ask the author.
		"""

	def raiseIfError(self):
		if self._errorFromServer is not None:
			raise Error(self._errorFromServer)

	def waitForPhases(self, phases, pollInterval=None, increment=None,
			giveUpAfter=None):
		# you could argue that sync jobs are in no phase, but I'd say
		# they are in all of them at the same time:
		return

	def _setErrorFromServer(self, data):
		# this is a somewhat convolved way to get server error messages
		# out of request even when it later errors out.  See the
		# except construct around the postToService call in start()
		#
		# Also, try to interpret what's coming back as a VOTable with an
		# error message; _getErrorInfo is robust against other junk.
		self._errorFromServer = _getErrorInfo(data)

	def start(self):
		params={
			"REQUEST": "doQuery",
			"LANG": self.lang,
			"QUERY": self.query}
		params.update(self.userParams)
		params = dict((k, str(v)) for k,v in params.iteritems())

		try:
			resp = self.postToService(params)
			self.result = LocalResult(resp.data, "TAPResult", resp.getheader(
				"Content-Type"))
		except Exception, msg:
			# do not clear _errorFromServer; but if it's empty, make up one
			# from our exception
			if not self._errorFromServer:
				self._errorFromServer = str(msg)
			raise
		else:
			# all went well, clear error indicator
			self._errorFromServer = None
		return self

	def run(self, pollInterval=None):
		return self.start()

	@property
	def info(self):
		return {}

	@property
	def phase(self):
		return None
	
	@property
	def quote(self):
		return None
	
	@property
	def owner(self):
		return None
	
	@property
	def parameters(self):
		return self.userParameters
	
	@property
	def allResults(self):
		if self.result is None:
			return []
		else:
			return [self.result]

	def openResult(self, simple=True):
		if self.result is None:
			raise Error("No result in so far")
		return StringIO(self.result.data)

	def setParameter(self, key, value):
		self.userParams[key] = value

	def getErrorFromServer(self):
		return self._errorFromServer

	def addUpload(self, name, data):
		raise NotImplementedError("Uploads not yet implemented for sync TAP")
		self.uploads.append((name, data))


class ADQLEndpoint(_WithEndpoint):
	"""A facade for an ADQL endpoint.

	This is only needed for inspecting server metadata (i.e., in general
	only for rather fancy applications).
	"""
	def __init__(self, endpointURL):
		self._defineEndpoint(endpointURL)
	
	def createJob(self, query, lang="ADQL-2.0", userParams={}):
		return ADQLTAPJob(self.endpointURL, query, lang, userParams)

	@property
	def available(self):
		"""returns True, False, or None (undecidable).

		None is returned when /availability gives a 404 (which is legal)
		or the returned document doesn't parse.
		"""
		try:
			response = request(self.destHost, self.destPath+"/availability",
				expectedStatus=200)
			res = _parseWith(_AvailabilityParser(), response.data)
		except WrongStatus:
			res = None
		return res
	
	@property
	def capabilities(self):
		"""returns a dictionary containing some meta info on the remote service.

		Keys to look for include title, identifier, contact (the mail address),
		and referenceURL.

		If the remote server doesn't return capabilities as expected, an
		empty dict is returned.
		"""
		return _parseWith(_CapabilitiesParser(), 
				request(self.destHost, self.destPath+"/capabilities").data)

	@property
	def tables(self):
		"""returns a sequence of table definitions for the tables accessible
		through this service.

		The table definitions come as gavo.votable.Table instances.
		"""
		return _parseWith(_TablesParser(),
				request(self.destHost, self.destPath+"/tables").data)
