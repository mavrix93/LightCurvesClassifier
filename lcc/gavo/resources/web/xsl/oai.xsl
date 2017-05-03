<?xml version="1.0" encoding="UTF-8"?>

<xsl:stylesheet
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:ri="http://www.ivoa.net/xml/RegistryInterface/v1.0"
    xmlns:oai="http://www.openarchives.org/OAI/2.0/"
    xmlns="http://www.w3.org/1999/xhtml"
    version="1.0">
   
   	<xsl:include href="dachs-xsl-config.xsl"/>

    <!-- ############################################## Global behaviour -->

    <xsl:output method="xml" 
      doctype-public="-//W3C//DTD XHTML 1.0 Strict//EN"
      doctype-system="http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd"/>

    <!-- Don't spill the content of unknown elements. -->
    <xsl:template match="text()"/>

	  <xsl:template match="oai:OAI-PMH">
        <html>
            <head>
                <title>OAI PMH</title>
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
                    .deleted a {
                        text-decoration: line-through;
                    }
                ]]></style>
            </head>
            <body>
                <h1>OAI PMH result of <xsl:value-of select="oai:responseDate"/>
                </h1>
    				    <xsl:apply-templates/>
    				    <p><a href="/oai.xml?verb=ListIdentifiers&amp;metadataPrefix=ivo_vor">All identifiers defined here</a></p>
                <xsl:call-template name="localMakeFoot"/>
            </body>
        </html>
    </xsl:template>

    <xsl:template match="oai:request">
        <p class="reqinfo">
            Request verb was <xsl:value-of select="@verb"/>
        </p>
    </xsl:template>

    <xsl:template match="oai:error">
        <div class="errors"><p>Error code <xsl:value-of select="@code"/>:
            <xsl:value-of select="."/></p>
        </div>
    </xsl:template>

    <xsl:template match="oai:ListIdentifiers">
        <ul class="listIdentifiers">
            <xsl:apply-templates/>
        </ul>
    </xsl:template>

    <xsl:template match="oai:header">
        <li>
            <xsl:attribute name="class">oairec
                <xsl:value-of select="@status"/>
            </xsl:attribute>
            <xsl:apply-templates/>
        </li>
    </xsl:template>

    <xsl:template match="oai:identifier">
        <xsl:element name="a">
            <xsl:attribute name="href">/oai.xml?verb=GetRecord&amp;metadataPrefix=ivo_vor&amp;identifier=<xsl:value-of select="."/>
            </xsl:attribute>
            <xsl:value-of select="."/>
        </xsl:element>
    </xsl:template>

    <xsl:template match="oai:metadata">
        <xsl:apply-templates mode="dumpall"/>
    </xsl:template>

    <xsl:template match="*" mode="dumpall">
        <div class="nestbox">
            <p class="boxtitle"><xsl:value-of select="name(.)"/></p>
            <xsl:if test="@ivo-id">
                <a>
                    <xsl:attribute name="href"
                        >/oai.xml?verb=GetRecord&amp;metadataPrefix=ivo_vor&amp;identifier=<xsl:value-of select="@ivo-id"/>
                    </xsl:attribute>&#8594;</a>
            </xsl:if>
            <xsl:apply-templates mode="dumpall"/>
        </div>
    </xsl:template>

    <xsl:template match="/ri:Resource">
        <!-- naked ri:Resource at the root: this is from metarender -->
        <html>
            <head>
                <title>Resource Record for 
                    <xsl:value-of select="identifier"/></title>
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
                    .deleted a {
                        text-decoration: line-through;
                    }
                ]]></style>
            </head>
            <body>
                <h1>Resource Record for <xsl:value-of select="identifier"/>
                </h1>
    				    <xsl:apply-templates mode="dumpall"/>
                <xsl:call-template name="localMakeFoot"/>
            </body>
        </html>
    </xsl:template>
</xsl:stylesheet>


<!-- vim:et:sw=4:sta
-->
