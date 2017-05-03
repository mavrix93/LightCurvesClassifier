"""
A simple client of OAI-http.

This includes both some high-level functions and rudimentary parsers
that can serve as bases for more specialized parsers.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import urllib
from xml import sax


from gavo import base
from gavo import utils


class FailedQuery(Exception):
	pass


class NoRecordsMatch(Exception):
	pass


class OAIErrorMixin(object):
	def _end_error(self, name, attrs, content):
		if attrs["code"]=="noRecordsMatch":
			raise NoRecordsMatch()
		raise FailedQuery("Registry bailed with code %s, value %s"%(
			attrs["code"], content))


class IdParser(utils.StartEndHandler, OAIErrorMixin):
	"""A parser for simple OAI-PMH headers.

	Records end up as a list of dictionaries in the recs attribute.
	"""
	resumptionToken = None

	def __init__(self, initRecs=None):
		utils.StartEndHandler.__init__(self)
		if initRecs is None:
			self.recs = []
		else:
			self.recs = initRecs

	def getResult(self):
		return self.recs

	def _end_identifier(self, name, attrs, content):
		self.recs[-1]["id"] = content
	
	def _end_datestamp(self, name, attrs, content):
		try:
			self.recs[-1]["date"] = utils.parseISODT(content)
		except ValueError:  # don't fail just because of a broken date
			self.recs[-1]["date"] = None
	
	def _start_header(self, name, attrs):
		self.recs.append({})

	def _end_resumptionToken(self, name, attrs, content):
		if content.strip():
			self.resumptionToken = content


class RecordParser(IdParser, OAIErrorMixin):
	"""A simple parser for ivo_vor records.
	"""
	def _end_title(self, name, attrs, content):
		if self.getParentTag()=="Resource":
			self.recs[-1][name] = content

	def _end_name(self, name, attrs, content):
		if self.getParentTag()=="creator":
			self.recs[-1].setdefault(name, []).append(content)

	def _end_subject(self, name, attrs, content):
		self.recs[-1].setdefault(name, []).append(content)

	def _handleContentChild(self, name, attrs, content):
		if self.getParentTag()=="content":
			self.recs[-1][name] = content

	_end_description = _end_source = _end_referenceURL = \
		_handleContentChild

	def _end_datestamp(self, name, attrs, content):
		# nuke IdParser implementation, we take our date from ri:Resource
		pass

	def _startResource(self, name, attrs):
		self.recs.append({})

	def _end_Resource(self, name, attrs, content):
		self.recs[-1]["date"] = utils.parseISODT(attrs["updated"])

	def _end_accessURL(self, name, attrs, content):
		self.recs[-1].setdefault(name, []).append(content)


class ServerProperties(object):
	"""A container for what an OAI-PMH server gives in response to
	identify.
	"""
	repositoryName = None
	baseURL = None
	protocolVersion = None
	adminEmails = ()
	earliestDatestamp = None
	deletedRecord = None
	granularity = None
	repositoryName = None
	compressions = ()

	def __init__(self):
		self.adminEmails = []
		self.compressions = []
		self.descriptions = []

	def set(self, name, value):
		setattr(self, name, value)
	
	def add(self, name, value):
		getattr(self, name).append(value)


class IdentifyParser(utils.StartEndHandler, OAIErrorMixin):
	"""A parser for the result of the identify operation.

	The result (an instance of ServerProperties) is in the serverProperties
	attribute.
	"""
	resumptionToken = None

	def getResult(self):
		return self.serverProperties

	def _start_Identify(self, name, attrs):
		self.serverProperties = ServerProperties()

	def _endListThing(self, name, attrs, content):
		self.serverProperties.add(name+"s", content.strip())

	_end_adminEmail = _end_compression \
		= _endListThing

	def _endStringThing(self, name, attrs, content):
		self.serverProperties.set(name, content.strip())

	_end_repositoryName = _end_baseURL = _end_protocolVersion \
		= _end_granularity = _end_deletedRecord = _end_earliestDatestamp \
		= _end_repositoryName = _endStringThing


class OAIQuery(object):
	"""A container for queries to OAI interfaces.

	Construct it with the oai endpoint and the OAI verb, plus some optional
	query attributes.  If you want to retain or access the raw responses
	of the server, pass a contentCallback function -- it will be called
	with a byte string containing the payload of the server response if
	it was parsed successfully.  Error responses cannot be obtained in
	this way.

	The OAIQuery is constructed with OAI-PMH parameters (verb, startDate,
	endDate, set, metadataPrefix; see the OAI-PMH docs for what they mean,
	only verb is mandatory).  In addition, you can pass granularity,
	which is the granularity
	"""
	startDate = None
	endDate = None
	set = None
	registry = None
	metadataPrefix = None

	# maxRecords is mainly used in test_oai; that's why there's no
	# constructor parameter for it
	maxRecords = None

	def __init__(self, registry, verb, startDate=None, endDate=None, set=None,
			metadataPrefix="ivo_vor", contentCallback=None, 
			granularity=None):
		self.registry = registry
		self.verb, self.set = verb, set
		self.startDate, self.endDate = startDate, endDate
		self.metadataPrefix = metadataPrefix
		self.contentCallback = contentCallback
		self.granularity = granularity
		if not self.granularity:
			self.granularity = "YYYY-MM-DD"

	def getKWs(self, **moreArgs):
		"""returns a dictionary containing query keywords for OAI interfaces
		from what's specified on the command line.
		"""
		kws = {"verb": self.verb} 
		if self.metadataPrefix:
			kws["metadataPrefix"] = self.metadataPrefix
		kws.update(moreArgs)
		
		if self.granularity=='YY-MM-DD':
			dateFormat = "%Y-%m-%d"
		else:
			dateFormat = "%Y-%m-%dT%H:%M:%SZ"
		if self.startDate:
			kws["from"] = self.startDate.strftime(dateFormat)
		if self.endDate:
			kws["until"] = self.endDate.strftime(dateFormat)

	 	if self.set:
			kws["set"] = self.set
		if self.maxRecords:
			kws["maxRecords"] = str(self.maxRecords)

		if "resumptionToken" in kws:
			kws = {"resumptionToken": kws["resumptionToken"],
				"verb": kws["verb"]}
		return kws

	def doHTTP(self, **moreArgs):
		"""returns the result of parsing the current query plus
		moreArgs to the current registry.

		The result is returned as a string.
		"""
		srcURL = self.registry.rstrip("?"
			)+"?"+self._getOpQS(**self.getKWs(**moreArgs))
		base.ui.notifyInfo("OAI query %s"%srcURL)
		f = utils.urlopenRemote(srcURL)
		res = f.read()
		f.close()
		return res

	def _getOpQS(self, **args):
		"""returns a properly quoted HTTP query part from its (keyword) arguments.
		"""
		# we don't use urllib.urlencode to not encode empty values like a=&b=val
		qString = "&".join("%s=%s"%(k, urllib.quote(v)) 
			for k, v in args.iteritems() if v)
		return "%s"%(qString)

	def talkOAI(self, parserClass):
		"""processes an OAI dialogue for verb using the IdParser-derived 
		parserClass.
		"""
		res = self.doHTTP(verb=self.verb)
		handler = parserClass()
		try:
			sax.parseString(res, handler)
			if self.contentCallback:
				self.contentCallback(res)
		except NoRecordsMatch:
			return []
		oaiResult = handler.getResult()

		while handler.resumptionToken is not None:
			resumptionToken = handler.resumptionToken
			handler = parserClass(oaiResult)
			try:
				res = self.doHTTP(metadataPrefix="ivo_vor", verb=self.verb,
					resumptionToken=resumptionToken)
				sax.parseString(res, handler)
				if self.contentCallback:
					self.contentCallback(res)
			except NoRecordsMatch:
				break

		return oaiResult


def getIdentifiers(registry, startDate=None, endDate=None, set=None,
		granularity=None):
	"""returns a list of "short" records for what's in the registry specified
	by args.
	"""
	q = OAIQuery(registry, verb="ListIdentifiers", startDate=startDate,
		endDate=endDate, set=set)
	return q.talkOAI(IdParser)


def getRecords(registry, startDate=None, endDate=None, set=None,
		granularity=None):
	"""returns a list of "long" records for what's in the registry specified
	by args.

	parser should be a subclass of RecordParser; otherwise, you'll miss
	resumption and possibly other features.
	"""
	q = OAIQuery(registry, verb="ListRecords", startDate=startDate,
		endDate=endDate, set=set, granularity=granularity)
	return q.talkOAI(RecordParser)


def getServerProperties(registry):
	"""returns a ServerProperties instance for registry.

	In particular, you can retrieve the granularity argument that
	actually matches the registry from the result's granularity attribute.
	"""
	q = OAIQuery(registry, verb="Identify", metadataPrefix=None)
	return q.talkOAI(IdentifyParser)
