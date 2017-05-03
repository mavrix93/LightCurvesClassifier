   <!-- 
    This stylesheet defines a couple of templates that can be overridden
    to customise the appearance of xml-generated DaCHS pages. -->

<xsl:stylesheet
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns="http://www.w3.org/1999/xhtml"
  version="1.0">

  <xsl:template name="localCompleteHead">
      <link rel="stylesheet" href="/static/css/gavo_dc.css"
          type="text/css"/>
      <!-- in GAVO DC, don't index this, there are better meta pages -->
       <meta name="robots" content="noindex,nofollow"/>
  </xsl:template>

  <xsl:template name="localMakeFoot">
      <hr/>
       <a href="/">The GAVO Data Center</a>
  </xsl:template>
</xsl:stylesheet>

