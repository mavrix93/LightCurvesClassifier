<resource schema="__system">


<!-- ================================ Obscore ===================== -->

	<STREAM id="obscore-extraevents">
		<doc><![CDATA[
			Write extra events to mix into obscore-published tables.  This
			will almost always be just additions to the obscore clause of
			looking roughly like::
				
				<property name="obscoreClause" cumulate="True">
					,
					CAST(\\\\plutoLong AS real) AS pluto_long,
					CAST(\\\\plutoLat AS real) AS pluto_lat
				</property>

			See also `Extending Obscore`_ in the reference manual.
		]]></doc>
	</STREAM>

	<STREAM id="obscore-extrapars">
		<doc><![CDATA[
			For each macro you reference in obscore-extraevents, add a
			mixinPar here, like:

				<mixinPar key="plutoLong">NULL</mixinPar>
			
			Note that all mixinPars here must have default (i.e., there must
			be some content in the element suitable as an SQL expression
			of the appropriate type).  If you fail to give one, the creation
			of the empty prototype obscore table will fail with fairly obscure
			error messages.
		]]></doc>
	</STREAM>

	<STREAM id="obscore-extracolumns">
		<doc>
			Add column definitions for obscore here.  See `Extending Obscore`_ for
			details.
		</doc>
	</STREAM>

	<script id="_test-script" lang="python" name="test instrumentation"
		type="preIndex">
		# (this space left blank intentionally)
	</script>


<!-- ================================ Registry Interface ============ -->

	<STREAM id="registry-interfacerecords">
		<doc>
			These are services and registry records for the registry interface
			of this service.

			Even if together with defaultmeta, this will just work, keep 
			these elements in your etc/userconfig.rd.

			The metaString macros in here generally point into defaultmeta.
			Replace them with whatever actual text applies to your site;  we
			will work to do away with defaultmeta.txt.
		</doc>

		<resRec id="authority"> <!-- ivo id of the authority is overridden in
			nonservice.NonServiceResource -->
			<meta>
				resType: authority
				creationDate: \\metaString{authority.creationDate}{UNCONFIGURED}
				title: \\metaString{authority.title}{UNCONFIGURED}
				shortName: \\metaString{authority.shortName}{UNCONFIGURED}
				subject: Authority
				managingOrg: \\metaString{authority.managingOrg}{UNCONFIGURED}
				referenceURL: \\metaString{authority.referenceURL}{UNCONFIGURED}
				identifier: ivo://\getConfig{ivoa}{authority}
				sets: ivo_managed
			</meta>
			<meta name="description">
				\\metaString{authority.description}{UNCONFIGURED}
			</meta>
		</resRec>

		<resRec id="manager"> <!-- the organisation running this registry -->
			<meta>
				resType: organization
				creationDate: \\metaString{authority.creationDate}{UNCONFIGURED}
				title: \\metaString{organization.title}{UNCONFIGURED}
				subject: Organization
				referenceURL: \\metaString{organization.referenceURL}{UNCONFIGURED}
				identifier: ivo://\getConfig{ivoa}{authority}/org
				sets: ivo_managed
			</meta>
			<meta name="description">
				\\metaString{organization.description}{UNCONFIGURED}
			</meta>
		</resRec>

		<registryCore id="registrycore"/>

		<service id="registry" core="registrycore" allowed="pubreg.xml">
			<publish render="pubreg.xml" sets="ivo_managed">
				<meta name="accessURL"
					>\getConfig{web}{serverURL}\getConfig{web}{nevowRoot}oai.xml</meta>
			</publish>
			<meta name="resType">registry</meta>
			<meta name="title">\getConfig{web}{sitename} Registry</meta>
			<meta name="creationDate">2008-05-07T11:33:00</meta>
			<meta name="description">
				The publishing registry for the \getConfig{web}{sitename}.
			</meta>
			<meta name="subject">Registry</meta>
			<meta name="shortName">\\metaString{authority.shortName} Reg</meta>
			<meta name="content.type">Archive</meta>
			<meta name="rights">public</meta>
			<meta name="harvest.description">The harvesting interface for 
				the publishing registry of the \getConfig{web}{sitename}</meta>
			<meta name="maxRecords">10000</meta>
			<meta name="managedAuthority">\getConfig{ivoa}{authority}</meta>
			<meta name="publisher">The staff at the \getConfig{web}{sitename}</meta>
		</service>
	</STREAM>

	<STREAM id="tapexamples">
		<doc>Examples for TAP querying</doc>
		
		<meta name="_example" title="tap_schema example">
			To locate columns "by physics", as it were, use UCD in
			:table:`tap_schema.columns`.  For instance,
			to find everything talking about the mid-infrared about 10µm, you
			could write:

			.. query::
				
				SELECT * FROM tap_schema.columns 
				  WHERE description LIKE '%em.IR.8-15um%'
		</meta>
	</STREAM>
</resource>
