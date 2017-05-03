<?xml version="1.0" encoding="utf-8"?>

<resource resdir="__system" schema="dc">

<!-- This has to match whatever is done in gavo.web.creds.
-->
	<table id="users" primary="username" onDisk="True" system="True">
<!-- prevent "normal" (e.g., ADQL) users from accessing this table -->
		<readProfiles/>
		<column name="username" type="text" tablehead="Username"/>
		<column name="password" type="text" displayHint="type=suppress"/>
		<!-- This is a plain text password.  We could store md5s, but
			then I guess it's more likely that people will ask for pws
			than that any unauthorized entity will be interested in them.
			If that assessment changes, by all means store md5s, since
			this table is largely unprotected -->
		<column name="remarks" type="text"/>
	</table>

	<table id="groups" onDisk="True" system="True">
		<readProfiles/>
		<foreignKey inTable="users" source="username"/>
		<column name="username" type="text"/>
		<column name="groupname" type="text"/>
	</table>

	<data id="maketables">
		<nullGrammar/>
		<make table="users"/>
		<make table="groups"/>
		
	</data>
</resource>
