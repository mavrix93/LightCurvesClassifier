"""
The datalink core and its numerous helper classes.

More on this in "Datalink Cores" in the reference documentation.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import os
import urllib

from gavo import base
from gavo import rsc
from gavo import rscdef
from gavo import svcs
from gavo import utils
from gavo.protocols import products
from gavo.formats import votablewrite
from gavo.votable import V, modelgroups

from nevow import inevow
from nevow import rend

MS = base.makeStruct


class FormatNow(base.ExecutiveAction):
	"""can be raised by data functions to abort all further processing
	and format the current descriptor.data.
	"""


class DeliverNow(base.ExecutiveAction):
	"""can be raised by data functions to abort all further processing
	and return the current descriptor.data to the client.
	"""


class ProductDescriptor(object):
	"""An encapsulation of information about some "product" (i.e., file).

	This is basically equivalent to a line in the product table; the
	arguments of the constructor are all available as same-named attributes.

	It also has an attribute data defaulting to None.  DataGenerators
	set it, DataFilters potentially change it.

	If you inherit from this method and you have a way to guess the
	size of what the descriptor describes, override the estimateSize()
	method.  The default will return a file size if accessPath points
	to an existing file, None otherwise.
	"""
	data = None

	def __init__(self, pubDID, accref, accessPath, mime, 
			owner=None, embargo=None, sourceTable=None, datalink=None,
			preview=None, preview_mime=None):
		self.pubDID = pubDID
		self.accref, self.accessPath, self.mime = accref, accessPath, mime
		self.owner, self.embargo, self.sourceTable = owner, embargo, sourceTable
		self.preview, self.preview_mime = preview, preview_mime

	@classmethod
	def fromAccref(cls, pubDID, accref):
		"""returns a product descriptor for an access reference.
		"""
		return cls(pubDID, **products.RAccref(accref).productsRow)

	def estimateSize(self):
		if isinstance(self.accessPath, basestring):
			candPath = os.path.join(base.getConfig("inputsDir"), self.accessPath)
			try:
				return os.path.getsize(candPath)
			except:
				# fall through to returning None
				pass


class DatalinkError(object):
	"""A datalink error.

	These are usually constructed using one of the classmethods


	* AuthenticationError -- Not authenticated (and authentication required)
	* AuthorizationError -- Not authorized (to access the resource)
	* NotFoundError -- Unknown ID value
	* UsageError -- Invalid input (e.g. no ID values)
	* TransientError -- Service is not currently able to function
	* FatalError -- Service cannot perform requested action
	* Error -- General error (not covered above)

	all of which take the pubDID that caused the failure and a human-oriented
	error message.
	"""
	def __init__(self, code, pubDID, message, exceptionClass):
		self.code, self.pubDID, self.message = code, pubDID, message
		self.exceptionClass = exceptionClass
	
	@classmethod
	def _addErrorMaker(cls, errCode, exceptionClass):
		def meth(inner, pubDID, message):
			return inner(errCode, pubDID, message, exceptionClass)
		setattr(cls, errCode, classmethod(meth))

	def asDict(self):
		"""returns an error row for the datalink response.
		"""
		return {"ID": self.pubDID, "error_message":
			"%s: %s"%(self.code, self.message)}

	def raiseException(self):
		raise self.exceptionClass(self.message+" (pubDID: %s)"%self.pubDID)

for errName, exClass in [
		("AuthenticationError", svcs.ForbiddenURI), 
		("AuthorizationError", svcs.ForbiddenURI),
		("NotFoundError", svcs.UnknownURI),
		("UsageError", svcs.BadMethod),
		("TransientError", svcs.BadMethod),
		("FatalError", svcs.Error),
		("Error", svcs.Error)]:
	DatalinkError._addErrorMaker(errName, exClass)
del errName, exClass


class DescriptorGenerator(rscdef.ProcApp):
	"""A procedure application for making product descriptors for PUBDIDs
	
	A normal product descriptor contains basically what DaCHS' product
	table contains.  You could derive from protocols.datalink.ProductDescriptor,
	though, e.g., in the setup of this proc.

	The following names are available to the code:

	  - pubDID -- the pubDID to be resolved
	  - args -- all the arguments that came in from the web
	    (these should not ususally be necessary and are completely unparsed)
	
	If you made your pubDID using the ``getStandardPubDID`` rowmaker function,
	and you need no additional logic within the descriptor,
	the default (//datalink#fromStandardPubDID) should do.

	If you need to derive custom descriptor classes, you can see the base
	class under the name ProductDescriptor.
	"""
	name_ = "descriptorGenerator"
	requiredType = "descriptorGenerator"
	formalArgs = "pubDID, args"

	additionalNamesForProcs = {
		"ProductDescriptor": ProductDescriptor,
		"DatalinkError": DatalinkError,
	}


class LinkDef(object):
	"""A definition of a datalink related document.

	These are constructed at least with:

		- the pubDID (as a string)
	  - the access URL (as a string)

	In addition, we accept the remaining column names from 
	//datalink#dlresponse as keyword arguments.
	
	For semantics, try to user one of science, calibration, preview, info,
	auxiliary, and processed.
	"""
	def __init__(self, pubDID, accessURL, 
			serviceType=None, 
			errorMessage=None,
			description=None, 
			semantics=None, 
			contentType=None, 
			contentLength=None):
		ID = pubDID #noflake: used in locals()
		del pubDID
		self.dlRow = locals()

	def asDict(self):
		"""returns the link definition in a form suitable for ingestion
		in //datalink#dlresponse.
		"""
		return {
			"ID": self.dlRow["ID"],
			"access_url": self.dlRow["accessURL"],
			"service_def": self.dlRow["serviceType"],
			"error_message": self.dlRow["errorMessage"],
			"description": self.dlRow["description"],
			"semantics": self.dlRow["semantics"],
			"content_type": self.dlRow["contentType"],
			"content_length": self.dlRow["contentLength"]}


class _ServiceDescriptor(object):
	"""An internal descriptor for one of our services.

	These are serialized into service resources in VOTables.
	Basically, these collect input keys, a pubDID, as well as any other
	data we might need in service definitioin.
	"""
	def __init__(self, pubDID, inputKeys):
		self.pubDID, self.inputKeys = pubDID, inputKeys

	def asVOT(self, ctx, accessURL, linkIdTo=None):
		"""returns VOTable stanxml for a description of this service.

		This is a RESOURCE as required by Datalink.

		linkIdTo is used to support data access descriptors embedded
		in descovery queries.  It is the id of the column containing
		the identifiers.  SSA can already provide this.  It ends up
		in a LINK child of the ID parameter.
		"""
		paramsByName, stcSpecs = {}, set()
		for param in self.inputKeys:
			paramsByName[param.name] = param
			if param.stc:
				stcSpecs.add(param.stc)

		def getIdFor(colRef):
			colRef.toParam = True
			return ctx.makeIdFor(paramsByName[colRef.dest])

		res = V.RESOURCE(ID=ctx.getOrMakeIdFor(self), type="meta",
			utype="adhoc:service")[
			[modelgroups.marshal_STC(ast, getIdFor)
				for ast in stcSpecs],
			V.PARAM(arraysize="*", datatype="char", 
				name="accessURL", ucd="meta.ref.url",
				value=accessURL)]

		inputParams = V.GROUP(name="input")
		res = res[inputParams]

		for ik in self.inputKeys:
			param = votablewrite._addID(ik,
				votablewrite.makeFieldFromColumn(V.PARAM, ik), ctx)
			if linkIdTo and ik.name=="ID":
				# TODO: Kill the LINK child (older proposal implemented by some
				# splat betas) some time after June 2014
				param = param(ref=linkIdTo)[
					V.LINK(content_role="ddl:id-source", value="#"+linkIdTo)]
			inputParams[param]

		return res


class MetaMaker(rscdef.ProcApp):
	"""A procedure application that generates metadata for datalink services.

	The code must be generators (i.e., use yield statements) producing either
	svcs.InputKeys or protocols.datalink.LinkDef instances.

	metaMaker see the data descriptor of the input data under the name
	descriptor.

	The data attribute of the descriptor is always None for metaUpdaters, so
	you cannot use anything given there.

	Within MetaMakers' code, you can access InputKey, Values, Option, and
	LinkDef without qualification, and there's the MS function to build
	structures.  Hence, a metaMaker returning an InputKey could look like this::

		<metaMaker>
			<code>
				yield MS(InputKey, name="format", type="text",
					description="Output format desired",
					values=MS(Values,
						options=[MS(Option, content_=descriptor.mime),
							MS(Option, content_="text/plain")]))
			</code>
		</metaMaker>

	(of course, you should give more metadata -- ucds, better description,
	etc) in production).

	In addition to the usual names available to ProcApps, meta makers have:
	  - MS -- function to make DaCHS structures
	  - InputKey -- the class to make for input parameters
	  - Values -- the class to make for input parameters' values attributes
	  - Options -- used by Values
	  - LinkDef -- a class to define further links within datalink services.
	  - DatalinkError -- a container of datalink error generators
	"""
	name_ = "metaMaker"
	requiredType = "metaMaker"
	formalArgs = "descriptor"

	additionalNamesForProcs = {
		"MS": base.makeStruct,
		"InputKey": svcs.InputKey,
		"Values": rscdef.Values,
		"Option": rscdef.Option,
		"LinkDef": LinkDef,
		"DatalinkError": DatalinkError,
	}


class DataFunction(rscdef.ProcApp):
	"""A procedure application that generates or modifies data in a processed
	data service.

	All these operate on the data attribute of the product descriptor.
	The first data function plays a special role: It *must* set the data
	attribute (or raise some appropriate exception), or a server error will 
	be returned to the client.

	What is returned depends on the service, but typcially it's going to
	be a table or products.*Product instance.

	Data functions can shortcut if it's evident that further data functions
	can only mess up (i.e., if the do something bad with the data attribute);
	you should not shortcut if you just *think* it makes no sense to
	further process your output.

	To shortcut, raise either of FormatNow (falls though to the formatter,
	which is usually less useful) or DeliverNow (directly returns the
	data attribute; this can be used to return arbitrary chunks of data).

	The following names are available to the code:
	  - descriptor -- whatever the DescriptorGenerator returned
	  - args -- all the arguments that came in from the web.
	
	In addition to the usual names available to ProcApps, data functions have:
	  - FormatNow -- exception to raise to go directly to the formatter
	  - DeliverNow -- exception to raise to skip all further formatting
	    and just deliver what's currently in descriptor.data
	"""
	name_ = "dataFunction"
	requiredType = "dataFunction"
	formalArgs = "descriptor, args"

	additionalNamesForProcs = {
		"FormatNow": FormatNow,
		"DeliverNow": DeliverNow,
	}


class DataFormatter(rscdef.ProcApp):
	"""A procedure application that renders data in a processed service.

	These play the role of the renderer, which for datalink is ususally
	trivial.  They are supposed to take descriptor.data and return
	a pair of (mime-type, bytes), which is understood by most renderers.

	When no dataFormatter is given for a core, it will return descriptor.data
	directly.  This can work with the datalink renderer itself if 
	descriptor.data will work as a nevow resource (i.e., has a renderHTTP
	method, as our usual products do).  Consider, though, that renderHTTP
	runs in the main event loop and thus most not block for extended
	periods of time.

	The following names are available to the code:
	  - descriptor -- whatever the DescriptorGenerator returned
	  - args -- all the arguments that came in from the web.
	
	In addition to the usual names available to ProcApps, data formatters have:
	  - Page -- base class for resources with renderHTTP methods.
	  - IRequest -- the nevow interface to make Request objects with.
	"""
	name_ = "dataFormatter"
	requiredType = "dataFormatter"
	formalArgs = "descriptor, args"

	additionalNamesForProcs = {
		"Page": rend.Page,
		"IRequest": inevow.IRequest,
	}


class DatalinkCoreBase(svcs.Core, base.ExpansionDelegator):
	"""Basic functionality for datalink cores.  

	This is pulled out of the datalink core proper as it is used without
	the complicated service interface sometimes, e.g., by SSAP.
	"""

	_descriptorGenerator = base.StructAttribute("descriptorGenerator",
		default=base.NotGiven, 
		childFactory=DescriptorGenerator,
		description="Code that takes a PUBDID and turns it into a"
			" product descriptor instance.  If not given,"
			" //datalink#fromStandardPubDID will be used.",
		copyable=True)

	_metaMakers = base.StructListAttribute("metaMakers",
		childFactory=MetaMaker,
		description="Code that takes a data descriptor and either"
			" updates input key options or yields related data.",
		copyable=True)

	_dataFunctions = base.StructListAttribute("dataFunctions",
		childFactory=DataFunction,
		description="Code that generates of processes data for this"
			" core.  The first of these plays a special role in that it"
			" must set descriptor.data, the others need not do anything"
			" at all.",
		copyable=True)

	_dataFormatter = base.StructAttribute("dataFormatter",
		default=base.NotGiven,
		childFactory=DataFormatter,
		description="Code that turns descriptor.data into a nevow resource"
			" or a mime, content pair.  If not given, the renderer will be"
			" returned descriptor.data itself (which will probably not usually"
			" work).",
		copyable=True)

	_inputKeys = rscdef.ColumnListAttribute("inputKeys",
		childFactory=svcs.InputKey,
		description="A parameter to one of the proc apps (data functions,"
		" formatters) active in this datalink core; no specific relation"
		" between input keys and procApps is supposed; all procApps are passed"
		" all argments. Conventionally, you will write the input keys in"
		" front of the proc apps that interpret them.",
		copyable=True)

	# The following is a hack complemented in inputdef.makeAutoInputDD.
	# We probably want some other way to do this (if we want to do it
	# at all)
	rejectExtras = True

	def completeElement(self, ctx):
		if self.descriptorGenerator is base.NotGiven:
			self.descriptorGenerator = MS(DescriptorGenerator, 
				procDef=base.caches.getRD("//datalink").getById("fromStandardPubDID"))

		if self.dataFormatter is base.NotGiven:
			self.dataFormatter = MS(DataFormatter, 
				procDef=base.caches.getRD("//datalink").getById("trivialFormatter"))
		
		self.inputKeys.append(MS(svcs.InputKey, name="ID", type="text", 
			ucd="meta.id;meta.main",
			multiplicity="multiple",
			required=True,
			std=True,
			description="The pubisher DID of the dataset of interest"))

		if self.inputTable is base.NotGiven:
			self.inputTable = MS(svcs.InputTable, params=self.inputKeys)

		# this is a cheat for service.getTableSet to pick up the datalink
		# table.  If we fix this for TAP, we should fix it here, too.
		self.queriedTable = base.caches.getRD("//datalink").getById(
			"dlresponse")

		self._completeElementNext(DatalinkCoreBase, ctx)

	def getMetaForDescriptor(self, descriptor):
		"""returns a pair of linkDefs, inputKeys for a datalink desriptor
		and this core.
		"""
		linkDefs, inputKeys, errors = [], self.inputKeys[:], []
	
		for metaMaker in self.metaMakers:
			try:
				for item in metaMaker.compile(self)(descriptor):
					if isinstance(item, LinkDef):
						linkDefs.append(item)
					elif isinstance(item, DatalinkError):
						errors.append(item)
					else:
						inputKeys.append(item)
			except Exception, ex:
				errors.append(DatalinkError.Error(descriptor.pubDID),
					"Unexpected failure while creating"
					" datalink: %s"%utils.safe_str(ex))
	
		return linkDefs, inputKeys, errors

	def getDatalinksResource(self, ctx, service):
		"""returns a VOTable RESOURCE element with the data links.

		This does not contain the actual service definition elements, but it
		does contain references to them.

		You must pass in a VOTable context object ctx (for the management
		of ids).  If this is the entire content of the VOTable, use
		votablewrite.VOTableContext() there.
		"""
		internalLinks = []

		if "dlget" in service.allowed:
			internalLinks = [LinkDef(s.pubDID, service.getURL("dlget"),
					serviceType=ctx.getOrMakeIdFor(s), semantics="access")
				for s in self.datalinkServices]
			for d in self.descriptors:
				if not isinstance(d, ProductDescriptor):
					continue
				internalLinks.append(LinkDef(d.pubDID, 
						service.getURL("dlget")+"?ID="+urllib.quote_plus(d.pubDID),
						description="The full dataset.",
						contentType=d.mime,
						contentLength=d.estimateSize(),
						semantics="self"))

				if d.preview:
					if d.preview.startswith("http"):
						previewLink = d.preview
					else:
						previewLink = products.makeProductLink(
							products.RAccref(d.accref, 
								inputDict={"preview": True}))
					internalLinks.append(LinkDef(d.pubDID,
						previewLink, description="A preview.",
						contentType=d.preview_mime, semantics="preview"))

		data = rsc.makeData(
			base.caches.getRD("//datalink").getById("make_response"),
			forceSource=self.datalinkLinks+internalLinks+self.errors)
		data.setMeta("_type", "results")

		return votablewrite.makeResource(
			votablewrite.VOTableContext(tablecoding="td"),
			data)

	
class DatalinkCore(DatalinkCoreBase):
	"""A core for processing datalink and processed data requests.

	The input table of this core is dynamically generated from its
	metaMakers; it makes no sense at all to try and override it.

	See `Datalink Cores`_ for more information.

	In contrast to "normal" cores, one of these is made (and destroyed)
	for each datalink request coming in.  This is because the interface
	of a datalink service depends on the request's value(s) of ID.

	The datalink core can produce both its own metadata and data generated.
	It is the renderer's job to tell them apart.
	"""
	name_ = "datalinkCore"

	def _getPubDIDs(self, args):
		"""returns a list of pubDIDs from args["ID"].

		args is supposed to be a nevow request.args-like dict, where the PubDIDs
		are taken from the ID parameter.  If it's atomic, it'll be expanded into
		a list.  If it's not present, a ValidationError will be raised.
		"""
		try:
			pubDIDs = args["ID"]
			if not isinstance(pubDIDs, list):
				pubDIDs = [pubDIDs]
		except (KeyError, IndexError):
			raise base.ValidationError("Value is required but was not provided",
				"ID")
		return pubDIDs

	def adaptForDescriptors(self, renderer, descriptors):
		"""returns a core for renderer and a sequence of ProductDescriptors.

		This method is mainly for helping adaptForRenderer.  Do read the
		docstring there.
		"""
		linkDefs, services, errors = [], [], []
		for descriptor in descriptors:
			if isinstance(descriptor, DatalinkError):
				errors.append(descriptor)

			else:
				lds, inputKeys, lerrs = self.getMetaForDescriptor(descriptor)
				linkDefs.extend(lds)
				errors.extend(lerrs)
				services.append(_ServiceDescriptor(descriptor.pubDID, inputKeys))

		inputKeys = self.inputKeys[:]
		if services:
			inputKeys.extend(services[-1].inputKeys)

		# The queriedTable hack here is to get our table into the VOSI
		# endpoint; we should fix this when we fix this for TAP.
		if renderer.name=="dlmeta":
			inputKeys.append(MS(svcs.InputKey, name="REQUEST", 
				type="text", 
				ucd="meta.code",
				multiplicity="single",
				required=False,
				std=True,
				description="Request type (must be getLinks)",
				values=rscdef.Values.fromOptions(
					["getLinks"])))
			inputKeys.append(MS(svcs.InputKey, name="RESPONSEFORMAT", 
				type="text", 
				ucd="meta.code.mime",
				multiplicity="single",
				required=False,
				std=True,
				description="Format of the request document",
				values=rscdef.Values.fromOptions(
					["application/x-votable+xml;content=datalink"])))

		res = self.change(inputTable=MS(svcs.InputTable, 
			params=inputKeys))

		# this is a bit of a hack: dlmeta should return the metadata,
		# all other renderers are supposed to want to do the processing
		# (in particular dlget, but form should do, too)
		if renderer.name=="dlmeta":
			res.run = res.runForMeta
		else:
			if isinstance(descriptors[-1], DatalinkError):
				descriptors[-1].raiseException()
			res.run = res.runForData

		res.nocache = True
		res.datalinkLinks = linkDefs
		res.datalinkServices = services
		res.descriptors = descriptors
		res.errors = errors
		return res

	def adaptForRenderer(self, renderer):
		"""returns a core for a specific product.
	
		The ugly thing about datalink in DaCHS' architecture is that its
		interface (in terms of, e.g., inputKeys' values children) depends
		on the arguments themselves, specifically the pubdid.

		The workaround is to abuse the renderer-specific getCoreFor,
		ignore the renderer and instead steal an "args" variable from
		somewhere upstack.  Nasty, but for now an acceptable solution.

		It is particularly important to never let service cache the
		cores returned; hence to "nocache" magic.

		This tries to generate all datalink-relevant metadata in one go 
		and avoid calling the descriptorGenerator(s) more than once per
		pubDID.  It therefore adds datalinkLinks, datalinkServices,
		and datalinkDescriptors attributes.  These are used later
		in either metadata generation or data processing.

		The latter will in general use only the last pubDID passed in.  
		Therefore, this last pubDID determines the service interface
		for now.  Perhaps we should be joining the inputKeys in some way,
		though, e.g., if we want to allow retrieving multiple datasets
		in a tar file?  Or to re-use the same service for all pubdids?
		"""
		try:
			args = utils.stealVar("args")
			if not isinstance(args, dict):
				# again, we're not being called in a context with a pubdid
				raise ValueError("No pubdid")
		except ValueError:
			# no arguments found: no pubdid-specific interfaces
			return self

		pubDIDs = self._getPubDIDs(args)
		descGen = self.descriptorGenerator.compile(self)
		descriptors = []
		for pubDID in pubDIDs:
			try:
				descriptors.append(descGen(pubDID, args))
			except base.NotFoundError, ex:
				descriptors.append(DatalinkError.NotFoundError(pubDID,
					utils.safe_str(ex)))
# TODO: Catch more "known" exceptions, e.g. Authorization
			except Exception, ex:
				descriptors.append(DatalinkError.Error(pubDID,
					utils.safe_str(ex)))

		return self.adaptForDescriptors(renderer, descriptors)


	def runForMeta(self, service, inputTable, queryMeta):
		"""returns a rendered VOTable containing the datalinks.
		"""
		ctx = votablewrite.VOTableContext(tablecoding="td")
		vot = V.VOTABLE[
				self.getDatalinksResource(ctx, service), [
					dlSvc.asVOT(ctx, service.getURL("dlget")) 
						for dlSvc in self.datalinkServices]
				]
		return ("application/x-votable+xml;content=datalink", vot.render())

	def runForData(self, service, inputTable, queryMeta):
		"""returns a data set processed according to inputTable's parameters.
		"""
		args = inputTable.getParamDict()
		if not self.dataFunctions:
			raise base.DataError("This datalink service cannot process data")

		descriptor = self.descriptors[-1]
		self.dataFunctions[0].compile(self)(descriptor, args)

		if descriptor.data is None:
			raise base.ReportableError("Internal Error: a first data function did"
				" not create data.")

		for func in self.dataFunctions[1:]:
			try:
				func.compile(self)(descriptor, args)
			except FormatNow:
				break
			except DeliverNow:
				return descriptor.data

		return self.dataFormatter.compile(self)(descriptor, args)
