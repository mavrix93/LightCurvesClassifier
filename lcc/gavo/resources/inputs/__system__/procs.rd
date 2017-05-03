<resource schema="dc" resdir="__system">
<meta name="description">DaCHS predefined procedures.  Whatever is in here 
will also end up in the reference documentation, so that's where you
should look if you just want to use this.</meta>

<procDef type="apply" id="printRow">
	<doc>
		Print the current row to standard output.

		This is the equivalent of the printf-debugger.  It is much like the
		-d command line switch to gavo imp, but you can see the effects
		of row filters, var settings, potentially earlier proc applications, etc.
	</doc>
	<code>
		print vars
	</code>
</procDef>


<procDef type="apply" id="debug">
	<doc>
		Give a python debugger prompt.

		This drops you in the python debugger.  See vars for what's coming
		from the grammar, result for what's been mapped at this point.

		Type cont to continue.
	</doc>
	<code>
		import pdb; pdb.set_trace()
	</code>
</procDef>



<procDef type="apply" id="simpleSelect">
	<doc>
		Fill variables from a simple  database query.

		The idea is to obtain a set of values from the data base into some
		columns within vars (i.e., available for mapping) based on comparing
		a single input value against a database column.  The query should
		always return exactly one row.  If more rows are returned, the
		first one will be used (which makes the whole thing a bit of a gamble),
		if none are returned, a ValidationError is raised.
	</doc>
	<setup>
		<par key="assignments"><description><![CDATA[mapping from database 
			column names to vars column names, in the format 
			{<db colname>:<vars name>}"]]></description></par>
		<par key="table" description="name of the database table to query"/>
		<par key="column" description="the column to compare the input value
			against"/>
		<par key="errCol">'&lt;unknown&gt;'</par>
		<par key="val" late="True"/>
		<code>
			assignments = utils.parseAssignments(assignments)
			dbNames, recNames = assignments.keys(), assignments.values()
			query = "SELECT %s FROM %s WHERE %s=%%(val)s"%(
				", ".join(dbNames), table, column)

			def parseDestWithDefault(dest, defRe=re.compile(r"(\w+)\((.*)\)")):
				"""returns name, default from dests like bla(0).

				This can be used to provide defaulted targets to assignments parsed
				with _parseAssignments.
				"""
				mat = defRe.match(dest)
				if mat:
					return mat.groups()
				else:
					return dest, None
		</code>
	</setup>
	<code><![CDATA[
		try:
			with base.AdhocQuerier(base.getAdminConn) as querier:
				res = querier.query(query, {"val": val}).fetchall()[0]
				for name, resVal in zip(recNames, res):
					name, default = parseDestWithDefault(name)
					if resVal is None:
						vars[name] = default
					else:
						vars[name] = resVal
		except IndexError:
			raise base.ValidationError("The item %s didn't match"
				" any data.  Since this data is required for further"
				" operations, I'm giving up"%val, errCol)
		except base.DBError, msg:
			raise base.ValidationError("Internal error (%s)"%msg, "<unknown>")
	]]></code>
</procDef>

<procDef type="apply" id="resolveObject">
	<setup>
		<par key="ignoreUnknowns" description="Return Nones for unknown
			objects?  (if false, ValidationErrors will be raised)">True</par>
		<par key="logUnknowns" description="Write unresolved object names
			to the info log">False</par>
		<par key="identifier" late="True" 
			description="The identifier to be resolved."/>
		<code>
			from gavo.protocols import simbadinterface
			resolver = simbadinterface.Sesame(saveNew=True)
		</code>
	</setup>
	<doc>
		Resolve identifiers to simbad positions.

		It caches query results (positive as well as negative ones) in
		cacheDir.  To avoid flooding simbad with repetetive requests, it
		raises an error if this directory is not writable.

		It leaves J2000.0 positions as floats in the simbadAlpha and 
		simbadDelta variables.
	</doc>
	<code>
		ra, dec = None, None
		try:
			ra, dec = resolver.getPositionFor(identifier)
		except KeyError:
			if logUnknowns:
				base.ui.notifyInfo("Identifier did not resolve: %s"%identifier)
			if not ignoreUnknowns:
				raise base.Error("resolveObject could not resolve object"
					" %s."%identifier)
		vars["simbadAlpha"] = ra
		vars["simbadDelta"] = dec
	</code>
</procDef>

<procDef type="apply" id="mapValue">
	<doc><![CDATA[
	is an apply proc that translates values via a utils.NameMap
	
	Destination may of course be the source field (though that messes
	up idempotency of macro expansion, which shouldn't usually hurt).

	The format of the mapping file is::

		<target key><tab><source keys>

	where source keys is a whitespace-seperated list of values that should
	be mapped to target key (sorry the sequence's a bit unusual).

	A source key must be encoded quoted-printable.  This usually doesn't
	matter except when it contains whitespace (a blank becomes =20) or equal
	signs (which become =3D).

	Here's an example application for a filter that's supposed to translate
	some botched object names::

		<apply name="cleanObject" procDef="//procs#mapValue">
			<bind name="destination">"cleanedObject"</bind>
			<bind name="failuresMapThrough">True</bind>
			<bind name="value">@preObject</bind>
			<bind name="sourceName">"flashheros/res/namefixes.txt"</bind>
		</apply>

	The input could look like this, with a Tab char written as " <TAB> "
	for clarity::

		alp Cyg <TAB> aCyg alphaCyg
		Nova Cygni 1992 <TAB> Nova=20Cygni=20'92 Nova=20Cygni
]]></doc>
	<setup>
		<par key="destination" description="name of the field the mapped 
			value should be written into"/>
		<par key="logFailures" description="Log non-resolved names?">False</par>
		<par key="failuresAreNone" description="Rather than raise an error,
			yield NULL for values not in the mapping">False</par>
		<par key="failuresMapThrough" description="Rather than raise an error,
			yield the input value if it is not in the mapping (this is for
			'fix some'-like functions and only works when failureAreNone is False)"
			>False</par>
		<par key="sourceName" description="An inputsDir-relative path to 
			the NameMap source file."/>
		<par key="value" late="True" description="The value to be mapped."/>
		<code>
			map = utils.NameMap(os.path.join(
				base.getConfig("inputsDir"), sourceName))
		</code>
	</setup>
	<code>
		try:
			vars[destination] = map.resolve(str(value))
		except KeyError:
			if logFailures:
				base.ui.notifyWarning("Name %s could not be mapped\n"%value)
			if failuresAreNone:
				vars[destination] = None
			elif failuresMapThrough:
				vars[destination] = value
			else:
				raise base.LiteralParseError("Name %s could not be mapped"%value,
					destination, value)
	</code>
</procDef>

<procDef type="apply" id="fullQuery">
	<doc><![CDATA[
	runs a free query against the data base and enters the first result 
	record into vars.

	locals() will be passed as data, so you can define more bindings
	and refer to their keys in the query.
	]]></doc>
	<setup>
		<par key="query" description="an SQL query"/>
		<par key="errCol" description="a column name to use when raising a
			ValidationError on failure."
			>'&lt;unknown&gt;'</par>
	</setup>
	<code>
		with base.AdhocQuerier(base.getTableConn) as q:
			cursor = q.query(query, locals())
			keys = [f[0] for f in cursor.description]
			res = list(cursor)
			if not res:
				raise base.ValidationError("Could not find a matching row",
					errCol)
			vars.update(dict(zip(keys, res[0])))
	</code>
</procDef>

<procDef type="apply" id="dictMap">
	<doc>
		Maps input values through a dictionary.

		The dictionary is given in its python form here.  This apply
		only operates on the rawdict, i.e., the value in vars is changed,
		while nothing is changed in the rowdict.
	</doc>
	<setup>
		<par key="mapping" description="Python dictionary literal giving
			 the mapping"/>
		<par key="default" description="Default value for missing keys
			 (with this at the default, an error is raised)">KeyError</par>
		<par key="key" description="Name of the input key to map"/>
		<code>
			def doTheMap(vars):
				newVal = mapping.get(vars[key], default)
				if newVal is KeyError:
					raise base.ValidationError("dictMap saw %s, which it was"
						" not prepared to see."%repr(vars[key]),
						colName=key,
						hint="This dictMap knows the keys %s"%mapping.keys())
				vars[key] = newVal
		</code>
	</setup>
	<code>
		doTheMap(vars)
	</code>
</procDef>


<procDef id="expandIntegers" type="rowfilter">
	<doc>
	A row processor that produces copies of rows based on integer indices.

	The idea is that sometimes rows have specifications like "Star 10
	through Star 100".  These are a pain if untreated.  A RowExpander
	could create 90 individual rows from this.
	</doc>
	<setup>
		<par key="startName" description="column containing the start value"/>
		<par key="endName" description="column containing the end value"/>
		<par key="indName" description="name the counter should appear under"/>
	</setup>
	<code>
		try:
			lowerInd = int(row[startName])
			upperInd = int(row[endName])
		except (ValueError, TypeError): # either one not given
			yield row
			return
		for ind in range(lowerInd, upperInd+1):
			newRow = row.copy()
			newRow[indName] = ind
			yield newRow
	</code>
</procDef>


<procDef id="expandDates" type="rowfilter">
	<doc>
	is a row generator to expand time ranges.

	The finished dates are left in destination as datetime.datetime
	instances
	</doc>
	<setup>
		<par key="dest" description="name of the column the time should
			appear in">'curTime'</par>
		<par key="start" description="the start date(time), as either 
			a datetime object or a column ref"/>
		<par key="end" description="the end date(time)"/>
		<par key="hrInterval" late="True" description="difference
			 between generated timestamps in hours">24</par>
		<code>
		def _parseTime(val, fieldName):
			try:
				val = val
				if isinstance(val, datetime.datetime):
					return val
				elif isinstance(val, datetime.date):
					return datetime.datetime(val.year, val.month, val.day)
				else:
					return utils.parseISODT(val)
			except Exception, msg:
				raise base.ValidationError("Bad date from %s (%s)"%(fieldName,
					unicode(msg)), dest)
		</code>
	</setup>
	<code><![CDATA[
		stampTime = _parseTime(row[start], "start")
		endTime = _parseTime(row[end], "end")
		endTime = endTime+datetime.timedelta(hours=23)

		try:
			interval = float(hrInterval)
		except ValueError:
			raise base.ValidationError("Not a time interval: '%s'"%hrInterval,
				"hrInterval")
		if interval<0.01:
			interval = 0.01
		interval = datetime.timedelta(hours=interval)

		try:
			matchLimit = 100000 #getQueryMeta()["dbLimit"]
		except ValueError:
			matchLimit = 1000000
		while stampTime<=endTime:
			matchLimit -= 1
			if matchLimit<0:
				break
			newRow = row.copy()
			newRow[dest] = stampTime
			yield newRow
			stampTime = stampTime+interval
	]]></code>
</procDef>


<procDef id="expandComma" type="rowfilter">
	<doc>
	A row generator that reads comma seperated values from a
	field and returns one row with a new field for each of them.
	</doc>
	<setup>
		<par key="srcField" description="Name of the column containing
			the full string"/>
		<par key="destField" description="Name of the column the individual
			columns are written to"/>
	</setup>
	<code>
		src = row[srcField]
		if src is not None and src.strip():
			for item in src.split(","):
				item = item.strip()
				if not item:
					continue
				newRow = row.copy()
				newRow[destField] = item
				yield newRow
	</code>
</procDef>


<!--############################################################
Core phrase makers and friends -->

<procDef id="makeRangeQuery" type="phraseMaker">
	<doc>
	A phraseMaker that makes a pair of inputKeys into a range query,
	possibly half-open.

	The name of the column queried can be passed in the late parameter
	colName; the default is the name of the first inputKey minus the
	last four characters.  This looks weird but complements the
	rangeCondDesc stream below.
	</doc>
	<setup>
		<par key="colName" late="True" description="The name of the column queried
			against">inputKeys[0].name[:-4]</par>
	</setup>
	<code><![CDATA[
			minKey, maxKey = inputKeys
			minVal, maxVal = inPars.get(minKey.name), inPars.get(maxKey.name)
			if minVal is None:
				yield "%s<=%%(%s)s"%(colName,
					base.getSQLKey(maxKey.name, maxVal, outPars))
			elif maxVal is None:
				yield "%s>=%%(%s)s"%(colName,
					base.getSQLKey(minKey.name, minVal, outPars))
			else:
				yield "%s BETWEEN %%(%s)s AND %%(%s)s"%(colName,
					base.getSQLKey(minKey.name, minVal, outPars),
					base.getSQLKey(maxKey.name, maxVal, outPars))
	]]></code>
</procDef>

<STREAM id="rangeCond">
	<doc>
		A condDesc that expresses a range and has an InputKey each for min
		and max.

		Specify the following macros when replaying:

		* name -- the column name in the core's queried table
		* groupdesc -- a terse phrase describing the range.  This will be
		  used in the description of both the input keys and the group
		* grouplabel -- a label (include the unit, it is not taken from InputKey)
		  written in front of the form group

		groupdesc has to work after "Range of", "Lower bound of", and
		"Upper bound of".  Do not include a concluding period.
	</doc>

	<condDesc combining="True">
		<inputKey name="\name\+_min" original="\name"
				tablehead="Min \grouplabel"
				description="Lower bound of \groupdesc">
			<property name="cssClass">formkey_min</property>
		</inputKey>
		<inputKey name="\name\+_max" original="\name"
				tablehead="Max \grouplabel"
				description="Upper bound of \groupdesc">
			<property name="cssClass">formkey_max</property>
		</inputKey>
		<group name="mf\name">
			<description>Range of \groupdesc.  If you only specify one bound,
				you get a half-infinite interval.</description>
			<property name="label">\grouplabel</property>
			<property name="style">compact</property>
		</group>
		<phraseMaker procDef="//procs#makeRangeQuery"/>
	</condDesc>
</STREAM>

</resource>
