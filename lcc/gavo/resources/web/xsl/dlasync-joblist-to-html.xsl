<?xml version="1.0" encoding="UTF-8"?>

<xsl:stylesheet
    xmlns:uws="http://www.ivoa.net/xml/UWS/v1.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
		xmlns="http://www.w3.org/1999/xhtml"
    version="1.0">
    
    <!-- A stylesheet to convert a datalink UWS joblist to HTML.  -->

		<xsl:output method="xml" 
			doctype-public="-//W3C//DTD XHTML 1.0 Strict//EN"
			doctype-system="http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd"/>

		<xsl:template match="uws:jobref">
			<li>
				<a>
					<xsl:attribute name="href">dlasync/<xsl:value-of select="@id"/>
					</xsl:attribute>
					<xsl:value-of select="@id"/>
				</a>
				(<xsl:apply-templates/>)</li>
		</xsl:template>
	
		<xsl:template match="/">
			<html>
				<head>
					<title>Async data access job list</title></head>
					<meta name="robots" content="nofollow"/>
				<body>
					<h1>Async datalink jobs</h1>
					<ul>
						<xsl:apply-templates/>
					</ul>
					<h1>Create a data access job</h1>
					<form action="dlasync" method="POST">
						<h2>Create a new async job</h2>
						<p><label for="pubdid">PubDID:</label>
						<input type="text" name="ID" id="pubdid"/></p>
						<p><input type="submit" value="New job..."/></p>
					</form>
				</body>
			</html>
		</xsl:template>
</xsl:stylesheet>
