<resource schema="dc" resdir="__system">
	<meta name="description">Helper objects for the support of the VO's
	ad-hoc "parameter query language" as used in various DAL protocols.
	</meta>

	<procDef id="coneParameter" type="phraseMaker">
		<doc>
			A parameter containing a cone search with a single position-like
			key (the first, expecting a coordinate pair fairly leniently) and
			a cone search (a float, in the second input key).

			The generated expression uses pgsphere.
		</doc>

		<setup>
			<par name="posCol" description="Name of the database column
				to be compared against the input value(s).  It must be of
				type spoint."/>
		</setup>

		<code>
			try:
				posKey = inputKeys[0].name
				sizeKey = inputKeys[1].name
			except IndexError:
				raise base.ValidationError("Operator error: the cone condition"
					" is lacking input keys.", "query")
			parsedPos = pql.PQLPositionPar.fromLiteral(
				inPars.get(posKey, None), posKey)
			size = inputKeys[1]._parse(inPars.get(sizeKey, None))
			if parsedPos is not None and size is not None:
				yield parsedPos.getConeSQL(posCol, outPars, size)
		</code>
	</procDef>

	<procDef id="dateParameter">
		<doc>
			A parameter constraining an epoch or similar. 
		</doc>

		<setup>
			<par name="consCol" description="Name of the database column
				constrained by the input value."/>
			<par name="consColKind" description="The kind of date specification
				of consCol; this can be timestamp (also good for dates), jd, mjd,
				or jy (julian year).">"timestamp"</par>
		</setup>

		<code>
			inputKey = inputKeys[0]
			if consColKind=="timestamp":
				convertTo = None
			else:
				convertTo = consColKind

			key = inputKey.name
			parsed = pql.PQLDatePar.fromLiteral(inPars.get(key, None), key)
			if parsed is not None:
				yield parsed.getSQL(consCol, outPars, convertTo)
		</code>
	</procDef>

	<procDef id="floatParameter">
		<setup>
			<par name="consCol" description="Name of the database column
				constrained by the input value."/>
		</setup>

		<code>
			key = inputKeys[0].name
			parsed = pql.PQLFloatPar.fromLiteral(inPars.get(key, None), key)
			if parsed is not None:
				yield parsed.getSQL(consCol, outPars)
		</code>
	</procDef>

	<procDef id="stringParameter">
		<doc>
			A parameter that constrains a string-valued column.  Matches
			are literal and case-sensitive; the collation (for ranges)
			is that given by the database.  Steps are not allowed.
		</doc>

		<setup>
			<par name="consCol" description="Name of the database column
				constrained by the input value."/>
		</setup>

		<code>
			key = inputKeys[0].name
			parsed = pql.PQLPar.fromLiteral(inPars.get(key, None), key)
			if parsed is not None:
				yield parsed.getSQL(consCol, outPars)
		</code>
	</procDef>

	<procDef id="irStringParameter">
		<doc>
			A parameter that constrains a string-valued column, where both
			the column values and the search value are interpreted as 
			document vectors and compared according to the information retrieval
			functions of Postgres -- i.e., more or less like google matches
			queries.

			Since it is hard to figure out what they could mean, neither 
			steps nor ranges are supported.
		</doc>

		<setup>
			<par name="consCol" description="Name of the database column
				constrained by the input value."/>
		</setup>

		<code>
			key = inputKeys[0].name
			parsed = pql.PQLTextParIR.fromLiteral(inPars.get(key, None), key)
			if parsed is not None:
				yield parsed.getSQL(consCol, outPars)
		</code>
	</procDef>


<!-- For lack of a better place: Descriptors of the standard DALI parameters
vodal-based services interpret. -->

	<NXSTREAM id="DALIPars">
		<inputKey name="RESPONSEFORMAT" type="text"
			ucd="meta.code.mime"
			tablehead="Output Format"
			description="File format requested for output.">
			<values>
				<LOOP>
					<codeItems>
						from gavo import formats
						for key in formats.iterFormats():
							yield {"item": formats.getMIMEFor(key), 
								"title": formats.getLabelFor(key)}
					</codeItems>
					<events>
						<option title="\\title">\\item</option>
					</events>
				</LOOP>
			</values>
		</inputKey>

		<inputKey name="MAXREC" type="integer"
			tablehead="Match limit"
			description="Maximum number of records returned.  Pass 0 to
				 retrieve service parameters."/>
	</NXSTREAM>
	
</resource>
