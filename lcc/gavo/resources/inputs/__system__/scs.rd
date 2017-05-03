<?xml version="1.0" encoding="utf-8"?>
<!-- definition of the position-related interfaces (and later SCS fragments) -->

<resource resdir="__system" schema="dc">
	<STREAM id="q3cIndexDef">
		<doc>
			Definition of a q3c index over the main position of a table.
		</doc>
		<index name="q3c_\\tablename" cluster="True">
			<columns>\\nameForUCDs{pos.eq.ra;meta.main|POS_EQ_RA_MAIN}, \\nameForUCDs{pos.eq.dec;meta.main|POS_EQ_DEC_MAIN}</columns>
			q3c_ang2ipix(\\nameForUCDs{pos.eq.ra;meta.main|POS_EQ_RA_MAIN}, \\nameForUCDs{pos.eq.dec;meta.main|POS_EQ_DEC_MAIN})
		</index>
	</STREAM>

	<STREAM id="positionsFields">
		<doc>
			Old-style positions.  Use naked q3c instead.
		</doc>
		<!-- fill these using the handleEquatorialPosition macro defined below;
		no rowmakers required. -->
		<column name="alphaFloat" unit="deg" type="double precision" 
			ucd="pos.eq.ra;meta.main" verbLevel="1"
			tablehead="RA" description="Main value of right ascension"/>
		<column name="deltaFloat" unit="deg" type="double precision" 
			ucd="pos.eq.dec;meta.main" verbLevel="1"
			tablehead="Dec" description="Main value of declination"/>
		<column name="c_x" type="real" verbLevel="30"
			tablehead="c_x" unit="" ucd="pos.cartesian.x" description=
				"x coordinate of intersection of radius vector and unit sphere"/>
		<column name="c_y" type="real" verbLevel="30"
			tablehead="c_y" unit="" ucd="pos.cartesian.y" description=
				"y coordinate of intersection of radius vector and unit sphere"/>
		<column name="c_z" type="real" verbLevel="30" tablehead="c_z" 
			unit="" ucd="pos.cartesian.z" description=
			"z coordinate of intersection of radius vector and unit sphere"/>
	</STREAM>

	<mixinDef id="positions">
		<doc><![CDATA[
			A mixin adding standardized columns for equatorial positions to the
			table.

			It consists of the fields alphaFloat, deltaFloat (float angles
			in degrees, J2000.0) and c_x, c_y, c_z (intersection of the radius
			vector to alphaFloat, deltaFloat with the unit sphere).

			You will usually use it in conjunction with the //scs#eqFloat procDef that
			preparse these fields for you.

			Thus, you could say::

				<proc procDef="//scs#eqFloat">
					<arg name="alpha">alphaSrc</arg>
					<arg name="delta">deltaSrc</arg>
				</proc>
			
			Note, however, that it's usually much better to not mess with the
			table structure and handle positions using the q3cindex mixin.
		]]></doc>
		<events>
			<FEED source="//scs#positionsFields"/>
		</events>
	</mixinDef>

	<mixinDef id="q3cpositions">
		<doc>
			An extension of `the positions mixin`_ adding a positional index.
		
			This works exactly like the positions interface, except that behind
			the scenes some magic code generates a q3c index on the fields
			alphaFloat and deltaFloat.

			This will fail without the q3c extension to postgres.  Again,
			in general use the plain q3cindex.
		</doc>
		<events>
			<FEED source="//scs#positionsFields"/>
		</events>
		<lateEvents>
			<FEED source="//scs#q3cIndexDef"/>
		</lateEvents>
	</mixinDef>

	<mixinDef id="q3cindex">
		<doc>
			A mixin adding an index to the main equatorial positions.

			This is what you usually want if your input data already has
			"sane" (i.e., ICRS or at least J2000) positions or you convert
			the positions manually.

			You have to designate exactly one column with the ucds pos.eq.ra;meta.main
			pos.eq.dec;meta.main, respectively.  These columns receive the
			positional index.

			This will fail without the q3c extension to postgres.
		</doc>
		<lateEvents>
			<FEED source="//scs#q3cIndexDef"/>
		</lateEvents>
	</mixinDef>


	<procDef id="eqFloat">
		<doc>
			A proc feeding alphaFloat and deltaFloat as well as c_[x|y|z] from
			equatorial coordinates.

			This is now considered a misguided experiment.  Do not use it in new
			RDs.

			Specifically, it generates alphaFloat, deltaFloat as well as
			c_x, c_y, c_z (cartesian coordinates of the intersection of the 
			direction vector with the unit sphere).

			TODO: Equinox handling (this will probably be handled through an
			optional arguments srcEquinox and destEquinox, both J2000.0 by default).
			
			Setup pars:

			* raFormat -- the literal format of Right Ascension.  By default,
				a sexagesimal time angle is expected.  Supported formats include
				mas (RA in milliarcsecs), ...
			* decFormat -- as raFormat, only the default is sexagesimal angle.
			* sepChar (optional) -- seperator for alpha, defaults to whitespace
			* alphaKey, deltaKey -- keys to take alpha and delta from.
			
			If alpha and delta use different seperators, you'll have to fix
			this using preprocessing macros.
		</doc>
		<setup>
			<par key="alphaFormat"><description>the literal format of Right 
				Ascension.  Supported formats include
				mas (RA in milliarcsecs), hour (hours minutes seconds), sexag
				(degrees minutes seconds), and binary (copy through).
				</description>'hour'</par>
			<par key="deltaFormat" description="see alphaFormat">'sexag'</par>
			<par key="alphaKey" description="name of the column containing the RA"
				>'alpha'</par>
			<par key="deltaKey" description="name of the column containing the
				Declination">'delta'</par>
			<par key="sepChar" description="separator for RA and Dec (default
				means any whitespace)">None</par>
			<code>
				coordComputer = {
					"hour": lambda hms: utils.hmsToDeg(hms, sepChar),
					"sexag": lambda dms: utils.dmsToDeg(dms, sepChar),
					"mas": lambda mas: float(mas)/3.6e6,
					"binary": lambda a: a,
				}
				def convertCoo(literalForm, literal):
					return coordComputer[literalForm](literal)
				def computeCoos(alpha, delta):
					alphaFloat = convertCoo(alphaFormat, alpha)
					deltaFloat = convertCoo(deltaFormat, delta)
					return (alphaFloat, deltaFloat)+tuple(
						coords.computeUnitSphereCoords(alphaFloat, deltaFloat))
			</code>
		</setup>
		<code>
			alpha, delta = vars[alphaKey], vars[deltaKey]
			if alpha is None or delta is None:
				alphaFloat, deltaFloat, c_x, c_y, c_z = [None]*5
			else:
				alphaFloat, deltaFloat, c_x, c_y, c_z = computeCoos(
					alpha, delta)
			result["alphaFloat"] = alphaFloat
			result["deltaFloat"] = deltaFloat
			result["c_x"] = c_x
			result["c_y"] = c_y
			result["c_z"] = c_z
		</code>
	</procDef>

	<macDef name="csQueryCode">	</macDef>

	<condDesc>
		<!-- common setup for the SCS-related condDescs -->
		<phraseMaker id="scsUtils">
			<setup id="scsSetup">
				<code>
					from gavo.protocols import simbadinterface

					def getRADec(inPars, sqlPars):
						"""tries to guess coordinates from inPars.

						(for human SCS condition).
						"""
						pos = inPars["hscs_pos"]
						try:
							return base.parseCooPair(pos)
						except ValueError:
							data = base.caches.getSesame("web").query(pos)
							if not data:
								raise base.ValidationError("%s is neither a RA,DEC"
								" pair nor a simbad resolvable object"%
								inPars["hscs_pos"], "hscs_pos")
							return float(data["RA"]), float(data["dec"])

					def genQuery(inPars, outPars):
						"""returns the query fragment for this cone search.
						"""
						return ("q3c_radial_query(%s, %s, %%(%s)s, "
							"%%(%s)s, %%(%s)s)")%(
							"\nameForUCDs{pos.eq.ra;meta.main|POS_EQ_RA_MAIN}",
							"\nameForUCDs{pos.eq.dec;meta.main|POS_EQ_DEC_MAIN}",
							base.getSQLKey("RA", inPars["RA"], outPars),
							base.getSQLKey("DEC", inPars["DEC"], outPars),
							base.getSQLKey("SR", inPars["SR"], outPars))
				</code>
			</setup>
		</phraseMaker>
	</condDesc>

	<condDesc id="protoInput" required="True">
		<inputKey name="RA" type="double precision" unit="deg" ucd="pos.eq.ra"
			description="Right Ascension (ICRS decimal)" tablehead="Alpha (ICRS)"
			multiplicity="single"
			std="True">
			<property name="onlyForRenderer">scs.xml</property>
		</inputKey>
		<inputKey name="DEC" type="double precision" unit="deg" ucd="pos.eq.dec"
			description="Declination (ICRS decimal)" tablehead="Delta (ICRS)"
			multiplicity="single"
			std="True">
			<property name="onlyForRenderer">scs.xml</property>
		</inputKey>
		<inputKey name="SR" type="real" unit="deg" description="Search radius"
			multiplicity="single"
			tablehead="Search Radius" std="True">
			<property name="onlyForRenderer">scs.xml</property>
		</inputKey>
		<phraseMaker id="scsPhrase" name="scsSQL">
			<setup original="scsSetup"/>
			<code>
				yield genQuery(inPars, outPars)
			</code>
		</phraseMaker>
	</condDesc>

	<condDesc id="humanInput" combining="True">
		<inputKey id="hscs_pos" 
			name="hscs_pos" type="text"
			multiplicity="single"
			description= "Coordinates (as h m s, d m s or decimal degrees), or SIMBAD-resolvable object" tablehead="Position/Name">
			<property name="notForRenderer">scs.xml</property>
		</inputKey>
		<inputKey id="hscs_sr" 
			name="hscs_sr" description="Search radius in arcminutes"
			multiplicity="single"
			tablehead="Search radius">
			<property name="notForRenderer">scs.xml</property>
		</inputKey>
		<phraseMaker original="scsUtils" id="humanSCSPhrase" name="humanSCSSQL">
			<code>
				if inPars["hscs_pos"] is None:
					return
				if inPars["hscs_sr"] is None:
					raise base.ValidationError("If you query for a position,"
						" you must give a search radius", "hscs_sr")

				ra, dec = getRADec(inPars, outPars)
				try:
					sr = float(inPars["hscs_sr"])/60.
				except ValueError: # in case we're not running behind forms
					raise gavo.ValidationError("Not a valid float", "hscs_sr")
				inPars = {"RA": ra, "DEC": dec, "SR": sr}
				yield genQuery(inPars, outPars)
			</code>
		</phraseMaker>
	</condDesc>

	<STREAM id="makeSpointCD">
		<doc><![CDATA[
			This builds a cone search condDesc for Web forms for an spoint column.

			To define it, say something like::

				<FEED source="//scs#makeSpointCD"
					tablehead="Position observed"
					matchColumn="ssa_location"/>

			This is also used in ``<condDesc buildFrom="(some spoint col)"/>``
		]]></doc>

		<!-- this should beforbidden in untrusted RDs since it's easy to
		do python code or SQL injection using this.  To mitigate it,
		we'd need some input validation for (specific) macro arguments
		or a notion of "unsafe" streams.  Well, right before untrusted
		DaCHS RDs actually start to get swapped, I'll do either of these. -->

		<condDesc>
			<inputKey name="pos_\matchColumn" type="text"
				multiplicity="single"
				description= "Coordinates (as h m s, d m s or decimal degrees), 
					or SIMBAD-resolvable object" tablehead="\tablehead">
			</inputKey>
			<inputKey name="sr_\matchColumn" 
				multiplicity="single"
				description="Search radius in arcminutes"
				unit="arcmin"
				tablehead="Search radius for \tablehead">
			</inputKey>
			<phraseMaker>
				<setup>
					<code>
						from gavo.protocols import simbadinterface
						
						def getRADec(inPars, sqlPars):
							"""tries to guess coordinates from inPars.

							(for human SCS condition).
							"""
							pos = inPars["pos_\matchColumn"]
							try:
								return base.parseCooPair(pos)
							except ValueError:
								data = base.caches.getSesame("web").query(pos)
								if not data:
									raise base.ValidationError("%s is neither a RA,DEC"
									" pair nor a simbad resolvable object"%
									inPars["pos_\matchColumn"], "pos_\matchColumn")
								return float(data["RA"]), float(data["dec"])
					</code>
				</setup>
				<code><![CDATA[
					ra, dec = getRADec(inPars, outPars)
					try:
						sr = float(inPars["sr_\matchColumn"])/60.
					except ValueError: # in case we're not running behind forms
						raise gavo.ValidationError("Not a valid float", "sr_\matchColumn")
					yield "%s <-> %%(%s)s < %%(%s)s"%("\matchColumn",
						base.getSQLKey("pos", 
							pgsphere.SPoint.fromDegrees(ra, dec), outPars), 
						base.getSQLKey("sr", sr/180*math.pi, outPars))
				]]></code>
			</phraseMaker>
		</condDesc>
	</STREAM>

	<STREAM id="coreDescs">
		<doc><![CDATA[
			This stream inserts three condDescs for SCS services on tables with
			pos.eq.(ra|dec).main columns; one producing the standard SCS RA, 
			DEC, and SR parameters, another creating input fields for human
			consumption, and finally MAXREC.
		]]></doc>
		<condDesc original="//scs#humanInput"/>
		<condDesc original="//scs#protoInput"/>
		<condDesc silent="True">
			<inputKey name="MAXREC" type="integer" tablehead="Limit"
				description="Do not return more than MAXREC records"
				multiplicity="single"
					>\\getConfig{ivoa}{dalDefaultLimit}
					<property name="onlyForRenderer">scs.xml</property></inputKey>
		</condDesc>
	</STREAM>

</resource>
