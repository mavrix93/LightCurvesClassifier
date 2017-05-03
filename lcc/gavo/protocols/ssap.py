"""
The SSAP core and supporting code.

"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from gavo import base
from gavo import rsc
from gavo import rscdef
from gavo import svcs
from gavo import utils
from gavo import votable
from gavo.formats import votablewrite
from gavo.protocols import datalink
from gavo.svcs import outputdef
from gavo.votable import V


RD_ID = "//ssap"
MS = base.makeStruct


def getRD():
	return base.caches.getRD(RD_ID)


class SSADescriptor(datalink.ProductDescriptor):
	ssaRow = None

	@classmethod
	def fromSSARow(cls, ssaRow, paramDict):
		"""returns a descriptor from a row in an ssa table and
		the params of that table.
		"""
		paramDict.update(ssaRow)
		# this could come from _combineRowIntoOne if it ran
		if "collected_calibs" in ssaRow:
			ssaRow["collected_calibs"].add(ssaRow["ssa_fluxcalib"])
			ssaRow["ssa_fluxcalib"] = ssaRow["collected_calibs"]

		ssaRow = paramDict
		res = cls.fromAccref(ssaRow["ssa_pubDID"], ssaRow['accref'])
		res.ssaRow = ssaRow
		return res


def _combineRowIntoOne(ssaRows):
	"""makes a "total row" from ssaRows.

	In the resulting row, minima and maxima are representative of the
	whole result set, and enumerated columsn are set-valued.

	This is useful when generating parameter metadata.
	"""
	if not ssaRows:
		raise base.ReportableError("Datalink meta needs at least one result row")

	totalRow = ssaRows[0].copy()
	totalRow["mime"] = set([totalRow["mime"]])
	calibs = set()

	for row in ssaRows[1:]:
		if row["ssa_specstart"]<totalRow["ssa_specstart"]:
			totalRow["ssa_specstart"] = row["ssa_specstart"]
		if row["ssa_specend"]>totalRow["ssa_specend"]:
			totalRow["ssa_specend"] = row["ssa_specend"]
		totalRow["mime"].add(row["mime"])
		calibs.add(row.get("ssa_fluxcalib", None))
	
	totalRow["collect_calibs"] = set(c for c in calibs if c is not None)
	return totalRow


def getDatalinkCore(dlSvc, ssaTable):
	"""returns a datalink core adapted for ssaTable.

	dlSvc is the datalink service, ssaTable a non-empty SSA result table.
	"""
	totalRow = _combineRowIntoOne(ssaTable.rows)
	desc = SSADescriptor.fromSSARow(totalRow, ssaTable.getParamDict())
	return dlSvc.core.adaptForDescriptors(svcs.getRenderer("dlmeta"), [desc])


class SSAPCore(svcs.DBCore):
	"""A core doing SSAP queries.

	This core knows about metadata queries, version negotiation, and 
	dispatches on REQUEST.  Thus, it may return formatted XML data
	under certain circumstances.

	SSAPCores also know how to handle getData requests according to the 2012
	draft.  This is done via datalink, and we expect parameters as per
	the sdm_* streams in datalink.
	"""
	name_ = "ssapCore"

	ssapVersion = "1.04"

	outputTableXML = """
		<outputTable verbLevel="30">
			<property name="virtual">True</property>
			<FEED source="//ssap#coreOutputAdditionals"/>
		</outputTable>"""

	def wantsTableWidget(self):
		# we only return XML, and we have a custom way of doing limits.
		return False

	# The following is evaluated by the form renderer to suppress the
	# format selection widget.  We should really furnish cores with
	# some way to declare what they're actually returning.
	HACK_RETURNS_DOC = True

	################ Helper methods

	def _makeMetadata(self, service):
		metaTD = self.outputTable.change(id="results")
		for param in metaTD.params:
			param.name = "OUTPUT:"+param.name
		dd = base.makeStruct(rscdef.DataDescriptor, parent_=self.rd,
			makes=[base.makeStruct(rscdef.Make, table=metaTD,
				rowmaker=base.makeStruct(rscdef.RowmakerDef))])
		dd.setMetaParent(service)

		for inP in self.inputTable.params:
			dd.feedObject("param", inP.change(name="INPUT:"+inP.name))

		dd.setMeta("_type", "meta")
		dd.addMeta("info", base.makeMetaValue(
			"", name="info", infoName="QUERY_STATUS", infoValue="OK"))
		dd.addMeta("info", base.makeMetaValue(
			"SSAP", name="info", infoName="SERVICE_PROTOCOL", infoValue="1.04"))

		data = rsc.makeData(dd)
		
		return base.votableType, votablewrite.getAsVOTable(data)

	def _declareGenerationParameters(self, resElement, datalinkCore):
		"""adds a table declaring getData support to resElement as appropriate.

		resElement is a votable.V RESOURCE element, datalinkCore
		is the datalink core adapted for the SSA table in resElement.

		Deprecated; this will go as we remove vintage getData support.
		"""
		# this assumes datalinkCore uses the ucds as in //datalink#sdm_*;
		# also, we only support the keywords we've supported in the original
		# getData implementation.
		paramTable = V.TABLE(name="generationParameters")

		for ik in datalinkCore.inputTable.params:
			if ik.name=="FLUXCALIB":
				paramTable[
					V.PARAM(name="FLUXCALIB", datatype="char", arraysize="*") [
						V.DESCRIPTION["Recalibrate the spectrum to..."],
						V.VALUES[[
							V.OPTION(value=option.content_, name=option.title)
								for option in ik.values.options]]]]

			elif ik.name=="LAMBDA_MIN":
				paramTable[
					V.PARAM(name="BAND", datatype="char", arraysize="m", unit="m")[
						V.DESCRIPTION["The spectral range of the cutout"],
						V.VALUES[
							V.MIN(value=ik.values.min),
							V.MAX(value=ik.values.max)]]]
			
			elif ik.name=="FORMAT":
				paramTable[
    			V.PARAM(name="FORMAT", datatype="char", arraysize="*",
			      	value="application/x-votable+xml") [
			      V.DESCRIPTION["Format to deliver the spectrum in."],
		      	V.VALUES[[
							V.OPTION(value=option.content_, name=option.title)
								for option in ik.values.options]]]]

			else:
				pass

		resElement[
			V.RESOURCE(name="getDataMeta")[
				paramTable]]


	############### Implementation of the service operations

	def _run_getData(self, service, inputTable, queryMeta):
		"""returns mime and payload for a getData operation on the parameters
		defined in inputTable.
		"""
		datalinkId = service.getProperty("datalink", None)
		if datalinkId is None:
			raise base.ValidationError("No getData support on %s"%
				service.getMeta("identifier"), "REQUEST", hint="Only SSAP"
						" services with a datalink property support getData")

		rawArgs = queryMeta.ctxArgs
		del rawArgs[utils.getKeyNoCase(rawArgs, "request")]
		# Also remove artificial parameter introduced by the SSA renderer
		if "_DBOPTIONS_LIMIT" in rawArgs:
			del rawArgs["_DBOPTIONS_LIMIT"]
		if "_FORMAT" in rawArgs:
			del rawArgs["_FORMAT"]

		if "BAND" in rawArgs:
			bandVal = utils.getfirst(rawArgs, "BAND")
			del rawArgs["BAND"]
			if bandVal:
				try:
					min, max = bandVal.split("/")
					if min:
						rawArgs["LAMBDA_MIN"] = min
					if max:
						rawArgs["LAMBDA_MAX"] = max
				except (ValueError, TypeError):
					# malformed BAND, complain
					raise base.ValidationError("BAND must have form [number]/[number].", 
						"BAND")

		# rename PUBDID (getData) to ID (datalink)
		if "PUBDID" not in rawArgs:
			raise base.ValidationError("Value is required but was not provided",
				"PUBDID")
		rawArgs["ID"] = rawArgs.pop("PUBDID")

		dlService = self.rd.getById(datalinkId)
		return dlService.run("dlget", rawArgs, queryMeta).original
			
	def _run_getTargetNames(self, service, inputTable, queryMeta):
		with base.getTableConn()  as conn:
			table = rsc.TableForDef(self.queriedTable, create=False,
				role="primary", connection=conn)
			destTD = base.makeStruct(outputdef.OutputTableDef, 
				parent_=self.queriedTable.parent,
				id="result", onDisk=False,
				columns=[self.queriedTable.getColumnByName("ssa_targname")])
			res = rsc.TableForDef(destTD, rows=table.iterQuery(destTD, "",
				distinct=True))
			res.noPostprocess = True
			return res

	def _run_queryData(self, service, inputTable, queryMeta):
		format = inputTable.getParam("FORMAT") or ""
		if format.lower()=="metadata":
			return self._makeMetadata(service)

		limits = [q for q in 
				(inputTable.getParam("MAXREC"), inputTable.getParam("TOP"))
			if q]
		if not limits:
			limits = [base.getConfig("ivoa", "dalDefaultLimit")]
		limit = min(min(limits), base.getConfig("ivoa", "dalHardLimit"))
		queryMeta["dbLimit"] = limit

		res = svcs.DBCore.run(self, service, inputTable, queryMeta)
		if len(res)==limit:
			queryStatus = "OVERFLOW"
			queryStatusBody = ("Exactly %s rows were returned.  This means your"
				" query probably reached the match limit.  Increase MAXREC."%limit)
		else:
			queryStatus = "OK"
			queryStatusBody = ""

		# We wrap our result into a data instance since we need to set the
		#	result type
		data = rsc.wrapTable(res)
		data.setMeta("_type", "results")
		data.addMeta("_votableRootAttributes",
			'xmlns:ssa="http://www.ivoa.net/xml/DalSsap/v1.0"')

		# The returnRaw property is a hack, mainly for unit testing;
		# The renderer would have to add the QUERY_STATUS here.
		if service.getProperty("returnData", False):
			return data

		# we fix tablecoding to td for now since nobody seems to like
		# binary tables and we don't have huge tables here.
		votCtx = votablewrite.VOTableContext(tablecoding="td")

		vot = votablewrite.makeVOTable(data, votCtx)
		pubDIDId = votCtx.getIdFor(res.tableDef.getColumnByName("ssa_pubDID"))
		resElement = vot.makeChildDict()["RESOURCE"][0]
		resElement[
			V.INFO(name="SERVICE_PROTOCOL", value=self.ssapVersion)["SSAP"],
			V.INFO(name="QUERY_STATUS", value=queryStatus)[
				queryStatusBody]]
	
		datalinkId = service.getProperty("datalink", None)
		if datalinkId and res:
			dlService = self.rd.getById(datalinkId)
			dlCore = getDatalinkCore(dlService, res)

			# old and stinky getData (remove at some point)
			self._declareGenerationParameters(vot, dlCore)

			# new and shiny datalink (keep)
			vot[dlCore.datalinkServices[0].asVOT(
				votCtx, dlService.getURL("dlget"), linkIdTo=pubDIDId)]

			# Also point to the dl metadata service
			vot[V.RESOURCE(type="meta", utype="adhoc:service")[
				V.PARAM(name="standardID", datatype="char", arraysize="*",
					value="ivo://ivoa.net/std/DataLink#links"),
				V.PARAM(name="accessURL", datatype="char", arraysize="*",
					value=self.rd.getById(datalinkId).getURL("dlmeta")),
				V.GROUP(name="inputParams")[
					V.PARAM(name="ID", datatype="char", arraysize="*", 
						ref=pubDIDId,
						ucd="meta.id;meta.main")[
						V.LINK(content_role="ddl:id-source", value="#"+pubDIDId)]]]]

		return "application/x-votable+xml", votable.asString(vot)

	################ the main dispatcher

	def run(self, service, inputTable, queryMeta):
		requestType = (inputTable.getParam("REQUEST") or "").upper()
		if requestType=="QUERYDATA":
			return self._run_queryData(service, inputTable, queryMeta)
		elif requestType=="GETDATA":
			return self._run_getData(service, inputTable, queryMeta)
		elif requestType=="GETTARGETNAMES":
			return self._run_getTargetNames(service, inputTable, queryMeta)
		else:
			raise base.ValidationError("Missing or invalid value for REQUEST.",
				"REQUEST")


class SSAPProcessCore(SSAPCore):
	"""Temporary Hack; delete when ccd700 is ported to a sane infrastructure.
	"""
	name_ = "ssapProcessCore"
