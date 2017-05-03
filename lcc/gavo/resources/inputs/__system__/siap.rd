<?xml version="1.0" encoding="utf-8"?>
<!-- mixin definition for tables implementing the siap interface(s) -->

<resource resdir="__system" schema="dc">

	<STREAM id="SIAPbase">
		<FEED source="//products#tablecols"/>
		<column name="centerAlpha"  ucd="POS_EQ_RA_MAIN"
			type="double precision" unit="deg" 
			displayHint="sf=2" verbLevel="0" tablehead="Ctr. RA"
			description="Approximate center of image, RA"/>
		<column name="centerDelta"  ucd="POS_EQ_DEC_MAIN" tablehead="Ctr. Dec"
			type="double precision" unit="deg"
			displayHint="sf=2" verbLevel="0"
			description="Approximate center of image, Dec"/>
		<column name="imageTitle"  ucd="VOX:Image_Title"
			type="text" tablehead="Title" verbLevel="0"
			description="Synthetic name of the image"/>
		<column name="instId"  ucd="INST_ID"
			type="text" tablehead="Instrument" verbLevel="15"
			description="Identifier of the originating instrument"/>
		<column name="dateObs"  ucd="VOX:Image_MJDateObs"
			type="double precision" unit="d" tablehead="Obs. date"
			verbLevel="0" description="Epoch at midpoint of observation"
			displayHint="type=humanDate"
			xtype="mjd"/>
		<column name="nAxes"  ucd="VOX:Image_Naxes"
			type="integer" verbLevel="20" tablehead="#axes"
			description="Number of axes in data">
			<values nullLiteral="-1"/>
		</column>
		<column name="pixelSize"  ucd="VOX:Image_Naxis"
			type="integer[]" verbLevel="15" tablehead="Axes Lengths"
			description="Number of pixels along each of the axes"
			unit="pix"/>
		<column name="pixelScale"  ucd="VOX:Image_Scale"
			type="real[]" verbLevel="12" tablehead="Scales"
			description="The pixel scale on each image axis"
			unit="deg/pix"/>
		<column name="refFrame"  type="text"
			ucd="VOX:STC_CoordRefFrame" verbLevel="20"
			tablehead="Ref. Frame" 
			description="Coordinate system reference frame"/>
		<column name="wcs_equinox" ucd="VOX:STC_CoordEquinox"
			 verbLevel="20" tablehead="Equinox"
			description="Equinox of the given coordinates" unit="yr"/>
		<column name="wcs_projection" ucd="VOX:WCS_CoordProjection"
			 type="text" verbLevel="20"
			tablehead="Proj." description="FITS WCS projection type"/>
		<column name="wcs_refPixel" ucd="VOX:WCS_CoordRefPixel"
			 type="real[]" verbLevel="20"
			tablehead="Ref. pixel" description="WCS reference pixel"
			unit="pix"/>
		<column name="wcs_refValues" ucd="VOX:WCS_CoordRefValue"
			 type="double precision[]"
			verbLevel="20" tablehead="Ref. values"
			description="World coordinates at WCS reference pixel"
			unit="deg"/>
		<column name="wcs_cdmatrix" ucd="VOX:WCS_CDMatrix" verbLevel="20"
			 type="real[]" tablehead="CD matrix"
			description="FITS WCS CDij matrix" unit="deg/pix"/>
		<column name="bandpassId" ucd="VOX:BandPass_ID" 
			tablehead="Bandpass" description="Freeform name of the bandpass used"
			 type="text" verbLevel="10"/>
		<column name="bandpassUnit" ucd="VOX:BandPass_Unit"
			description="Unit of bandpass specifications"
			tablehead="Bandpass unit"
			 type="text" verbLevel="20"/>
		<column name="bandpassRefval" ucd="VOX:BandPass_RefValue"
			 verbLevel="20" tablehead="Band Ref."
			description="Characteristic quantity for the bandpass of the image"/>
		<column name="bandpassHi" ucd="VOX:BandPass_HiLimit"
			 verbLevel="20" tablehead="Band upper"
			description="Upper limit of the bandpass (in BandPass_Unit units)"/>
		<column name="bandpassLo" ucd="VOX:BandPass_LoLimit"
			 verbLevel="20" tablehead="Band lower"
			description="Lower limit of the bandpass (in BandPass_Unit units)"/>
		<column name="pixflags" ucd="VOX:Image_PixFlags" verbLevel="20"
			 type="text" tablehead="P. Flags"
			description="Flags specifying the processing done (C-original; F-resampled; Z-fluxes valid; X-not resampled; V-for display only"/>
	</STREAM>

	<mixinDef id="bbox">
		<doc>
			A table mixin for simple support of SIAP based on hand-made bboxes.

			The columns added into the tables include

				- (certain) FITS WCS headers 
				- imageTitle (interpolateString should come in handy for these)
				- instId -- some id for the instrument used
				- dateObs -- MJD of the "characteristic" observation time
				- the bandpass* values.  You're on your own with them...
				- the values of the //products#table mixin.  
				- mimetype -- the mime type of the product.
				- the primaryBbox, secondaryBbox, centerAlpha and centerDelta, nAxes, 
					pixelSize, pixelScale, wcs* fields calculated by the 
					computeBboxSIAPFields macro.   

			(their definition is in the siap system RD)

			Tables mixing in //siap#bbox can be used for SIAP querying and
			automatically mix in the products table mixin.

			To feed these tables, use the //siap#computeBbox and 
			//siap#setMeta procs.  Since you are dealing with products, you will also
			need the //products#define rowgen in your grammar.

			If you have pgSphere, you definitely should use the pgs mixin in
			preference to this.
		</doc>
		
		<FEED source="//products#hackProductsData"/>

		<events>
			<FEED source="//siap#SIAPbase"/>
			<column name="primaryBbox"  
				type="box" description="Bounding box of the image for internal use"
				displayHint="type=suppress"/>
			<column name="secondaryBbox"  
				type="box" description="Bounding box of the image for internal use"
				displayHint="type=suppress"/>
		</events>
	</mixinDef>


	<mixinDef id="pgs">
		<doc>
			A table mixin for simple support of SIAP.

			The columns added into the tables include

				- (certain) FITS WCS headers 
				- imageTitle (interpolateString should come in handy for these)
				- instId -- some id for the instrument used
				- dateObs -- MJD of the "characteristic" observation time
				- the bandpass* values.  You're on your own with them...
				- the values of the product mixin.  
				- mimetype -- the mime type of the product.
				- the coverage, centerAlpha and centerDelta, nAxes, 
					pixelSize, pixelScale, wcs* fields calculated by the 
					computePGS macro.   

			(their definition is in the siap system RD)

			Tables mixing in pgs can be used for SIAP querying and
			automatically mix in the products table mixin.

			To feed these tables, use the //siap#computePGS and 
			//siap#setMeta procs.  Since you are dealing with products, 
			you will also need the //products#define rowgen in your grammar.
		</doc>
		<FEED source="//products#hackProductsData"/>

		<events>
			<stc>
				Time TT "dateObs"
				Polygon ICRS [coverage] Position "centerAlpha" "centerDelta"
				SpectralInterval "bandpassLo" "bandpassHi" Spectral "bandpassRefval"
					unit m
			</stc>
			<FEED source="//siap#SIAPbase"/>
			<column name="coverage" type="spoly" unit="deg"
				description="Field covered by the image"/>
			<index columns="coverage" name="pgspos" method="GIST"/>
		</events>
	</mixinDef>


	<procDef type="apply" id="computeInputBase">
		<doc>
			Computes WCS information for SIA tables from FITS WCS keys.

			It takes no arguments but expects WCS-like keywords in rowdict, i.e.,
			CRVAL1, CRVAL2 (interpreted as float deg), CRPIX1, CRPIX2 (pixel
			corresponding to CRVAL1, CRVAL2), CUNIT1, CUNIT2 (pixel scale unit,
			we bail out if it isn't deg and assume deg when it's not present), 
			CDn_n (the transformation matrix; substitutable by CDELTn), NAXISn 
			(the image size).

			Records without or with insufficient wcs keys are furnished with
			all-NULL wcs info if the missingIsError setup parameter is False,
			else they bomb out with a DataError (the default).

			Use either computePGS or computeBbbox depending on what mixin
			the table has.  PGS is much preferable.
		</doc>
		<!-- Actually, this is a common base for both bbox and pgsphere based
		procs -->
		<setup>
			<par name="missingIsError" description="Throw an exception when
				no WCS information can be located.">True</par>
			<par name="naxis" description="Comma-separated list of integer
				axis indices (1=first) to be considered for WCS">"1,2"</par>
			<code>
				from gavo.protocols import siap

				wcskeys = ["centerAlpha", "centerDelta",
					"nAxes",  "pixelSize", "pixelScale", "wcs_projection",
					"wcs_refPixel", "wcs_refValues", "wcs_cdmatrix", "wcs_equinox"]

				naxis = map(int, naxis.split(","))

				class PixelGauge(object):
					"""is a container for information about pixel sizes.

					It is constructed with an pywcs.WCS instance and an (x, y)
					pair of pixel coordinates that should be close to the center 
					of the frame.
					"""
					def __init__(self, wcs, centerPix):
						self.centerPos = coords.pix2sky(wcs, centerPix)
						self.pixelScale = coords.getPixelSizeDeg(wcs)
						offCenterPos = coords.pix2sky(wcs,
							(centerPix[0]+1, centerPix[1]+1))
						

				def copyFromWCS(vars, wcs, result):
					"""adds the "simple" WCS keys from the wcstools instance wcs to
					the record result.
					"""
					result["mime"] = "image/fits"
					result["centerAlpha"], result["centerDelta"
						] = coords.getCenterFromWCSFields(wcs)
					result["nAxes"] = int(vars["NAXIS"])
					axeInds = range(1, result["nAxes"]+1)
					dims = tuple(int(vars["NAXIS%d"%i]) 
						for i in axeInds)
					pixelGauge = PixelGauge(wcs, (dims[0]/2., dims[1]/2.))
					result["pixelSize"] = dims
					result["pixelScale"] = pixelGauge.pixelScale
	
					result["wcs_projection"] = vars.get("CTYPE1")
					if result["wcs_projection"]:
						result["wcs_projection"] = result["wcs_projection"][5:8]
					result["wcs_refPixel"] = tuple(wcs.wcs.crpix)
					result["wcs_refValues"] = tuple(wcs.wcs.crval)
					result["wcs_cdmatrix"] = tuple(
						(wcs.wcs.get_pc()*wcs.wcs.get_cdelt()).ravel())
					result["wcs_equinox"] = vars.get("EQUINOX", None)

				def nullOutWCS(result, additionalKeys):
					"""clears all wcs fields, plus the ones in additonalKeys.
					"""
					for key in wcskeys+additionalKeys:
						result[key] = None
				
				def addWCS(vars, result, additionalKeys, addCoverage):
					wcs = coords.getWCS(vars, naxis=naxis)
					if wcs is None:
						if missingIsError:
							raise base.DataError("No WCS information")
						else:
							nullOutWCS(result, additionalKeys)
					else:
						copyFromWCS(vars, wcs, result)
						addCoverage(vars, wcs, result)
			</code>
		</setup>

	</procDef>

	<procDef type="apply" id="computeBbox" original="computeInputBase">
		<code>
			additionalKeys = ["primaryBbox", "secondaryBbox"]

			def addCoverage(vars, wcs, result):
				result["primaryBbox"], result["secondaryBbox"
					] = siap.splitCrossingBox(coords.getBboxFromWCSFields(wcs))

			addWCS(vars, result, additionalKeys, addCoverage)
		</code>
	</procDef>

	<procDef type="apply" id="computePGS" original="computeInputBase">
		<code>
			additionalKeys = ["coverage"]

			def addCoverage(vars, wcs, result):
				result["coverage"] = coords.getSpolyFromWCSFields(wcs)

			addWCS(vars, result, additionalKeys, addCoverage)
		</code>
	</procDef>

	<procDef type="apply" id="setMeta">
		<doc>
			sets siap meta *and* product table fields.
	
			These fields are common to all SIAP implementations.

			Unless you are sure you will never publish the table to
			obscore, make sure bandpassUnit is m.  Also, typically you
			will fill in bandpassId and then let the //siap#getBandFromFilter
			apply do the job.

			Do *not* use ``idmaps="*"`` when using this procDef; it writes
			directly into result, and you would be clobbering what it does.
		</doc>
		<setup>
			<par key="title" late="True" description="image title.  This
				should, in as few characters as possible, convey some idea what
				the image will show (e.g., instrument, object, bandpass">None</par>
			<par key="instrument" late="True" description="a short identifier
				for the instrument used">None</par>
			<par key="dateObs" late="True" description="the midpoint of the 
				observation; this can either be a datetime instance, or
				a float>1e6 (a julian date) or something else (which is then
				interpreted as an MJD)">None</par>
			<par key="bandpassId" late="True" description="a rough indicator
				of the bandpass, like Johnson bands">None</par>
			<par key="bandpassUnit" late="True" description="the unit of
				the bandpassRefval and friends">None</par>
			<par key="bandpassRefval" late="True" description="characteristic
				frequency or wavelength of the exposure">None</par>
			<par key="bandpassHi" late="True" description="lower value of
				wavelength or frequency">None</par>
			<par key="bandpassLo" late="True" description="upper value of
				the wavelength or frequency">None</par>
			<par key="refFrame" late="True" description="reference frame
				of the coordinates (change at your peril)">'ICRS'</par>
			<par key="pixflags" late="True" description="processing flags 
				(C atlas image or cutout, F resampled, X computed without 
				interpolation, Z pixel flux
				calibrated, V unspecified visualisation for presentation only)"
				>None</par>
		</setup>
		<code>
			result["dateObs"] = toMJD(dateObs)
			result["imageTitle"] = title
			result["instId"] = instrument
			result["bandpassId"] = bandpassId
			result["bandpassUnit"] = bandpassUnit
			result["bandpassRefval"] = bandpassRefval
			result["bandpassHi"] = bandpassHi
			result["bandpassLo"] = bandpassLo
			result["refFrame"] = refFrame
			result["pixflags"] = pixflags
		</code>
	</procDef>

	<procDef type="apply" id="getBandFromFilter">
		<doc>
			sets the bandpassId, bandpassUnit, bandpassRefval, bandpassHi,
			and bandpassLo from a set of standard band Ids.

			The bandpass ids known are contained in a file supplied file
			that you should consult for supported values.  Run
			gavo admin dumpDF data/filters.txt for details.

			All values filled in here are in meters.

			If this is used, it must run after //siap#setMeta since 
			setMeta clobbers our result fields.
		</doc>
		<setup>
			<par key="sourceCol" description="Name of the column containing
				the filter name; leave at default None to take the band from
				result['bandpassId'], where such information would be left
				by siap#setMeta.">None</par>
			<code>
				_filterMap = {}
				_aliases = {}

				NM = 1e-9

				def parseFilterMap():
					with base.openDistFile("data/filters.txt") as f:
						for line in f:
							if not line:
								break
							line = line.strip()
							if line.startswith("#"):
								continue
							parts = line.split("\t")
							primary = parts[0].strip()
							if primary.startswith("="):
								primary = primary[1:].strip()
								for p in parts[1:]:
									_aliases[p.strip()] = primary
							else:
								_filterMap[primary] = (
									float(parts[1])*NM, float(parts[2])*NM, float(parts[3])*NM)
							
				def setBandpass(result, filterId):
					if not _filterMap:
						parseFilterMap()
					try:
						short, mid, long = _filterMap[_aliases.get(filterId, filterId)]
					except KeyError:  # nothing known, do nothing
						return
					result["bandpassId"] = filterId
					result["bandpassUnit"] = "m"
					result["bandpassRefval"] = mid
					result["bandpassLo"] = short
					result["bandpassHi"] = long
			</code>
		</setup>
		<code>
			if sourceCol is None:
				val = result['bandpassId']
			else:
				val = vars[sourceCol]
			setBandpass(result, val)
		</code>
	</procDef>

	<condDesc id="siapCondBase">
		<!-- This just contains some components the real SIAP conditions build
		upon.  Do not inherit from this, do not instanciate it. -->
		<phraseMaker>
			<setup id="baseSetup">
				<code>
					from gavo import rscdef
					from gavo.protocols import siap

					def interpretFormat(inPars, sqlPars):
						# Interprets a SIA FORMAT parameter.  METADATA is caught by the
						# SIAP renderer, which of the magic values leaves ALL and 
						# GRAPHIC to us.
						fmt = inPars.get("FORMAT")
						if fmt is None or fmt=="ALL":
							return ""
						elif fmt=="GRAPHIC":
							return "mime IN %%(%s)s"%base.getSQLKey("format", 
								base.getConfig("web", "graphicMimes"), sqlPars)
						else:
							return "mime=%%(%s)s"%base.getSQLKey(
								"format", fmt, sqlPars)

					def getQueriedTable(inputKeys):
						"""tries to infer the table queried from the inputKeys passed to
						the condDesc.

						This will return None if it cannot find this parent table.
						"""
						try:
							res = inputKeys[0].parent.parent.queriedTable
						except (AttributeError, IndexError):
							traceback.print_exc()
							return None
						if not isinstance(res, rscdef.TableDef):
							return None
						return res
				</code>
			</setup>
		</phraseMaker>

		<inputKey id="base_POS" name="POS" type="text" unit="deg"
			multiplicity="single"
			ucd="pos.eq"
			description="ICRS Position, RA,DEC decimal degrees (e.g., 234.234,-32.46)"
			tablehead="Position" required="True">
		</inputKey>

		<inputKey name="SIZE" type="text" unit="deg" id="base_SIZE"
			multiplicity="single"
			description="Size in decimal degrees (e.g., 0.2 or 1,0.1)"
			tablehead="Field size" required="True">
		</inputKey>

		<inputKey name="INTERSECT" id="base_INTERSECT" type="text" description=
			"Relation of image and specified Region of Interest."
			multiplicity="single"
			tablehead="Intersection type" required="False">
			<values default="OVERLAPS" id="base_INTERSECT_values">
				<option title="Image overlaps RoI">OVERLAPS</option>
				<option title="Image covers RoI">COVERS</option>
				<option title="RoI covers image">ENCLOSED</option>
				<option title="The given position is shown on image">CENTER</option>
			</values>
		</inputKey>

		<inputKey name="FORMAT" id="base_FORMAT" type="text" required="False"
			description="Requested format of the image data"
			multiplicity="single"
			tablehead="Output format">
			<values default="image/fits"/>
		</inputKey>
	</condDesc>

	<condDesc id="protoInput" required="True">
		<inputKey original="base_POS" required="True" std="True">
			<property name="onlyForRenderer">siap.xml</property>
		</inputKey>
		<inputKey original="base_SIZE" required="True" std="True">
			<property name="onlyForRenderer">siap.xml</property>
		</inputKey>
		<inputKey original="base_INTERSECT" std="True"
			>OVERLAPS<property name="onlyForRenderer">siap.xml</property>
		</inputKey>
		<inputKey original="base_FORMAT" std="True"
			>GRAPHIC<property name="onlyForRenderer">siap.xml</property>
		</inputKey>
		<phraseMaker>
			<setup original="baseSetup"/>
			<code>
				yield siap.getQuery(getQueriedTable(inputKeys), inPars, outPars)
				yield interpretFormat(inPars, outPars)
			</code>
		</phraseMaker>
	</condDesc>

	<condDesc id="humanInput">
		<inputKey original="base_POS" name="hPOS"
			description="ICRS Position, RA,DEC, or Simbad object (e.g., 234.234,-32.45)">
			<property name="notForRenderer">siap.xml</property>
		</inputKey>
		<inputKey original="base_SIZE" name="hSIZE">
			<property name="notForRenderer">siap.xml</property>
			<values default="0.5"/>
		</inputKey>
		<inputKey original="base_INTERSECT" name="hINTERSECT">
			<property name="notForRenderer">siap.xml</property>
			<values original="base_INTERSECT_values" default="OVERLAPS"/>
		</inputKey>
		<inputKey original="base_FORMAT" name="hFORMAT" widgetFactory='Hidden'>
			<property name="notForRenderer">siap.xml</property>
		</inputKey>

		<phraseMaker>
			<setup original="baseSetup"/>
			<code>
				pos = inPars["hPOS"]
				try:
					ra, dec = base.parseCooPair(pos)
				except ValueError:
					data = base.caches.getSesame("web").query(pos)
					if not data:
						raise base.ValidationError("%r is neither a RA,DEC pair nor"
								" a simbad resolvable object"%inPars.get("hPOS", "Not given"), 
							"hPOS")
					ra, dec = float(data["RA"]), float(data["dec"])
				inPars = {
					"POS": "%f, %f"%(ra, dec), "SIZE": inPars["hSIZE"],
					"INTERSECT": inPars["hINTERSECT"], "FORMAT": inPars.get("hFORMAT")}
				yield siap.getQuery(getQueriedTable(inputKeys), inPars, outPars)
				yield interpretFormat(inPars, outPars)
			</code>
		</phraseMaker>
	</condDesc>

</resource>
