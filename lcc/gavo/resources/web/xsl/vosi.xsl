<?xml version="1.0" encoding="UTF-8"?>

<xsl:stylesheet
    xmlns:avl="http://www.ivoa.net/xml/VOSIAvailability/v1.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:ri="http://www.ivoa.net/xml/RegistryInterface/v1.0"
    xmlns:cap="http://www.ivoa.net/xml/VOSICapabilities/v1.0"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:vtm="http://www.ivoa.net/xml/VOSITables/v1.0"
    xmlns="http://www.w3.org/1999/xhtml"
    version="1.0">
   
   	<xsl:include href="dachs-xsl-config.xsl"/>
    
    <!-- ############################################## Global behaviour -->

    <xsl:output method="xml" 
      doctype-public="-//W3C//DTD XHTML 1.0 Strict//EN"
      doctype-system="http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd"/>

    <!-- Don't spill the content of unknown elements. -->
    <xsl:template match="text()"/>


    <!-- ################################### VOSI availability templates -->
    
    <xsl:template match="avl:available">
        <p>This service is <strong>
            <xsl:choose>
                <xsl:when test=".='true'">up</xsl:when>
                <xsl:when test=".='false'">down</xsl:when>
                <xsl:otherwise>broken</xsl:otherwise>
            </xsl:choose></strong></p>
    </xsl:template>

    <xsl:template match="avl:upSince">
        <p>It has been up since <xsl:value-of select="."/>.</p>
    </xsl:template>

    <xsl:template match="avl:downAt">
        <p>It will go offline approximately at <xsl:value-of select="."/>.</p>
    </xsl:template>

    <xsl:template match="avl:backAt">
        <p>The operators predict it will be back at
            <xsl:value-of select="."/>.</p>
    </xsl:template>

    <xsl:template match="avl:note">
        <p><xsl:value-of select="."/></p>
    </xsl:template>

    <xsl:template match="avl:availability">
        <html>
            <head>
              <title>Service availability</title>
              <xsl:call-template name="localCompleteHead"/>
            </head>
            <body>
                <h1>Availability information for this service</h1>
    				    <xsl:apply-templates/>
                <p><em>All times in UTC</em></p>
                <xsl:call-template name="localMakeFoot"/>
            </body>
        </html>
    </xsl:template>


    <!-- ################################### VOSI capabilities templates -->

    <xsl:template match="identifier"/>

    <xsl:template match="curation">
        <dl class="curation">
            <xsl:apply-templates/>
        </dl>
    </xsl:template>

    <xsl:template match="content">
        <div class="content">
            <p>Further information may be found at the
                <a>
                    <xsl:attribute name="href">
                        <xsl:value-of select="referenceURL"/>
                    </xsl:attribute>
                    reference URL</a>.
            </p>
            <xsl:apply-templates/>
        </div>
    </xsl:template>

    <xsl:template match="title">
        <p class="vosititle"><xsl:value-of select="."/></p>
    </xsl:template>

    <xsl:template match="publisher">
        <dt>Publisher</dt><dd><xsl:value-of select="."/></dd>
    </xsl:template>

    <xsl:template match="creator/name">
        <xsl:value-of select="."/>
    </xsl:template>

    <xsl:template match="creator/logo">
        <xsl:text> </xsl:text>
        <img alt="[Creator logo]">
            <xsl:attribute 
                name="src"><xsl:value-of select="."/></xsl:attribute>
        </img>
    </xsl:template>

    <xsl:template match="creator">
        <dt>Created by</dt><dd><xsl:apply-templates/></dd>
    </xsl:template>

    <xsl:template match="contact">
        <dt>Contact</dt>
        <dd>
            <xsl:value-of select="name"/><br/>
            <xsl:value-of select="address"/><br/>
            <xsl:value-of select="email"/><br/>
            <xsl:value-of select="telephone"/><br/>
        </dd>
    </xsl:template>

    <xsl:template match="content/description">
        <p><strong>Description: </strong><xsl:value-of select="."/></p>
    </xsl:template>

    <xsl:template match="accessURL">
        <a>
            <xsl:attribute name="href">
                <xsl:value-of select="."/>
            </xsl:attribute>
            <xsl:value-of select="."/>
        </a>
    </xsl:template>

    <xsl:template match="interface">
        <dt>Interface
            <xsl:if test="@xsi:type">
                <xsl:value-of select="@xsi:type"/>
            </xsl:if>
        </dt>
        <dd>
            <xsl:apply-templates/>
        </dd>
    </xsl:template>

    <xsl:template match="dataModel">
       <dt>Data model
           <xsl:value-of select="."/>
       </dt>
       <dd>
           <xsl:value-of select="@ivo-id"/>
       </dd>
    </xsl:template>

    <xsl:template match="language/version">
        Version <xsl:value-of select="."/>;
    </xsl:template>

    <xsl:template match="description" priority="0">
        <xsl:value-of select="."/>
    </xsl:template>

    <xsl:template match="language/userDefinedFunction">
        <dt class="udfsig"><xsl:value-of select="signature"/></dt>
        <dd><xsl:value-of select="description"/></dd>
    </xsl:template>

    <xsl:template match="language">
        <dt>Query language <xsl:value-of select="name"/></dt>
        <dd>
            <xsl:apply-templates select="version|description"/>
            <xsl:if test="userDefinedFunction">
                <p class="sechdr">User Defined Functions</p>
                <dl class="udflist">
                    <xsl:apply-templates select="userDefinedFunction"/>
                </dl>
            </xsl:if>
        </dd>
    </xsl:template>

    <xsl:template match="outputFormat">
        <dt>Output format <xsl:value-of select="mime"/></dt>
        <dd> 
            <xsl:apply-templates select="description"/>
            <xsl:if test="alias"><br/>
                Also available as <xsl:value-of select="alias"/>.
            </xsl:if>
        </dd>
    </xsl:template>

    <xsl:template match="uploadMethod">
        <dt>Upload method supported</dt>
        <dd><xsl:value-of select="@ivo-id"/>
        </dd>
    </xsl:template>

    <xsl:template match="default">
      by default: <xsl:value-of select="."/><xsl:text> </xsl:text>
        <xsl:value-of select="@unit"/><br/>
    </xsl:template>

    <xsl:template match="hard">
       not exceedable: <xsl:value-of select="."/><xsl:text> </xsl:text>
        <xsl:value-of select="@unit"/>
    </xsl:template>

    <xsl:template match="retentionPeriod">
        <dt>Time a job is kept (in seconds)</dt>
        <dd><xsl:apply-templates/></dd>
    </xsl:template>

    <xsl:template match="executionDuration">
        <dt>Maximal run time of a job</dt>
        <dd><xsl:apply-templates/></dd>
    </xsl:template>

    <xsl:template match="outputLimit">
        <dt>Maximal size of result sets</dt>
        <dd><xsl:apply-templates/></dd>
    </xsl:template>

    <xsl:template match="capability">
        <h2>Capability <xsl:value-of select="@standardID"/></h2>
        <xsl:choose>
            <xsl:when test="@standardID='ivo://ivoa.net/std/TAP'">
                <p>The endpoint for actual database queries.</p>
            </xsl:when>
            <xsl:when test="@standardID='ivo://ivoa.net/std/VOSI#availability'">
                <p>Information on up- and downtimes of the service.</p>
            </xsl:when>
            <xsl:when test="@standardID='ivo://ivoa.net/std/VOSI#capabilities'">
                <p>Information on service properties.</p>
            </xsl:when>
            <xsl:when test="@standardID='ivo://ivoa.net/std/VOSI#tables'">
                <p>The tables exposed by this service (may be large!).</p>
            </xsl:when>
        </xsl:choose>
        <dl class="caplist">
            <xsl:apply-templates/>
        </dl>
    </xsl:template>

    <xsl:template match="cap:capabilities">
        <html>
            <head>
              <title>Service Capabilities</title>
              <xsl:call-template name="localCompleteHead"/>
              <style type="text/css">
                table.caplist {
                    border: 1px solid grey;
                }
                .udfsig {
                    font-family: monospace;
                }
                p.sechdr { /* should be a h3, really, but that doesn't
                    result in a pretty doc structure either, so there. */
                    font-weight: bold;
                    font-size: 120%;
                }
              </style>
            </head>
            <body>
                <h1>Service Capabilities</h1>
                <xsl:apply-templates/>
                <xsl:call-template name="localMakeFoot"/>
            </body>
        </html>
    </xsl:template>


    <!-- #################################################### Table Sets -->

    <xsl:template match="dataType">
        <xsl:value-of select="text()"/>
        <xsl:if test="@arraysize and @arraysize!='1'"
            >[<xsl:value-of select="@arraysize"/>]
        </xsl:if>
    </xsl:template>

    <xsl:template match="column">
        <tr>
            <td><xsl:value-of select="name"/></td>
            <td><xsl:value-of select="unit"/></td>
            <td><xsl:value-of select="ucd"/></td>
            <td><xsl:apply-templates select="dataType"/></td>
            <td><xsl:value-of select="description"/></td>
        </tr>
    </xsl:template>

    <xsl:template match="table">
        <h2>Table <xsl:value-of select="name"/></h2>
        <p><xsl:value-of select="description"/></p>
        <table class="shorttable">
            <tr>
                <th>Name</th>
                <th>Unit</th>
                <th>UCD</th>
                <th>VOTable type</th>
                <th>Description</th>
            </tr>
            <xsl:apply-templates select="column"/>
        </table>
    </xsl:template>

    <xsl:template match="vtm:tableset">
        <html>
            <head>
              <title>VOSI Table Set</title>
              <xsl:call-template name="localCompleteHead"/>
            </head>
            <body>
                <h1>VOSI Table Set</h1>
                <xsl:apply-templates select="*/table"/>
                <xsl:call-template name="localMakeFoot"/>
            </body>
        </html>
    </xsl:template>

</xsl:stylesheet>


<!-- vim:et:sw=4:sta
-->
