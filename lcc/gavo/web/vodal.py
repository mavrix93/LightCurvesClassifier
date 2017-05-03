"""
Support for IVOA DAL and registry protocols.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import datetime

from nevow import appserver
from nevow import inevow

from twisted.internet import defer

from zope.interface import implements

from gavo import base
from gavo import formats
from gavo import registry
from gavo import rscdef
from gavo import rsc
from gavo import svcs
from gavo import utils
from gavo import votable
from gavo.protocols import dali
from gavo.svcs import streaming
from gavo.votable import V
from gavo.web import common
from gavo.web import grend


MS = base.makeStruct


__docformat__ = "restructuredtext en"


class DALRenderer(grend.ServiceBasedPage):
	"""is a base class for renderers for the usual IVOA DAL protocols.

	This is for simple, GET-based DAL renderers (where we allow POST as 
	well).  They work using nevow forms, but with standard-compliant error
	reporting (i.e., in VOTables).

	Since DALRenderer mixes in FormMixin, it always has the form genFrom.
	"""

	implements(inevow.ICanHandleException)

	resultType = base.votableType
	parameterStyle = "pql"
	urlUse = "base"

	def __init__(self, ctx, *args, **kwargs):
		self.reqArgs = inevow.IRequest(ctx).args
		if not "MAXREC" in self.reqArgs:
			self.reqArgs["MAXREC"] = [
				str(base.getConfig("ivoa", "dalDefaultLimit"))]
		# XXX TODO: Do away with _FORMAT in general, move to RESPONSEFORMAT
		self.reqArgs["_FORMAT"] = ["VOTable"]

		# see _writeErrorTable
		self.saneResponseCodes = False
		grend.ServiceBasedPage.__init__(self, ctx, *args, **kwargs)

	@classmethod
	def makeAccessURL(cls, baseURL):
		return "%s/%s?"%(baseURL, cls.name)

	@classmethod
	def isBrowseable(self, service):
		return False

	def renderHTTP(self, ctx):
		queryMeta = svcs.QueryMeta.fromContext(ctx)
		if queryMeta["dbLimit"]==0:
			return self._renderMetadata(ctx, queryMeta)

		else:
			return defer.maybeDeferred(self._runService, ctx, queryMeta
				).addErrback(self._handleInputErrors, ctx
				).addErrback(self._handleRandomFailure, ctx)

	def _getMetadataData(self, queryMeta):
		"""returns a SIAP-style metadata data item.
		"""
		# XXX TODO: build VOTable directly (rather than from data)
		inputFields = []
		for param in self.service.getInputKeysFor(self):
			if param.type=="file":
				inputFields.append(dali.getUploadKeyFor(param))
			else:
				inputFields.append(param.change(name="INPUT:"+param.name))
		inputTable = MS(rscdef.TableDef, columns=inputFields)
		outputTable = MS(rscdef.TableDef, columns=
			self.service.getCurOutputFields(queryMeta), id="result")

		nullRowmaker = MS(rscdef.RowmakerDef)
		dataDesc = MS(rscdef.DataDescriptor, makes=[
			MS(rscdef.Make, table=inputTable, role="parameters", 
				rowmaker=nullRowmaker),
			MS(rscdef.Make, table=outputTable, rowmaker=nullRowmaker)],
			parent_=self.service.rd)

		data = rsc.makeData(dataDesc)
		data.tables["result"].votCasts = self._outputTableCasts
		data.setMeta("_type", "results")
		data.addMeta("info", base.makeMetaValue("OK", type="info", 
			infoName="QUERY_STATUS", infoValue="OK"))
		
		return data

	def _renderMetadata(self, ctx, queryMeta):
		metaData = self._getMetadataData(queryMeta)
		request = inevow.IRequest(ctx)
		request.setHeader("content-type", "text/xml")
		votLit = formats.getFormatted("votabletd1.1", metaData)
		# maybe provide a better way to attach stylesheet info?
		splitPos = votLit.find("?>")+2
		return votLit[:splitPos]+("<?xml-stylesheet href='/static"
				"/xsl/meta-votable-to-html.xsl' type='text/xsl'?>"
			)+votLit[splitPos:]

	def _runService(self, ctx, queryMeta):
		dali.mangleUploads(self.reqArgs)
		return self.runService(inevow.IRequest(ctx).args, queryMeta
			).addCallback(self._formatOutput, ctx)

	def _writeErrorTable(self, ctx, errmsg, code=200, queryStatus="ERROR"):
		request = inevow.IRequest(ctx)

		# Unfortunately, most legacy DAL specs say the error messages must
		# be delivered with a 200 response code.  I hope this is going
		# to change at some point, so I let renderers order sane response
		# codes.
		if not self.saneResponseCodes:
			request.setResponseCode(code)
		result = self._makeErrorTable(ctx, errmsg, queryStatus)
		request.setHeader("content-type", base.votableType)
		votable.write(result, request)
		return "\n"

	def _formatOutput(self, data, ctx):
		data.original.addMeta("info", base.makeMetaValue(type="info", 
			infoName="QUERY_STATUS", infoValue="OK"))

		request = inevow.IRequest(ctx)
		if "RESPONSEFORMAT" in request.args:
			# This is our DALI RESPONSEFORMAT implementation; to declare
			# this, use <STREAM source="//pql#RESPONSEFORMAT"/>
			# in the service body.
			destFormat = request.args["RESPONSEFORMAT"][0]
			request.setHeader("content-type", formats.getMIMEFor(
				destFormat, destFormat))

			# TBD: format should know extensions for common formats
			request.setHeader('content-disposition', 
				'attachment; filename="result.dat"')

			def writeStuff(outputFile):
				formats.formatData(destFormat,
					data.original, outputFile, acquireSamples=False)

			return streaming.streamOut(writeStuff, request)

		else:
			# default behaviour: votable.
			request.setHeader('content-disposition', 
				'attachment; filename="votable.xml"')
			request.setHeader("content-type", self.resultType)
			return streaming.streamVOTable(request, data)

	def _handleRandomFailure(self, failure, ctx):
		if not isinstance(failure, base.ValidationError):
			base.ui.notifyFailure(failure)
		return self._writeErrorTable(ctx,
			"Unexpected failure, error message: %s"%failure.getErrorMessage(),
			500)
	
	def _handleInputErrors(self, failure, ctx):
		queryStatus = "ERROR"

		if isinstance(failure.value, base.EmptyData):
			inevow.IRequest(ctx).setResponseCode(400)
			queryStatus = "EMPTY"

		return self._writeErrorTable(ctx, failure.getErrorMessage(),
			queryStatus=queryStatus)


class SCSRenderer(DALRenderer):
	"""
	A renderer for the Simple Cone Search protocol.

	These do their error signaling in the value attribute of an
	INFO child of RESOURCE.

	You must set the following metadata items on services using
	this renderer if you want to register them:

	* testQuery.ra, testQuery.dec -- A position for which an object is present
		within 0.001 degrees.
	"""
	name = "scs.xml"

	def __init__(self, ctx, *args, **kwargs):
		reqArgs = inevow.IRequest(ctx).args
		if not "_DBOPTIONS_LIMIT" in reqArgs:
			reqArgs["_DBOPTIONS_LIMIT"] = [
				str(base.getConfig("ivoa", "dalDefaultLimit")*10)]
		if "_VOTABLE_VERSION" not in reqArgs:
			reqArgs["_VOTABLE_VERSION"] = ["1.1"]
		DALRenderer.__init__(self, ctx, *args, **kwargs)

	def _writeErrorTable(self, ctx, msg, code=200, queryStatus="ERROR"):
		request = inevow.IRequest(ctx)
		request.setHeader("content-type", base.votableType)
		votable.write(V.VOTABLE11[
			V.DESCRIPTION[base.getMetaText(self.service, "description")],
			V.INFO(ID="Error", name="Error",
					value=str(msg).replace('"', '\\"'))], request)
		request.write("\n")
		return ""

	def _formatOutput(self, data, ctx):
		"""makes output SCS 1.02 compatible or causes the service to error out.

		This comprises mapping meta.id;meta.main to ID_MAIN and
		pos.eq* to POS_EQ*.
		"""
		ucdCasts = {
			"meta.id;meta.main": {"ucd": "ID_MAIN", "datatype": "char", 
				"arraysize": "*"},
			"pos.eq.ra;meta.main": {"ucd": "POS_EQ_RA_MAIN", 
				"datatype": "double"},
			"pos.eq.dec;meta.main": {"ucd": "POS_EQ_DEC_MAIN", 
				"datatype": "double"},
		}
		realCasts = {}
		table = data.original.getPrimaryTable()
		for ind, ofield in enumerate(table.tableDef.columns):
			if ofield.ucd in ucdCasts:
				realCasts[ofield.name] = ucdCasts.pop(ofield.ucd)
		if ucdCasts:
			return self._writeErrorTable(ctx, "Table cannot be formatted for"
				" SCS.  Column(s) with the following new UCD(s) were missing in"
				" output table: %s"%', '.join(ucdCasts))

		# allow integers as ID_MAIN [HACK -- this needs to become saner.
		# conditional cast functions?]
		idCol = table.tableDef.getColumnByUCD("meta.id;meta.main")
		if idCol.type in set(["integer", "bigint", "smallint"]):
			realCasts[idCol.name]["castFunction"] = str
		table.votCasts = realCasts

		return DALRenderer._formatOutput(self, data, ctx)


class SIAPRenderer(DALRenderer):
	"""A renderer for a the Simple Image Access Protocol.

	These have errors in the content of an info element, and they support
	metadata queries.

	For registration, services using this renderer must set the following
	metadata items:

		- sia.type -- one of Cutout, Mosaic, Atlas, Pointed, see SIAP spec
	
	You should set the following metadata items:

		- testQuery.pos.ra, testQuery.pos.dec -- RA and Dec for a query that
			yields at least one image
		- testQuery.size.ra, testQuery.size.dec -- RoI extent for a query that 
			yields at least one image.
	
	You can set the following metadata items (there are defaults on them
	that basically communicate there are no reasonable limits on them):

	 - sia.maxQueryRegionSize.(long|lat)
	 - sia.maxImageExtent.(long|lat)
	 - sia.maxFileSize
	 - sia.maxRecord (default dalHardLimit global meta)
	"""
# XXX TODO: put more functionality into the core and then use
# UnifiedDALRenderer rather than siap.xml.
	name = "siap.xml"

	def __init__(self, ctx, *args, **kwargs):
		reqArgs = inevow.IRequest(ctx).args
		reqArgs["_VOTABLE_VERSION"] = ["1.1"]
		if "_TDENC" not in reqArgs:
			reqArgs["_TDENC"] = ["True"]
		DALRenderer.__init__(self, ctx, *args, **kwargs)

	def renderHTTP(self, ctx):
		args = inevow.IRequest(ctx).args
		try:
			metadataQuery = args["FORMAT"][0].lower()=="metadata"
		except (IndexError, KeyError):
			metadataQuery = False
		if metadataQuery:
			return self._renderMetadata(ctx, svcs.QueryMeta.fromContext(ctx))

		return DALRenderer.renderHTTP(self, ctx)

	_outputTableCasts = {
		"pixelScale": {"datatype": "double", "arraysize": "*"},
		"wcs_cdmatrix": {"datatype": "double", "arraysize": "*"},
		"wcs_refValues": {"datatype": "double", "arraysize": "*"},
		"bandpassHi": {"datatype": "double"},
		"bandpassLo": {"datatype": "double"},
		"bandpassRefval": {"datatype": "double"},
		"wcs_refPixel": {"datatype": "double", "arraysize": "*"},
		"wcs_projection": {"arraysize": "3", "castFunction": lambda s: s[:3]},
		"mime": {"ucd": "VOX:Image_Format"},
		"accref": {"ucd": "VOX:Image_AccessReference"},
	}

	def _formatOutput(self, data, ctx):
		data.original.setMeta("_type", "results")
		data.original.getPrimaryTable().votCasts = self._outputTableCasts
		return DALRenderer._formatOutput(self, data, ctx)
	
	def _makeErrorTable(self, ctx, msg, queryStatus="ERROR"):
		return V.VOTABLE11[
			V.RESOURCE(type="results")[
				V.INFO(name="QUERY_STATUS", value=queryStatus)[
					str(msg)]]]


class UnifiedDALRenderer(DALRenderer):
	"""A renderer for new-style simple DAL protocols.

	All input processing (e.g., metadata queries and the like) are considered
	part of the individual protocol and thus left to the core.

	The error style is that of SSAP (which, hopefully, will be kept
	for the other DAL2 protocols, too).

	To define actual renderers, inherit from this and set the name attribute
	(plus _outputTableCasts if necessary).  Also, explain any protocol-specific
	metadata in the docstring.
	"""
	parameterStyle = "pql"

	_outputTableCasts = {}

	def _formatOutput(self, data, ctx):
		request = inevow.IRequest(ctx)
		if isinstance(data.original, tuple):  
			# core returned a complete document (mime and string)
			mime, payload = data.original
			request.setHeader("content-type", mime)
			return streaming.streamOut(lambda f: f.write(payload), request)
		else:
			request.setHeader("content-type", "text/xml+votable")
			data.original.setMeta("_type", "results")
			data.original.getPrimaryTable().votCasts = self._outputTableCasts
			return DALRenderer._formatOutput(self, data, ctx)
	
	def _makeErrorTable(self, ctx, msg, queryStatus="ERROR"):
		return V.VOTABLE11[
			V.RESOURCE(type="results")[
				V.INFO(name="QUERY_STATUS", value=queryStatus)[
					str(msg)]]]


class SSAPRenderer(UnifiedDALRenderer):
	"""A renderer for the simple spectral access protocol.

	For registration, you must set the following metadata on services 
	using the ssap.xml renderer:

	 - ssap.dataSource -- survey, pointed, custom, theory, artificial
	 - ssap.testQuery -- a query string that returns some data; REQUEST=queryData
	   is added automatically
	
	Other SSA metadata includes:

	 - ssap.creationType -- archival, cutout, filtered, mosaic,
	   projection, spectralExtraction, catalogExtraction (defaults to archival)
	 - ssap.complianceLevel -- set to "query" when you don't deliver
	   SDM compliant spectra; otherwise don't say anything, DaCHS will fill
	   in the right value.

	Services with this renderer can have a datalink property; if present, it
	must point to a datalink service producing SDM-compliant spectra; this
	is for doing cutouts and similar.
	"""
	name = "ssap.xml"


class APIRenderer(UnifiedDALRenderer):
	"""A renderer that works like a VO standard renderer but that doesn't
	actually follow a given protocol.

	Use this for improvised APIs.  The default output format is a VOTable,
	and the errors come in VOSI VOTables.  The renderer does, however,
	evaluate the VOSI RESPONSEFORMAT parameter.  You can declare
	its metadata by including <inputKey original="//procs#RESPONSEFORMAT"/>
	in your service.
	"""
	name = "api"


class RegistryRenderer(grend.ServiceBasedPage):
	"""A renderer that works with registry.oaiinter to provide an OAI-PMH
	interface.

	The core is expected to return a stanxml tree.
	"""
	name = "pubreg.xml"
	urlUse = "base"
	resultType = "text/xml"

	def renderHTTP(self, ctx):
		# Make a robust (unchecked) pars dict for error rendering; real
		# parameter checking happens in getPMHResponse
		inData = {"args": inevow.IRequest(ctx).args}
		return self.runService(inData, 
			queryMeta=svcs.QueryMeta.fromNevowArgs(inData["args"])
			).addCallback(self._renderResponse, ctx
			).addErrback(self._renderError, ctx, inData["args"])

	def _renderResponse(self, svcResult, ctx):
		return self._renderXML(svcResult.original, ctx)

	def _renderXML(self, stanxml, ctx):
# XXX TODO: this can be pretty large -- do we want async operation
# here?  Stream this?
		request = inevow.IRequest(ctx)
		request.setHeader("content-type", "text/xml")
		return utils.xmlrender(stanxml,
			"<?xml-stylesheet href='/static/xsl/oai.xsl' type='text/xsl'?>")

	def _getErrorTree(self, exception, pars):
		"""returns an ElementTree containing an OAI-PMH error response.

		If exception is one of "our" exceptions, we translate them to error messages.
		Otherwise, we reraise the exception to an enclosing
		function may "handle" it.

		Contrary to the recommendation in the OAI-PMH spec, this will only
		return one error at a time.
		"""
		from gavo.registry.model import OAI

		if isinstance(exception, registry.OAIError):
			code = exception.__class__.__name__
			code = code[0].lower()+code[1:]
			message = str(exception)
		else:
			code = "badArgument" # Why the hell don't they have a serverError?
			message = "Internal Error: "+str(exception)
		return OAI.PMH[
			OAI.responseDate[datetime.datetime.utcnow().strftime(
				utils.isoTimestampFmt)],
			OAI.request(verb=pars.get("verb", ["Identify"])[0], 
					metadataPrefix=pars.get("metadataPrefix", [None])[0]),
			OAI.error(code=code)[
				message
			]
		]

	def _renderError(self, failure, ctx, pars):
		try:
			if not isinstance(failure.value, 
					(registry.OAIError, base.ValidationError)):
				base.ui.notifyFailure(failure)
			return self._renderXML(self._getErrorTree(failure.value, pars),
				ctx)
		except:
			base.ui.notifyError("Cannot create registry error document")
			request = inevow.IRequest(ctx)
			request.setResponseCode(400)
			request.setHeader("content-type", "text/plain")
			request.write("Internal error.  Please notify site maintainer")
			request.finishRequest(False)
		return appserver.errorMarker


class _DatalinkRendererBase(grend.ServiceBasedPage):
	"""the base class of the two datalink sync renderers.
	"""
	urlUse = "base"

	def renderHTTP(self, ctx):
		request = inevow.IRequest(ctx)
		return self.runService(request.args, ctx
			).addCallback(self._formatData, request
			).addErrback(self._reportError, request)
	
	def _formatData(self, svcResult, request):
		# the core returns mime, data or a resource.  So, if it's a pair,
		# to something myself, else let twisted sort it out
		data = svcResult.original

		if isinstance(data, tuple):
# XXX TODO: the same thing is in formrender.  Refactor; since this is
# something most renderers should be able to do, ServiceBasedPage would be
# a good place
			mime, payload = data
			request.setHeader("content-type", mime)
			request.setHeader('content-disposition', 
				'attachment; filename=result%s'%common.getExtForMime(mime))
			return streaming.streamOut(lambda f: f.write(payload), 
				request)

		else:
			return data

	def _reportError(self, failure, request):
		base.ui.notifyFailure(failure)
		request.setHeader("content-type", "text/plain")
		if isinstance(failure.value, base.Error):
			request.setResponseCode(422)
		else:
			request.setResponseCode(500)
		return "%s: %s\n"%(
			failure.value.__class__.__name__, 
			utils.safe_str(failure.value))


class DatalinkGetDataRenderer(_DatalinkRendererBase):
	"""A renderer for data processing by datalink cores.

	This must go together with a datalink core, nothing else will do.

	This renderer will actually produce the processed data.  It must be
	complemented by the dlmeta renderer which allows retrieving metadata.
	"""
	name = "dlget"


class DatalinkGetMetaRenderer(_DatalinkRendererBase):
	"""A renderer for data processing by datalink cores.

	This must go together with a datalink core, nothing else will do.

	This renderer will return the links and services applicable to
	one or more pubDIDs.

	See `Datalink Cores`_ for more information.
	"""
	name = "dlmeta"
	resultType = "application/x-votable+xml;content=datalink"


class DatalinkAsyncRenderer(grend.ServiceBasedPage):
	"""A renderer for asynchronous datalink.
	"""
# TODO: I suspect this should go somewhere else, presumably together
# with the stripped-down TAP renderer.
	name = "dlasync"

	def renderHTTP(self, ctx):
		return self.locateChild(ctx, ())[0]

	def locateChild(self, ctx, segments):
		from gavo.protocols import dlasync, uwsactions
		from gavo.web import asyncrender

		# no trailing slashes here, ever (there probably should be central
		# code for this somewhere, as this is done in taprender, too, and
		# possibly in other places, too)
		if segments and not segments[-1]: # trailing slashes are forbidden here
			newSegments = "/".join(segments[:-1])
			if newSegments:
				newSegments = "/"+newSegments
			raise svcs.WebRedirect(self.service.getURL("dlasync")+newSegments)

		uwsactions.lowercaseProtocolArgs(inevow.IRequest(ctx).args)
		return asyncrender.getAsyncResource(ctx, dlasync.DL_WORKER,
			"dlasync", self.service, segments), ()


def _test():
	import doctest, vodal
	doctest.testmod(vodal)


if __name__=="__main__":
	_test()
