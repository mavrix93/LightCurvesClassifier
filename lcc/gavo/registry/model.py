"""
The schema and XML namespaces for OAI/VOR documents.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from gavo import base
from gavo.base import typesystems
from gavo.utils.stanxml import Element, schemaURL, registerPrefix, xsiPrefix


class Error(base.Error):
	pass


# See stanxml for the root of all the following evil.
registerPrefix("oai", "http://www.openarchives.org/OAI/2.0/",
	schemaURL("OAI-PMH.xsd"))
registerPrefix("oai_dc", "http://www.openarchives.org/OAI/2.0/oai_dc/",
	schemaURL("oai_dc.xsd"))
registerPrefix("ri",
	"http://www.ivoa.net/xml/RegistryInterface/v1.0",
	schemaURL("RegistryInterface-v1.0.xsd"))
registerPrefix("vg", "http://www.ivoa.net/xml/VORegistry/v1.0",
	schemaURL("VORegistry-v1.0.xsd"))
registerPrefix("vr", "http://www.ivoa.net/xml/VOResource/v1.0",
	schemaURL("VOResource-v1.0.xsd"))
registerPrefix("dc", "http://purl.org/dc/elements/1.1/",
	schemaURL("simpledc20021212.xsd"))
registerPrefix("vs0", "http://www.ivoa.net/xml/VODataService/v1.0",
	schemaURL("VODataService-v1.0.xsd"))
registerPrefix("vs", "http://www.ivoa.net/xml/VODataService/v1.1",
	schemaURL("VODataService-v1.1.xsd"))
registerPrefix("cs", "http://www.ivoa.net/xml/ConeSearch/v1.0",
	schemaURL("ConeSearch-v1.0.xsd"))
registerPrefix("sia", "http://www.ivoa.net/xml/SIA/v1.1",
	schemaURL("SIA-v1.1.xsd"))
registerPrefix("ssap", "http://www.ivoa.net/xml/SSA/v1.1",
	schemaURL("SSA-v1.1.xsd"))
registerPrefix("tr", "http://www.ivoa.net/xml/TAPRegExt/v1.0",
	schemaURL("TAPRegExt-v1.0.xsd"))
registerPrefix("vstd", "http://www.ivoa.net/xml/StandardsRegExt/v1.0",
	schemaURL("StandardsRegExt-1.0.xsd"))
registerPrefix("doc", "http://www.ivoa.net/xml/DocRegExt/v1.0",
	schemaURL("DocRegExt-v1.0.xsd"))


class OAI(object):
	"""is a container for classes modelling OAI elements.
	"""
	class OAIElement(Element):
		_prefix = "oai"

	class PMH(OAIElement):
		name_ = "OAI-PMH"
	
	class responseDate(OAIElement): pass

	class request(OAIElement):
		_mayBeEmpty = True
		_a_verb = None
		_a_metadataPrefix = None

	class metadata(OAIElement): pass

	class Identify(OAIElement): pass

	class ListIdentifiers(OAIElement): pass

	class ListRecords(OAIElement): pass

	class GetRecord(OAIElement): pass
	
	class ListMetadataFormats(OAIElement): pass

	class ListSets(OAIElement):
			_mayBeEmpty = True

	class header(OAIElement):
		_a_status = None

	class error(OAIElement):
		_mayBeEmpty = True
		_a_code = None

	class record(OAIElement): pass

	class identifier(OAIElement): pass
	
	class datestamp(OAIElement): pass
	
	class setSpec(OAIElement): pass

	class repositoryName(OAIElement): pass
	
	class baseURL(OAIElement): pass
	
	class adminEmail(OAIElement): pass
	
	class earliestDatestamp(OAIElement): pass
	
	class deletedRecord(OAIElement): pass
	
	class granularity(OAIElement): pass

	class description(OAIElement): pass
	
	class protocolVersion(OAIElement): pass

	class metadataFormat(OAIElement): pass

	class metadataPrefix(OAIElement): pass
	
	class schema(OAIElement): pass

	class metadataNamespace(OAIElement): pass

	class set(OAIElement): pass
	
	class setSpec(OAIElement): pass
	
	class setName(OAIElement): pass

	class setDescription(OAIElement): pass

	class resumptionToken(OAIElement): pass
		# optional attributes not supported here
		# The string value in here has a structure; see oaiinter.


class OAIDC:
	"""is a container for OAI's Dublin Core metadata model.
	"""
	class OAIDCElement(Element):
		_prefix = "oai_dc"
	
	class dc(OAIDCElement):
		pass


class VOR:
	"""is a container for classes modelling elements from VO Resource.
	"""
	class VORElement(Element):
		_prefix = "vr"
		_local = True

	class Resource(VORElement):
# This is "abstract" in that only derived elements may be present
# in an instance document (since VOR doesn't define any global elements).
# Typically, this will be vr:Resource elements with some funky xsi:type
		_a_created = None
		_a_updated = None
		_a_status = None
		name_ = "Resource"
		_local = False
		_additionalPrefixes = frozenset(["vr", "ri", "xsi"])

	class Organisation(Resource):
		_a_xsi_type = "vr:Organisation"
		
	class Service(Resource):
		_a_xsi_type = "vr:Service"

	class validationLevel(VORElement):
		_a_validatedBy = None
	
	class title(VORElement): pass
	
	class shortName(VORElement): pass

	class ResourceName(VORElement):
		_a_ivoId = None
		_name_a_ivoId = "ivo-id"

	class identifier(VORElement): pass

	class curation(VORElement): pass
	
	class content(VORElement): pass

	class creator(VORElement): pass
	
	class contributor(ResourceName): pass
	
	class date(VORElement):
		_a_role = None
	
	class version(VORElement): pass
	
	class contact(VORElement): pass
	
	class publisher(ResourceName): pass

	class facility(VORElement): pass

	class instrument(VORElement): pass
	
	class relatedResource(VORElement): pass
	
	class name(VORElement): pass
	
	class address(VORElement): pass
	
	class email(VORElement): pass
	
	class telephone(VORElement): pass
	
	class logo(VORElement): pass
	
	class subject(VORElement): pass
	
	class description(VORElement): pass
	
	class source(VORElement):
		_a_format = None
	
	class referenceURL(VORElement): pass
	
	class type(VORElement): pass
	
	class contentLevel(VORElement): pass
	
	class relationship(VORElement):
		def _setupNode(self):
			self.__isEmpty = None
			self._setupNodeNext(VOR.relationship)

		def isEmpty(self):
			# special rule: a relationship is empty if there's no relatedResource
			# in them (this is a simplification of "don't count relationshipType
			# since it's always non-empty").
			if self._isEmptyCache is None:
				self._isEmptyCache = True
				for c in self.iterChildrenOfType(VOR.relatedResource):
					self._isEmptyCache = False
					break
			return self._isEmptyCache

	class relationshipType(VORElement): pass
	
	class relatedResource(VORElement):
		_a_ivoId = None
		_name_a_ivoId = "ivo-id"

	class rights(VORElement): pass
	
	class capability(VORElement):
		name_ = "capability"
		_additionalPrefixes = xsiPrefix
		_a_standardID = None
	
	class interface(VORElement):
		name_ = "interface"
		_additionalPrefixes = xsiPrefix
		_a_version = None
		_a_role = None
		_a_qtype = None

	class WebBrowser(interface):
		_a_xsi_type = "vr:WebBrowser"
	
	class WebService(interface):
		_a_xsi_type = "vr:WebService"

	class wsdlURL(VORElement): pass

	class accessURL(VORElement):
		_a_use = None
	
	class securityMethod(VORElement):
		def isEmpty(self):
			return self.standardId is None
		_a_standardId = None
	

class RI:
	"""is a container for classes modelling elements from IVOA Registry Interface.
	"""
	class RIElement(Element):
		_prefix = "ri"
	
	class VOResources(RIElement): pass

	class Resource(VOR.Resource):
		_prefix = "ri"


class VOG:
	"""is a container for classes modelling elements from VO Registry.
	"""
	class VOGElement(Element):
		_prefix = "vg"
		_local = True

	class Resource(RI.Resource):
		_a_xsi_type = "vg:Registry"
		_additionalPrefixes = frozenset(["vg", "xsi"])

	class Authority(RI.Resource):
		_a_xsi_type = "vg:Authority"
		_additionalPrefixes = frozenset(["vg", "xsi"])

	class capability(VOR.capability):
		_a_standardID = "ivo://ivoa.net/std/Registry"
	
	class Harvest(capability):
		_a_xsi_type = "vg:Harvest"
		_additionalPrefixes = frozenset(["vg", "xsi"])

	class Search(VOGElement):
		_a_xsi_type = "vg:Search"
		_additionalPrefixes = frozenset(["vg", "xsi"])

	class OAIHTTP(VOR.interface):
		_a_xsi_type = "vg:OAIHTTP"
		# namespace declaration has happened in enclosing element

	class OAISOAP(VOR.interface):
		_a_xsi_type = "vg:OAISOAP"
		# namespace declaration has happened in enclosing element

	class description(VOGElement): pass
		
	class full(VOGElement): pass
	
	class managedAuthority(VOGElement): pass
	
	class validationLevel(VOGElement): pass
	
	class description(VOGElement): pass
	
	class interface(VOGElement): pass
	
	class maxRecords(VOGElement): pass

	class extensionSearchSupport(VOGElement): pass
	
	class optionalProtocol(VOGElement): pass
	
	class managingOrg(VOGElement): pass

	
class DC:
	"""is a container for classes modelling elements from Dublin Core.
	"""
	class DCElement(Element):
		_prefix = "dc"

	class contributor(DCElement): pass

	class coverage(DCElement): pass

	class creator(DCElement): pass

	class date(DCElement): pass

	class description(DCElement): pass

	class format(DCElement): pass

	class identifier(DCElement): pass

	class language(DCElement): pass

	class publisher(DCElement): pass

	class relation(DCElement): pass

	class rights(DCElement): pass

	class source(DCElement): pass

	class subject(DCElement): pass

	class title(DCElement): pass

	class type(DCElement): pass


def addBasicVSElements(baseNS, VSElement):
	"""returns an element namespace containing common VODataService elements.
	"""
	class TNS(baseNS):
		class facility(VSElement): pass
		
		class instrument(VSElement): pass
		
		class coverage(VSElement): pass
	
		class waveband(VSElement): pass

		class format(VSElement): 
			_a_isMIMEType = None
		
		class rights(VSElement): pass
		
		class accessURL(VSElement): pass
		
		class ParamHTTP(VOR.interface):
			_a_xsi_type = "vs:ParamHTTP"
			_additionalPrefixes = frozenset(["vg", "xsi"])

		class resultType(VSElement): pass
		
		class queryType(VSElement): pass

		class param(VSElement):
			_a_std = "false"
		
		class name(VSElement): pass
		
		class description(VSElement): pass

		class unit(VSElement): pass
		
		class ucd(VSElement): pass

		class Service(RI.Resource): pass

		class DataService(Service):
			_a_xsi_type = "vs:DataService"
			_additionalPrefixes = frozenset(["vs", "xsi"])

		class TableService(Service):
			_a_xsi_type = "vs:TableService"
			_additionalPrefixes = frozenset(["vs", "xsi"])

		class CatalogService(Service):
			_a_xsi_type = "vs:CatalogService"
			_additionalPrefixes = frozenset(["vs", "xsi"])

		class ServiceReference(VSElement):
			_a_ivoId = None
			_name_a_ivoId = "ivo-id"

		class column(VSElement): pass
	
		class dataType(VSElement):
			# dataType is something of a mess with subtle changes from 1.0 to
			# 1.1.  There are various type systems, and all of this is
			# painful.  I don't try to untangle this here.
			name_ = "dataType"
			_additionalPrefixes = xsiPrefix
			_a_arraysize = None
			_a_delim = None
			_a_extendedSchema = None
			_a_extendedType = None

			def addChild(self, item):
				assert isinstance(item, basestring)
				self._defineType(item)

			def _defineType(self, item):
				self.text_ = item

		class simpleDataType(dataType):
			name_ = "dataType"  # dataType with vs:SimpleDataType sounds so stupid
				# that I must have misunderstood something.
			
			typeMap = {
				"char": "string",
				"short": "integer",
				"int": "integer",
				"long": "integer",
				"float": "real",
				"double": "real",
			}

			def _defineType(self, type):
				self.text_ = self.typeMap.get(type, type)
		
		class voTableDataType(dataType):
			_a_xsi_type = "vs:VOTableType"

			def _defineType(self, type):
				typeName, arrLen = typesystems.toVOTableConverter.convert(type)
				self.text_ = typeName
				self(arraysize=str(arrLen))


	return TNS

# Elements common to VODataService 1.0 and 1.1 are added by addBasicVSElements

class _VS1_0Stub(object):
	"""The stub for VODataService 1.0.
	"""
	class VSElement(Element):
		_prefix = "vs0"
		_local = True

	class table(VSElement):
		_a_role = None



VS0 = addBasicVSElements(_VS1_0Stub, _VS1_0Stub.VSElement)

class _VS1_1Stub:
	"""The stub for VODataService 1.1.
	"""
	class VSElement(Element):
		_prefix = "vs"
		_local = True

	class DataCollection(RI.Resource):
		_a_xsi_type = "vs:DataCollection"
		_additionalPrefixes = frozenset(["vs", "xsi"])

	class tableset(VSElement):
		_additionalPrefixes = xsiPrefix
		_mayBeEmpty = True
		_childSequence = ["schema"]
	
	class schema(VSElement):
		_childSequence = ["name", "title", "description", "utype",
			"table"]
	
	class title(VSElement): pass
	class utype(VSElement): pass
	
	class table(VSElement):
		_a_type = None
		_childSequence = ["name", "title", "description", "utype",
			"column", "foreignKey"]

	class foreignKey(VSElement):
		_childSequence = ["targetTable", "fkColumn", "description", "utype"]
	
	class targetTable(VSElement): pass
	
	class fkColumn(VSElement):
		_childSequence = ["fromColumn", "targetColumn"]

	class fromColumn(VSElement): pass
	class targetColumn(VSElement): pass
	class flag(VSElement): pass
	class regionOfRegard(VSElement): pass

VS = addBasicVSElements(_VS1_1Stub, _VS1_1Stub.VSElement)


class SIA(object):
	"""A container for classes modelling elements for describing simple
	image access services.
	"""
	class SIAElement(Element):
		_prefix = "sia"
		_local = True

	class interface(VOR.interface):
		_prefix = "sia"
		_a_role = "std"
		_additionalPrefixes = frozenset(["vs", "xsi"])
		_a_xsi_type = "vs:ParamHTTP"

	class capability(VOR.capability):
		_a_standardID = 	"ivo://ivoa.net/std/SIA"
		_a_xsi_type = "sia:SimpleImageAccess"
		_additionalPrefixes = frozenset(["sia", "xsi"])

	class imageServiceType(SIAElement): pass
	
	class maxQueryRegionSize(SIAElement): pass
	
	class maxImageExtent(SIAElement): pass
	
	class maxImageSize(SIAElement): pass

	class maxFileSize(SIAElement): pass

	class maxRecords(SIAElement): pass

	class long(SIAElement): pass
	
	class lat(SIAElement): pass

	class testQuery(SIAElement): pass
	
	class pos(SIAElement): pass
	
	class size(SIAElement): pass

	
class SCS(object):
	"""A container for elements describing Simple Cone Search services.
	"""
	class SCSElement(Element):
		_prefix = "cs"
		_local = True

	class interface(VOR.interface):
		_prefix = "cs"
		_a_role = "std"
		_a_xsi_type = "vs:ParamHTTP"
		_additionalPrefixes = frozenset(["xsi", "vs"])

	class capability(VOR.capability):
		_a_standardID = 	"ivo://ivoa.net/std/ConeSearch"
		_a_xsi_type = "cs:ConeSearch"
		_additionalPrefixes = frozenset(["xsi", "vs"])
	
	class maxSR(SCSElement): pass
	
	class maxRecords(SCSElement): pass
	
	class verbosity(SCSElement): pass

	class testQuery(SCSElement): pass
	class ra(SCSElement): pass
	class dec(SCSElement): pass
	class sr(SCSElement): pass
	class extras(SCSElement): pass


class SSAP(object):
	"""A container for the elements of the SSA registry extension.
	"""
	class SSAElement(Element):
		_prefix = "ssap"
		_local = True
	
	class capability(VOR.capability):
		_a_standardID = "ivo://ivoa.net/std/SSA"
		_a_xsi_type = "ssap:SimpleSpectralAccess"
		_additionalPrefixes = frozenset(["xsi", "vs"])

	class interface(VOR.interface):
		_prefix = "ssap"
		_a_role = "std"
		_additionalPrefixes = frozenset(["vs", "xsi"])
		_a_xsi_type = "vs:ParamHTTP"

	class complianceLevel(SSAElement): pass
	class dataSource(SSAElement): pass
	class creationType(SSAElement): pass
	class maxSearchRadius(SSAElement): pass
	class maxRecords(SSAElement): pass
	class defaultMaxRecords(SSAElement): pass
	class maxAperture(SSAElement): pass
	class maxFileSize(SSAElement): pass
	class supportedFrame(SSAElement): pass
	class testQuery(SSAElement): pass
	class queryDataCmd(SSAElement): pass


class TR(object):
	"""A container for elements describing TAP services.
	"""
	class TRElement(Element):
		_prefix = "tr"
		_local = True

	class interface(VOR.interface):
		_a_role = "std"
		_a_xsi_type = "vs:ParamHTTP"
		_additionalPrefixes = frozenset(["xsi", "vs"])

	class capability(VOR.capability):
		_a_standardID = 	"ivo://ivoa.net/std/TAP"
		_a_xsi_type = "tr:TableAccess"
		_additionalPrefixes = frozenset(["tr", "xsi"])

	class dataModel(TRElement):
		_a_ivoId = None
		_name_a_ivoId = "ivo-id"

	class label(TRElement):
		pass

	class language(TRElement):
		_a_LANG = None
	
	class outputFormat(TRElement):
		_a_FORMAT = None
		_a_mime = None
		_a_ivoId = None
		_name_a_ivoId = "ivo-id"
	
	class uploadMethod(TRElement):
		_mayBeEmpty = True
		_a_protocol = None
		_a_ivoId = None
		_name_a_ivoId = "ivo-id"

	class default(TRElement):
		_a_unit = None

	class hard(TRElement):
		_a_unit = None

	class version(TRElement):
		_a_ivoId = None
		_name_a_ivoId = "ivo-id"

	class languageFeatures(TRElement):
		_a_type = None

	class alias(TRElement): pass
	class description(TRElement): pass
	class executionDuration(TRElement): pass
	class mime(TRElement): pass 
	class name(TRElement): pass
	class parameter(TRElement): pass
	class protocol(TRElement): pass
	class retentionPeriod(TRElement): pass
	class outputLimit(TRElement): pass
	class form(TRElement): pass
	class uploadLimit(TRElement): pass
	class feature(TRElement): pass


class VSTD(object):
	"""A container for elements from StandardsRegExt.
	"""
	class VSTDElement(Element):
		_prefix = "vstd"
		_local = True

	class endorsedVersion(VSTDElement):
		_a_status = "n/a"
		_a_use = "preferred"
	
	class Standard(RI.Resource):
		_a_xsi_type = "vstd:Standard"
		_additionalPrefixes = frozenset(["vstd", "xsi"])

	class deprecated(VSTDElement): pass
	class key(VSTDElement): pass
	class description(VSTDElement): pass
	class name(VSTDElement): pass


class DOC(object):
	"""A container for elements from DocRegExt.
	"""
	class DOCElement(Element):
		_prefix = "doc"
		_local = True

	class Document(RI.Resource):
		_a_xsi_type = "doc:Document"
		_additionalPrefixes = frozenset(["doc", "xsi"])

	class language(DOCElement): pass
	class accessURL(DOCElement): pass
	class sourceURI(DOCElement): pass

