<?xml version="1.0" encoding="UTF-8"?>

<xsl:stylesheet
    xmlns:uws="http://www.ivoa.net/xml/UWS/v1.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
		xmlns="http://www.w3.org/1999/xhtml"
    version="1.0">
    
    <!-- A stylesheet to convert a UWS joblist into HTML.  -->

		<xsl:output method="xml" 
			doctype-public="-//W3C//DTD XHTML 1.0 Strict//EN"
			doctype-system="http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd"/>

		<xsl:template match="uws:jobref">
			<li>
				<a>
					<xsl:attribute name="href">async/<xsl:value-of select="@id"/>
					</xsl:attribute>
					<xsl:value-of select="@id"/>
				</a>
				(<xsl:apply-templates/>)</li>
		</xsl:template>
	
		<xsl:template match="/">
			<html>
				<head>
					<title>UWS job list</title></head>
					<meta name="robots" content="nofollow"/>
				<body>
					<h1>UWS jobs</h1>
					<ul>
						<xsl:apply-templates/>
					</ul>
					<form action="async" method="POST">
						<h2>Create a new async job</h2>
						<input type="submit" value="New job..."/>
						<input type="hidden" name="LANG" value="ADQL"/>
						<input type="hidden" name="REQUEST" value="doQuery"/>
					</form>

					<form action="sync" method="GET">
						<h2>Run a sync job</h2>
						<input type="hidden" name="LANG" value="ADQL"/>
						<input type="hidden" name="REQUEST" value="doQuery"/>
						<textarea name="QUERY" style="width:100%"/>
						<p>
						<label for="formatbutton">Output Format: </label>
						<select name="FORMAT" id="formatbutton">
							<option value="application/x-votable+xml">VOTable</option>
							<option value="text/html">HTML</option>
							<option value="application/fits">FITS</option>
							<option value="text/csv">CSV</option>
							<option value="text/plain">Tab separated</option>
						</select>
						</p>
						<p><input type="submit" value="Run"/></p>
					</form>
				</body>
			</html>
		</xsl:template>
</xsl:stylesheet>
