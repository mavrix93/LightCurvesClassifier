<?xml version="1.0" encoding="UTF-8"?>

<xsl:stylesheet
		xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
		xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
		xmlns:plan="http://docs.g-vo.org/std/TAPPlan.xsd"
		xmlns="http://www.w3.org/1999/xhtml"
		version="1.0">

	 	<xsl:include href="dachs-xsl-config.xsl"/>
		
		<!-- ############################################## Global behaviour -->

		<xsl:output method="xml" 
			doctype-public="-//W3C//DTD XHTML 1.0 Strict//EN"
			doctype-system="http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd"/>

		<!-- Don't spill the content of unknown elements. -->
		<xsl:template match="text()"/>

		<xsl:template match="plan:plan">
				<html>
						<head>
								<title>Query Plan</title>
								<xsl:call-template name="localCompleteHead"/>
								<style type="text/css"><![CDATA[
										.nestbox {
												padding: 1ex;
												margin-top: 2ex;
												border: 1px solid grey;
												position: relative;
										}
										.boxtitle {
												background-color: white;
												position: absolute;
												top: -3ex;
										}
								]]></style>
						</head>
						<body>
								<h1>Query Plan</h1>
								<xsl:apply-templates/>
						</body>
				</html>
		</xsl:template>

		<xsl:template match="plan:query">
				<h2>Executed query:</h2>
				<pre class="exquery">
						<xsl:value-of select="."/>
				</pre>
				<h2>Operations</h2>
		</xsl:template>

		<xsl:template match="plan:operation">
				<div class="nestbox">
						<xsl:apply-templates/>
				</div>
		</xsl:template>

		<xsl:template match="plan:description">
				<p class="boxtitle"><xsl:value-of select="."/></p>
		</xsl:template>

		<xsl:template match="plan:cost">
				<p>Cost:
						<xsl:apply-templates/>
				</p>
		</xsl:template>

		<xsl:template match="plan:rows">
				<p>Rows:
						<xsl:apply-templates/>
				</p>
		</xsl:template>

		<xsl:template match="plan:min">
				<xsl:text> &gt; </xsl:text><xsl:value-of select="."/>
		</xsl:template>

		<xsl:template match="plan:max">
				<xsl:text> &lt; </xsl:text><xsl:value-of select="."/>
		</xsl:template>

		<xsl:template match="plan:value">
				<xsl:text> (</xsl:text>
				<xsl:value-of select="."/>
				<xsl:text>)</xsl:text>
		</xsl:template>

</xsl:stylesheet>


<!-- vim:et:sw=4:sta
-->
