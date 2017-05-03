<?xml version="1.0" encoding="UTF-8"?>
<!-- Shamelessly lifted from astrogrid dsa and then hacked.  Operating
on verbal permission here. -->

<xsl:stylesheet
    xmlns:uws="http://www.ivoa.net/xml/UWS/v1.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns="http://www.w3.org/1999/xhtml"
    version="1.0">
    
    <!-- A stylesheet to convert a UWS job-summary into HTML.  -->
    
    <xsl:output method="xml" 
      doctype-public="-//W3C//DTD XHTML 1.0 Strict//EN"
      doctype-system="http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd"/>

    <!-- Don't spill the content of unknown elements. -->
    <xsl:template match="text()"/>

    <xsl:template match="uws:parameter">
      <dt><xsl:value-of select="@id"/></dt>
      <dd><xsl:value-of select="text()"/></dd>
    </xsl:template>

    <xsl:template match="uws:parameters">
      <dl><xsl:apply-templates/></dl>
    </xsl:template>

    <xsl:template match="/">
        <html>
            <head>
              <title>UWS job <xsl:value-of select="/*/uws:jobId"/></title>
            </head>
            <body>
                <h1>UWS job <xsl:value-of select="/*/uws:jobId"/></h1>
                <xsl:apply-templates/>
            </body>
        </html>
    </xsl:template>

    <xsl:template match="uws:job">
      <xsl:variable name="jobId"><xsl:value-of select="uws:jobId"/></xsl:variable>
      <xsl:variable name="phase"><xsl:value-of select="uws:phase"/></xsl:variable>
      <dl>
        <dt><xsl:text>Phase:</xsl:text></dt>
        <dd><xsl:value-of select="uws:phase"/></dd>

        <dt><xsl:text>Start time</xsl:text></dt>
        <dd><xsl:value-of select="uws:startTime"/></dd>

        <dt><xsl:text>End time:</xsl:text></dt>
        <dd><xsl:value-of select="uws:endTime"/></dd>

        <dt><xsl:text>Maximum duration:</xsl:text></dt>
        <dd><xsl:value-of select="uws:executionDuration"/></dd>

        <dt><xsl:text>Destruction time:</xsl:text></dt>
        <dd><xsl:value-of select="uws:destruction"/></dd>

        <dt>Parameters</dt>
        <dd><xsl:apply-templates/></dd>

        <xsl:if test="$phase='COMPLETED'">
          <dt><xsl:text>Query results:</xsl:text></dt>
          <dd><a>
            <xsl:attribute name="href">
              <xsl:value-of select="$jobId"/>/results/result</xsl:attribute>
             Result</a></dd>
        </xsl:if>

        <xsl:if test="$phase='ERROR'">
          <dt><xsl:text>Error message:</xsl:text></dt>
          <dd><xsl:value-of select="uws:errorSummary/uws:message"/></dd>
        </xsl:if>

      </dl>
      <xsl:if test="$phase='PENDING'">
          <form method="post">
            <xsl:attribute name="action">
              <xsl:value-of select="$jobId"/>/phase</xsl:attribute>
              <input type="hidden" name="PHASE" value="RUN"/>
              <input type="submit" value="Execute"/>
          </form>
        </xsl:if>
      <xsl:if test="$phase='EXECUTING' or $phase='QUEUED'">
        <p>Use your browser's reload to update the phase information.</p>
        <form method="post">
          <xsl:attribute name="action">
            <xsl:value-of select="$jobId"/>/phase</xsl:attribute>
              <input type="hidden" name="PHASE" value="ABORT"/>
              <input type="submit" value="Abort execution"/>
          </form></xsl:if>
      <p>
        <form method="post">
          <xsl:attribute name="action">
            <xsl:value-of select="$jobId"/></xsl:attribute>
           <input type="hidden" name="ACTION" value="DELETE"/>
           <input type="submit" value="Delete job"/></form></p>
      <p>
        <form method="post">
          <xsl:attribute name="action">
            <xsl:value-of select="$jobId"/>/destruction</xsl:attribute>
          <input type="submit" value="Change destruction time to"/>
          <input type="text" name="DESTRUCTION">
            <xsl:attribute name="value"><xsl:value-of select="uws:destruction"/></xsl:attribute>
            <xsl:attribute name="size">23</xsl:attribute>
          </input> </form> </p>
       <p>
        <a href="../dlasync">List of known jobs</a></p>
  </xsl:template>
</xsl:stylesheet>
<!-- vi:et:sw=2:sta 
-->
