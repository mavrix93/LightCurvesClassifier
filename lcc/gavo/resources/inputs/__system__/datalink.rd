<!-- a collection of various helpers for building dataling services. -->

<resource resdir="__system" schema="dc">

	<table id="dlresponse">
		<meta name="description">Data links for data sets.</meta>
		<column name="ID" type="text"
			ucd="meta.id;meta.main"
			tablehead="PubDID"
			description="Publisher data set id; this is an identifier for
				the dataset in question and can be used to retrieve the data."
			verbLevel="1"/>
		<column name="access_url" type="text"
			ucd="meta.ref.url"
			tablehead="URL"
			description="URL to retrieve the data or access the service."
			verbLevel="1" displayHint="type=url"/>
		<column name="error_message" type="text"
			ucd="meta.code.error"
			tablehead="Why not?"
			description="If accessURL is empty, this column give the reason why."
			verbLevel="20"/>
		<column name="service_def" type="text"
			ucd="meta.code"
			tablehead="Svc. Type"
			description="Identifier for the type of service if accessURL refers
				to a service."
			verbLevel="1"/>
		<column name="description" type="text"
			ucd="meta.note"
			tablehead="Description"
			description="More information on this link"
			verbLevel="1"/>
		<column name="semantics" type="text"
			ucd="meta.code"
			tablehead="What?"
			description="What kind of data is linked here?  Standard identifiers
				here include science, calibration, preview, info, auxiliary" 
				verbLevel="1"/>
		<column name="content_type" type="text"
			ucd="meta.code.mime"
			tablehead="MIME"
			description="MIME type for the data returned."
			verbLevel="1"/>
		<column name="content_length" type="bigint"
			ucd="phys.size;meta.file" unit="byte"
			tablehead="Size"
			description="Size of the resource at access_url"
			verbLevel="1">
			<values nullLiteral="-1"/>
		</column>
	</table>

	<data id="make_response">
		<!-- this data build a datalink response table out of LinkDefs.
		The input parameters for the computational part are built in
		within datalink.getDatalinkDescriptionResource. -->
		<embeddedGrammar>
			<iterator>
				<code>
					for linkDef in self.sourceToken:
						yield linkDef.asDict()
				</code>
			</iterator>
		</embeddedGrammar>
		
		<make table="dlresponse"/>
	</data>

<!-- ********************* generic datalink procs -->

	<procDef type="descriptorGenerator" id="fromStandardPubDID">
		<doc>A descriptor generator for datalink that builds a 
		ProductDescriptor for PubDIDs that have been built by getStandardsPubDID
		(i.e., the path part of the IVORN is a tilda, with the
		products table accref as the query part).
		</doc>
		<code>
			return ProductDescriptor.fromAccref(
				pubDID,
				getAccrefFromStandardPubDID(pubDID))
		</code>
	</procDef>

	<procDef type="dataFormatter" id="trivialFormatter">
		<doc>The tivial formatter for datalink processed data -- it just
		returns descriptor.data, which will only work it it works as a
		nevow resource.

		If you do not give any dataFormatter yourself in a datalink core,
		this is what will be used.
		</doc>
		<code>
			return descriptor.data
		</code>
	</procDef>


	<!-- ********************* datalink interface to generic products -->

	<procDef type="dataFunction" id="generateProduct">
		<doc>A data function for datalink that returns a product instance.
		You can restrict the mime type of the product requested so the
		following filters have a good idea what to expect.
		</doc>
		<setup>
			<par key="requireMimes" description="A set or sequence of mime type 
				strings; when given, the data generator will bail out with 
				ValidationError if the product mime is not among the mimes
				given.">frozenset()</par>
			<code>
				from gavo.protocols import products
			</code>
		</setup>
		<code>
			if requireMimes and descriptor.mime not in requireMimes:
				raise base.ValidationError("Document type not supported: %s"%
					descriptor.mime, colName="PUBDID", hint="Only source documents"
					" of the types %s are supported here."%str(requireMimes))

			descriptor.data = products.getProductForRAccref(descriptor.accref)
		</code>
	</procDef>


	<!-- ********************* datalink interface to SDM spectra -->

	<procDef type="descriptorGenerator" id="sdm_genDesc">
		<doc>A data function for datalink returning the product row
		corresponding to a PubDID within an SSA table.

		The descriptors generated have an ssaRow attribute containing
		the original row in the SSA table.
		</doc>
		<setup>
			<par key="ssaTD" description="Full reference (like path/rdname#id)
				to the SSA table the spectrum's PubDID can be found in."/>

			<code>
				from gavo import rscdef
				from gavo import rsc
				from gavo import svcs
				from gavo.protocols import ssap
				ssaTD = base.resolveCrossId(ssaTD, rscdef.TableDef)
			</code>
		</setup>
		
		<code>
			with base.getTableConn() as conn:
				ssaTable = rsc.TableForDef(ssaTD, connection=conn)
				matchingRows = list(ssaTable.iterQuery(ssaTable.tableDef, 
					"ssa_pubdid=%(pubdid)s", {"pubdid": pubDID}))
				if not matchingRows:
					return DatalinkError.NotFoundError(pubDID,
						"No spectrum with this pubDID known here")

				# the relevant metadata for all rows with the same PubDID should
				# be identical, and hence we can blindly take the first result.
				return ssap.SSADescriptor.fromSSARow(matchingRows[0],
					ssaTable.getParamDict())
		</code>
	</procDef>

	<procDef type="dataFunction" id="sdm_genData">
		<doc>A data function for datalink returning a spectral data model
		compliant table that later data functions can then work on.
		As usual for generators, it uses the implicit PUBDID argument.
		</doc>
		<setup>
			<par key="builder" description="Full reference (like path/rdname#id)
				to a data element building the SDM instance table as its
				primary table."/>
			<code>
				from gavo import rscdef
				builder = base.resolveCrossId(builder, rscdef.DataDescriptor)
			</code>
		</setup>

		<code>
			from gavo.protocols import sdm
			descriptor.data = sdm.makeSDMDataForSSARow(descriptor.ssaRow, builder)
		</code>
	</procDef>

	<STREAM id="sdm_plainfluxcalib">
		<doc>A stream inserting a data function and its metadata generator to
		do select flux calibrations in SDM data.  This expects
		sdm_generate (or at least parameters.data as an SDM data instance)
		as the generating function within the datalink core.

		Clients can select "RELATIVE" as FLUXCALIB, which does a
		normalization to max(flux)=1 here.  Everything else is rejected
		right now.

		This probably is more an example of how to write such a thing
		then genuinely useful.
		</doc>
		<metaMaker>
			<code>
				supportedCalibs = set(["RELATIVE"])
				foundCalibs = descriptor.ssaRow["ssa_fluxcalib"]
				if isinstance(foundCalibs, basestring):
					foundCalibs = set([foundCalibs])
				supportedCalibs.update(foundCalibs)

				yield MS(InputKey, name="FLUXCALIB", type="text",
					multiplicity="single",
					ucd="phot.calib",
					utype="ssa:Char.FluxAxis.Calibration",
					description="Recalibrate the spectrum.  Right now, the only"
						" recalibration supported is max(flux)=1 ('RELATIVE').",
						values=MS(Values, options=[
							MS(Option, content_=val) for val in supportedCalibs]))
			</code>
		</metaMaker>

		<dataFunction>
			<code>
				if not args.get("FLUXCALIB"):
					return

				from gavo.protocols import sdm
				# table is changed in place
				sdm.mangle_fluxcalib(descriptor.data.getPrimaryTable(), 
					args["FLUXCALIB"])
				</code>
		</dataFunction>
	</STREAM>

	<STREAM id="sdm_cutout">
		<doc>A stream inserting a data function and its metaMaker to
		do cutouts in SDM data. This expects sdm_generate (or at least
		parameters.data as an SDM data instance) as the generating function 
		within the datalink core.

		The cutout limits are always given in meters, regardless of
		the spectrum's actual units (as in SSAP's BAND parameter).
		</doc>

  	<metaMaker>
    	<setup>
      	<code>
        	parSTC = stc.parseQSTCS('SpectralInterval "LAMBDA_MIN" "LAMBDA_MAX"')
      	</code>
    	</setup>
    	<code>
				for ik in genLimitKeys(MS(InputKey, name="LAMBDA",
					unit="m", stc=parSTC, ucd="em.wl", 
					description="Spectral cutout interval",
					values=MS(Values, 
						min=descriptor.ssaRow["ssa_specstart"],
						max=descriptor.ssaRow["ssa_specend"]))):
					yield ik
    	</code>
  	</metaMaker>

		<dataFunction>
			<code>
				if not args.get("LAMBDA_MIN") and not args.get("LAMBDA_MAX"):
					return

				from gavo.protocols import sdm
				# table is modified in place
				sdm.mangle_cutout(
					descriptor.data.getPrimaryTable(),
					args["LAMBDA_MIN"] or -1, args["LAMBDA_MAX"] or 1e308)
			</code>
		</dataFunction>
	</STREAM>

	<STREAM id="sdm_format">
		<doc>A formatter for SDM data, together with its input key
		for FORMAT.
		</doc>

		<metaMaker>
			<code>
				formatsAvailable = {
						"application/x-votable+xml": "VOTable, binary encoding",
						"application/x-votable+xml;serialization=tabledata": 
							"VOTable, tabledata encoding",
						"text/plain": "Tab separated values",
						"text/csv": "Comma separated values",
						"application/fits": "FITS binary table"}

				mimesFound = descriptor.mime
				if isinstance(mimesFound, basestring):
					mimesFound = set([mimesFound])
				for mime in mimesFound:
					if mime not in formatsAvailable:
						formatsAvailable[mime] = "Original format"

				yield MS(InputKey, name="FORMAT", type="text",
					ucd="meta.code.mime",
					utype="ssa:Access.Format",
					multiplicity="single",
					description="MIME type of the output format",
					values = MS(Values,
						options = [MS(Option, title=value, content_=key)
							for key, value in formatsAvailable.iteritems()]))
			</code>
		</metaMaker>

		<dataFormatter>
			<code>
				from gavo.protocols import sdm

				return sdm.formatSDMData(descriptor.data, args["FORMAT"])
			</code>
		</dataFormatter>
	</STREAM>


	<!-- ********************* datalink interface for generic FITS 
		manipulations -->
	<procDef type="descriptorGenerator" id="fits_genDesc">
		<doc>A data function for datalink returning the a fits descriptor.

		This has, in addition to the standard stuff, a hdr attribute containing
		the primary header as pyfits structure.

		The functionality of this is in its setup, getFITSDescriptor.
		The intention is that customized DGs (e.g., fixing the header)
		can use this as an original.
		</doc>
		<setup>
			<code>
				def getFITSDescriptor(pubDID):
					try:
						accref = getAccrefFromStandardPubDID(pubDID)
					except ValueError:
						return DatalinkError.NotFoundError(pubDID,
							"Not a pubDID from this site.")

					if accrefStart and not accref.startswith(accrefStart):
						return DatalinkError.AuthenticationError(pubDID,
							"This datalink service not available"
							" with this pubDID")

					descriptor = ProductDescriptor.fromAccref(pubDID, accref)
					with open(os.path.join(base.getConfig("inputsDir"), 
							descriptor.accessPath)) as f:
						descriptor.hdr = utils.readPrimaryHeaderQuick(f,
							maxHeaderBlocks=100)
					
					# see fits_doWCSCutout for more info this
					descriptor.slices = []

					return descriptor
			</code>

			<par key="accrefStart" description="A start of accrefs the parent
				datalink service works of.  Procedures on all other accrefs
				will be rejected with a 403 forbidden.  You should always
				include a restriction like this when you make assumptions
				about the FITSes (e.g., what axes are available).">None</par>
		</setup>
		<code>
			return getFITSDescriptor(pubDID)
		</code>
	</procDef>


	<procDef type="metaMaker" id="fits_makeWCSParams">
		<doc>A metaMaker that generates parameters allowing cutouts along
		the various WCS axes in physical coordinates.
	
		This uses pywcs for the spatial coordinates and tries to figure out 
		what these are with some heuristics.  For the remaining coordinates,
		it assumes all are basically 1D, and it sets up separate, manual
		transformations for them.

		The metaMaker leaves an axisNames mapping in the descriptor.
		This is important for the fits_doWCSCutout, and replacement metaMakers
		must do the same.

		The meta maker also creates a skyWCS attribute in the descriptor
		if successful, containing the spatial transformation only.  All
		other transformations, if present, are in miscWCS, by a dict mapping
		axis labels to the fitstools.WCS1Trans instances.
		
		If individual metadata in the header are wrong or to give better
		metadata, use axisMetaOverrides.  This will not generate standard
		parameters for non-spatial axis (LAMBDA and friends).  There are
		other datalink streams for those.
		</doc>
		<setup>
			<par key="stcs" description="A QSTC expression describing the
				STC structure of the parameters.  If you don't give this,
				no STC structure will be declared.">None</par>
			<par key="axisMetaOverrides" description="A python dictionary
				mapping fits axis indices (1-based) to dictionaries of
				inputKey constructor arguments; for spatial axis, use the
				axis name instead of the axis index.">{}</par>
			<code>
				from gavo.utils import fitstools

				def getSkyWCS(hdr):
					"""uses some heuristics to guess how spatial WCS might be
					in hdr.

					The function returns a pair of a pywcs.WCS instance (or
					None, if no spatial WCS was found) and a sequence of 
					the axes used.
					"""
					wcsAxes = []
					# heuristics: iterate through CTYPEn, anything that's got
					# a - is supposed to be a position (needs some refinement :-)
					for ind in range(1, hdr["NAXIS"]+1):
						if "-" in hdr.get("CTYPE%s"%ind, ""):
							wcsAxes.append(ind)

					if not wcsAxes:
						# more heuristics to be inserted here
						return None, ()

					if len(wcsAxes)!=2:
						raise base.ValidationError("This FITS has !=2"
							" spatial WCS axes.  Please contact the DaCHS authors and"
							" make them support it.", "PUBDID")

					return coords.getWCS(hdr, naxis=wcsAxes), wcsAxes

				def iterSpatialKeys(descriptor):
					"""yields inputKeys for spatial cutouts along the coordinate
					axes.

					This can be nothing if descriptor doesn't have a skyWCS attribute
					or if it's None.
					"""
					if not getattr(descriptor, "skyWCS", None):
						return

					footprint = descriptor.skyWCS.calcFootprint(descriptor.hdr)
					wcsprm = descriptor.skyWCS.wcs

					# FIXME: UCD inference!
					for name, colInd, description, baseUCD, cutoutName in [
						(wcsprm.lattyp.strip(), wcsprm.lat, "The latitude coordinate",
							"pos.eq.dec", "WCSLAT"),
						(wcsprm.lngtyp.strip(), wcsprm.lng, "The longitude coordinate",
							"pos.eq.ra", "WCSLONG")]:
						if name:
							vertexCoos = footprint[:,colInd]
							paramArgs = {"name": name, "unit": "deg", 
									"description": description,
									"ucd": baseUCD}
							if name in axisMetaOverrides:
								paramArgs.update(axisMetaOverrides[name])

							for ik in genLimitKeys(MS(InputKey,  multiplicity="single",
									stc=parSTC,
									values=MS(Values, min=min(vertexCoos), max=max(vertexCoos)),
									**paramArgs)):
								yield ik
							descriptor.axisNames[name] = cutoutName

				def iterOtherKeys(descriptor, spatialAxes):
					"""yields inputKeys for all WCS axes not covered by spatialAxes.
					"""
					axesLengths = fitstools.getAxisLengths(descriptor.hdr)
					for axIndex, length in enumerate(axesLengths):
						fitsAxis = axIndex+1
						if fitsAxis in spatialAxes:
							continue
						if length==1:
							# no cutouts along degenerate axes
							continue

						ax = fitstools.WCSAxis.fromHeader(descriptor.hdr, fitsAxis)
						descriptor.axisNames[ax.name] = fitsAxis
						minPhys, maxPhys = ax.getLimits()

						# FIXME: ucd inference
						paramArgs = {"name": ax.name, "unit": ax.cunit, 
							"stc": parSTC,
							"description": "Coordinate along axis number %s"%fitsAxis,
							"ucd": None}
						if fitsAxis in axisMetaOverrides:
							paramArgs.update(axisMetaOverrides[fitsAxis])

						for ik in genLimitKeys(MS(InputKey,  multiplicity="single",
							values=MS(Values, min=minPhys, max=maxPhys),
							**paramArgs)):
							yield ik

				if stcs is None:
					parSTC = None
				else:
					parSTC = stc.parseQSTCS(stcs)
			</code>
		</setup>

		<code>
			descriptor.axisNames = {}
			descriptor.skyWCS, spatialAxes = getSkyWCS(descriptor.hdr)

			for ik in iterSpatialKeys(descriptor):
				yield ik

			for ik in iterOtherKeys(descriptor, spatialAxes):
				yield ik
		</code>
	</procDef>

	<procDef type="dataFunction" id="fits_makeHDUList">
		<doc>
			An initial data function to construct a pyfits hduList and
			make that into a descriptor's data attribute.

			This wants a descriptor as returned by fits_genDesc.
		</doc>
		<setup>
			<par key="crop" description="Cut away everything but the
				primary HDU?">True</par>
		</setup>
		<code>
			from gavo.utils import pyfits

			descriptor.data = pyfits.open(os.path.join(
				base.getConfig("inputsDir"), descriptor.accessPath))
			if crop:
				descriptor.data = pyfits.HDUList([descriptor.data[0]])
		</code>
	</procDef>

	<procDef type="dataFunction" id="fits_doWCSCutout">
		<doc>
			A fairly generic FITS cutout function.

			It expects some special attributes in the descriptor to allow it
			to decode the arguments.  These must be left behind by the
			metaMaker(s) creating the parameters.

			This is axisNames, a dictionary mapping parameter names to
			the FITS axis numbers or the special names WCSLAT or WCSLONG. 
			It also expects a skyWCS attribute, a pywcs.WCS instance for spatial
			cutouts.

			Finally, descriptor must have a list attribute slices, containing
			zero or more tuples of (fits axis, lowerPixel, upperPixel); this
			allows things like LAMBDA to add their slices obtained
			from parameters in standard units.

			The .data attribute must be a pyfits hduList, as generated by the
			fits_makeHDUList data function.
		</doc>
		<code>
			from gavo.utils import fitstools
			import numpy

			slices = descriptor.slices

			footprint  = descriptor.skyWCS.calcFootprint(descriptor.hdr)
			# limits: [minRA, maxRA], [minDec, maxDec]]
			limits = [[min(footprint[:,0]), max(footprint[:,0])],
				[min(footprint[:,1]), max(footprint[:,1])]]

			for parBase, fitsAxis in descriptor.axisNames.iteritems():
				if args[parBase+"_MIN"] is None and args[parBase+"_MAX"] is None:
					continue

				if not isinstance(fitsAxis, int):
					# some sort of spherical axis
					if fitsAxis=="WCSLAT":
						cooLimits = limits[1]
					elif fitsAxis=="WCSLONG":
						cooLimits = limits[0]
					else:
						assert False

					if args[parBase+"_MIN"] is not None:
						cooLimits[0] = max(cooLimits[0], args[parBase+"_MIN"])
					if args[parBase+"_MAX"] is not None:
						cooLimits[1] = min(cooLimits[1], args[parBase+"_MAX"])
					
				else:
					# 1-d axis
					transform = fitstools.WCSAxis.fromHeader(descriptor.hdr, fitsAxis)
					axMin = args[parBase+"_MIN"]
					axMax = args[parBase+"_MAX"]
					slices.append((fitsAxis, 
						transform.physToPix(axMin), transform.physToPix(axMax)))
		
			pixelFootprint = numpy.asarray(
				numpy.round(descriptor.skyWCS.wcs_sky2pix([
					(limits[0][0], limits[1][0]),
					(limits[0][1], limits[1][1])], 1)), numpy.int32)
			pixelLimits = [[min(pixelFootprint[:,0]), max(pixelFootprint[:,0])],
				[min(pixelFootprint[:,1]), max(pixelFootprint[:,1])]]
			latAxis = descriptor.skyWCS.latAxis
			longAxis = descriptor.skyWCS.longAxis
			if pixelLimits[0]!=[1, descriptor.hdr["NAXIS%d"%longAxis]]:
				slices.append([longAxis]+pixelLimits[0])
			if pixelLimits[1]!=[1, descriptor.hdr["NAXIS%d"%latAxis]]:
				slices.append([latAxis]+pixelLimits[1])

			if slices:
				descriptor.data[0] = fitstools.cutoutFITS(descriptor.data[0],
					*slices)
		</code>
	</procDef>

	<procDef type="dataFormatter" id="fits_formatHDUs">
		<doc>
			Formats pyfits HDUs into a FITS file.

			This all works in memory, so for large FITS files you'd want something
			more streamlined.
		</doc>
		<code>
			from gavo.formats import fitstable
			resultName = fitstable.writeFITSTableFile(descriptor.data)
			with open(resultName) as f:
				data = f.read()
			os.unlink(resultName)
			return "application/fits", data
		</code>
	</procDef>

	<STREAM id="fits_genKindPar">
		<doc>This stream should be included in FITS-handling datalink services;
		it adds parameter and code to just retrieve the FITS header to the
		core.
		
		For this to work as expected, it must be immediately before the
		formatter.</doc>
		<metaMaker name="genKindPar">
			<code>
				yield MS(InputKey, name="KIND", type="text",
					multiplicity="single", description="Set to HEADER"
					" to retrieve just the primary header, leave empty for data.",
					values = MS(Values,
						options = [MS(Option, content_="HEADER", 
							title="Retrieve header only")]))
			</code>
		</metaMaker>

		<dataFunction>
			<setup>
				<code>
					from gavo.utils import fitstools
				</code>
			</setup>
			<code>
				if args["KIND"]=="HEADER":
					descriptor.data = ("application/fits-header", 
						fitstools.serializeHeader(descriptor.data[0].header))
					raise DeliverNow()
			</code>
		</dataFunction>
	</STREAM>

	<STREAM id="fits_genPixelPar">
		<doc>This stream should be included  in FITS-handling datalink services;
		it add parameters and code to perform cut-outs along pixel coordinates.
		</doc>
		<metaMaker name="genPixelPars">
			<code>
				for axisInd in range(descriptor.hdr["NAXIS"]):
					fitsInd = axisInd+1
					minVal, maxVal = 1, descriptor.hdr["NAXIS%s"%fitsInd]
					if maxVal==minVal:
						continue

					for ik in genLimitKeys(MS(InputKey, name="PIXEL_%s"%fitsInd,
							type="integer", unit="",
							description="Pixel coordinate along axis %s"%fitsInd,
							ucd="pos.cartesian;instr.pixel", multiplicity="single",
							values=MS(Values, min=minVal, max=maxVal))):
						yield ik
			</code>
		</metaMaker>

		<dataFunction name="cutoutPixelPars">
			<code>
				from gavo.utils import fitstools
				slices = []
				for fitsInd in range(1, descriptor.hdr["NAXIS"]+1):
					parBase = "PIXEL_%s"%fitsInd
					axMin, axMax = args[parBase+"_MIN"], args[parBase+"_MAX"]
					if axMin is not None or axMax is not None:
						slices.append([fitsInd, axMin, axMax])

				if slices:
					descriptor.data[0] = fitstools.cutoutFITS(descriptor.data[0],
						*slices)
			</code>
		</dataFunction>
	</STREAM>

	<procDef type="metaMaker" id="fits_makeLambdaMeta">
		<doc>
			Yields standard lambda params.

			This adds lambdaToMeterFactor and lambdaAxis attributes to the
			descriptor for later use by 
		</doc>
		<setup>
			<par key="fitsAxis" description="FITS axis index (1-based) of
				the wavelength dimension">3</par>
			<par key="wavelengthUnit" description="Override for the FITS
				unit given for the wavelength (for when it is botched or
				missing; leave at None for taking it from the header)">None</par>
			<code>
				from gavo.utils import fitstools
			</code>
		</setup>
		<code>
			if not wavelengthUnit:
				fitsUnit = descriptor.hdr["CUNIT%d"%fitsAxis]
			descriptor.lambdaToMeterFactor = base.computeConversionFactor(
				wavelengthUnit, "m")
			descriptor.lambdaAxis = fitstools.WCSAxis.fromHeader(
				descriptor.hdr, fitsAxis)
			descriptor.lambdaAxisIndex = fitsAxis

			minPhys, maxPhys = descriptor.lambdaAxis.getLimits()
			for ik in genLimitKeys(MS(InputKey, name="LAMBDA", unit="m",
				ucd="em.wl", description="Spectral wavelength",
				multiplicity="single",
				values=MS(Values, 
					min=minPhys*descriptor.lambdaToMeterFactor, 
					max=maxPhys*descriptor.lambdaToMeterFactor))):
				yield ik
		</code>
	</procDef>

	<procDef type="dataFunction" id="fits_makeLambdaSlice">
		<doc>
			Computes a cutout for the parameters added by makeLambdaMeta.

			This *must* sit in front of doWCSCutout.

			This also reuses internal state added by makeLambdaMeta,
			so this really only makes sense together with it.
		</doc>
		<code>
			if not args.get("LAMBDA_MIN") and not args.get("LAMBDA_MAX"):
				return
			axMax = args["LAMBDA_MAX"]
			if axMax is not None:
				axMax /= descriptor.lambdaToMeterFactor
			axMin = args["LAMBDA_MIN"]
			if axMin is not None:
				axMin /= descriptor.lambdaToMeterFactor
		
			transform = descriptor.lambdaAxis
			descriptor.slices.append(
				(descriptor.lambdaAxisIndex, transform.physToPix(axMin),
					transform.physToPix(axMax)))
		</code>
	</procDef>

	<STREAM id="fits_standardLambdaCutout">
		<doc>
			Adds metadata and processor for one axis containing wavelengths.

			(this could be extended to cover frequency and energy axis, I guess)
			
			To use this, give the fits axis containing the spectral coordinate
			in the spectralAxis attribute; if needed, you can override the
			unit in wavelengthUnit (if the unit in the header is somehow 
			bad or missing).
		</doc>

		<metaMaker procDef="//datalink#fits_makeLambdaMeta">
			<bind key="fitsAxis">\spectralAxis</bind>
			<bind key="wavelengthUnit">\wavelengthUnit</bind>
		</metaMaker>
		<dataFunction procDef="//datalink#fits_makeLambdaSlice"/>
	</STREAM>

	<STREAM id="fits_standardDLFuncs">
		<doc>
			Pulls in all "standard" datalink functions for FITSes, including
			cutouts and header retrieval.

			You must give both an stcs attribute (for fits_makeWCSParams) and an
			accrefStart attribute (for fits_genDesc).  Both can be empty,
			however (but if you think you should be leaving them empty you
			should probably think again).

			Do *not* add quotes to them, even though the proc parameters
			have them; the STREAM already puts in single quotes.
		</doc>
		<descriptorGenerator procDef="//datalink#fits_genDesc" name="genFITSDesc">
			<bind key="accrefStart">'\accrefStart'</bind>
		</descriptorGenerator>
		<metaMaker procDef="//datalink#fits_makeWCSParams" name="getWCSParams">
			<bind key="stcs">'\stcs'</bind>
		</metaMaker>
		<dataFunction procDef="//datalink#fits_makeHDUList" name="makeHDUList"/>
		<dataFunction procDef="//datalink#fits_doWCSCutout" name="doWCSCutout"/>
		<FEED source="//datalink#fits_genPixelPar"/>
		<FEED source="//datalink#fits_genKindPar"/>
		<dataFormatter procDef="//datalink#fits_formatHDUs" name="formatHDUs"/>
	</STREAM>


	<!-- ************************************************ async support -->

	<table id="datalinkjobs" onDisk="True" system="True">
		<meta name="description">A table managing datalink jobs submitted
			asynchronously (the dlasync renderer)</meta>

		<FEED source="//uws#uwsfields"/>
		<column name="pid" type="integer" 
				description="A unix pid to kill to make the job stop">
			<values nullLiteral="-1"/>
		</column>
	</table>

	<data id="import">
		<make table="datalinkjobs"/>
	</data>

</resource>
