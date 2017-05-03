<?xml version="1.0" encoding="utf-8"?>
<!-- meta tables containing field descriptions of all fields of data center
tables and the RDs the tables come from. -->

<!-- note that much of the stuff in here is reflected in code in
* rsc.dbtable
* rsc.metatable
* rscdef.column
-->

<resource resdir="__system" schema="dc">
	<meta name="description">Table-related metadata for
		the tables within this data center.</meta>


	<table id="tablemeta" onDisk="True" system="True" forceUnique="True"
			dupePolicy="overwrite">
		<meta name="description">A table mapping table names and schemas to
			the resource descriptors they come from and whether they are open
			to ADQL queries.  This table is primarily used for the table info
			services defined below.</meta>

		<primary>tableName, sourceRD</primary>

		<column name="tableName" description="Fully qualified table name"
			type="text" verbLevel="1"/>
		<column name="sourceRD" type="text"
			description="Id of the resource descriptor containing the 
				table's definition"
			tablehead="RD" verbLevel="15"/>
		<column name="tableDesc" type="text"
			description="Description of the table content" 
			tablehead="Table desc." verbLevel="1"/>
		<column name="resDesc" type="text"
			description="Description of the resource this table is part of"
			tablehead="Res desc." verbLevel="15"/>
		<column name="adql" type="boolean" required="True"
			description="True if this table may be accessed using ADQL"
			verbLevel="30"/>
	</table>

	<table id="metastore" onDisk="True" system="True" primary="key"
			forceUnique="True" dupePolicy="overwrite">
		<meta name="description">A table for storing all kinds of key-value
			pairs.  Key starting with an underscore are for use by user RDs.

			Only one pair per key is supported, newer keys overwrite older ones.
		</meta>

		<column name="key" type="text" description="A key; everything that
			starts with an underscore is user defined."/>
		<column name="value" type="text" description="A value; no serialization
			 format is defined here, but you are encouraged to use python literals
			 for non-strings."/>
	</table>

	<rowmaker id="fromColumnList">
		<!-- turns a rawrec with column, colInd, tableName keys into a
		columnmeta row -->
		<apply name="makerow">
			<code>
				column = vars["column"]
				for key in ["description", "unit", "ucd", "tablehead",
						"utype", "verbLevel", "type"]:
					result[key] = getattr(column, key)
				result["displayHint"] = column.getDisplayHintAsString()
				result["fieldName"] = column.name
				result["sourceRD"] = column.parent.rd.sourceId
			</code>
		</apply>
		<map dest="colInd"/>
		<map dest="tableName"/>
	</rowmaker>

	<data id="import">
		<make table="tablemeta"/>
		<make table="metastore">
			<script lang="python" type="postCreation">
				from gavo.user import upgrade
				from gavo import base
				base.setDBMeta(table.connection, 
					"schemaversion", upgrade.CURRENT_SCHEMAVERSION)
			</script>
		</make>
	</data>

	<fixedQueryCore id="queryList"
		query="SELECT tableName, tableName, tableDesc, resDesc FROM dc.tablemeta WHERE adql ORDER BY tableName">
		<outputTable namePath="tablemeta">
			<outputField original="tableName"/>
			<outputField name="tableinfo" original="tableName"/>
			<outputField original="tableDesc"/>
			<outputField original="resDesc"/>
		</outputTable>
	</fixedQueryCore>

	<service id="show" allowed="tableinfo" core="queryList">
		<meta name="shortName">Table infos</meta>
		<meta name="description">Information on tables within the 
			\getConfig{web}{sitename}</meta>
		<meta name="title">\getConfig{web}{sitename} Table Infos</meta>
	</service>

	<service id="list" core="queryList">
		<meta name="shortName">ADQL tables</meta>
		<meta name="description">An overview over the tables available for ADQL 
			querying within the \getConfig{web}{sitename}</meta>
		<meta name="title">\getConfig{web}{sitename} Public Tables</meta>
		<outputTable namePath="tablemeta">
			<outputField original="tableName"/>
			<outputField name="tableinfo" type="text" tablehead="Info">
				<formatter>
					return T.a(href=base.makeSitePath("/__system__/dc_tables/"
						"show/tableinfo/"+urllib.quote(data)))["Table Info"]
				</formatter>
			</outputField>
			<outputField original="tableDesc"/>
			<outputField original="resDesc"/>
		</outputTable>
	</service>
</resource>

