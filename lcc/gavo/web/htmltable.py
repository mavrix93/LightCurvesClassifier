"""
A renderer for Data to HTML/stan
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import datetime
import itertools
import os
import re
import urlparse
import urllib

from nevow import flat
from nevow import loaders
from nevow import rend
from nevow import tags as T

from gavo import base
from gavo import formats
from gavo import rsc
from gavo import svcs
from gavo import stc
from gavo import utils
from gavo.base import valuemappers
from gavo.protocols import products
from gavo.rscdef import rmkfuncs
from gavo.web import common


_htmlMFRegistry = valuemappers.ValueMapperFactoryRegistry()
_registerHTMLMF = _htmlMFRegistry.registerFactory


def _defaultMapperFactory(colDesc):
	def coder(val):
		if val is None:
			return
		return unicode(val)
	return coder
_registerHTMLMF(_defaultMapperFactory)


# insert new general factories here

floatTypes = set(["real", "float", "double", "double precision"])

def _sfMapperFactory(colDesc):
	if colDesc["dbtype"] not in floatTypes:
		return
	if colDesc["displayHint"].get("sf"):
		fmtStr = "%%.%df"%int(colDesc["displayHint"].get("sf"))
		def coder(val):
			if val is None:
				return "N/A"
			else:
				return fmtStr%val
		return coder
_registerHTMLMF(_sfMapperFactory)


def _hmsMapperFactory(colDesc):
	if colDesc["displayHint"].get("type")!="hms":
		return
	colDesc["unit"] = "h:m:s"
	sepChar = colDesc["displayHint"].get("sepChar", " ")
	sf = int(colDesc["displayHint"].get("sf", 2))
	def coder(val):
		if val is None:
			return "N/A"
		else:
			return utils.degToHms(val, sepChar, sf)
	return coder
_registerHTMLMF(_hmsMapperFactory)


def _dmsMapperFactory(colDesc):
	if colDesc["displayHint"].get("type")!="dms":
		return
	colDesc["unit"] = "d:m:s"
	sepChar = colDesc["displayHint"].get("sepChar", " ")
	sf = int(colDesc["displayHint"].get("sf", 2))
	def coder(val):
		if val is None:
			return "N/A"
		return utils.degToDms(val, sepChar, sf)
	return coder
_registerHTMLMF(_dmsMapperFactory)


def _unitMapperFactory(colDesc):
	"""returns a factory that converts between units for fields that have
	a displayUnit displayHint.

	The stuff done here has to be done for all factories handling unit-based
	floating point values.  Maybe we want to do "decorating" meta-factories?
	"""
	if colDesc["displayHint"].get("displayUnit") and \
			colDesc["displayHint"]["displayUnit"]!=colDesc["unit"]:
		try:
			factor = base.computeConversionFactor(colDesc["unit"], 
				colDesc["displayHint"]["displayUnit"])
		except base.BadUnit:
			# bad unit somewhere; ignore display hint
			base.ui.notifyError("Bad unit while computing conversion factor.")
			return None

		colDesc["unit"] = colDesc["displayHint"]["displayUnit"]
		fmtStr = "%%.%df"%int(colDesc["displayHint"].get("sf", 2))
		def coder(val):
			if val is None:
				return "N/A"
			return fmtStr%(val*factor)
		return coder
_registerHTMLMF(_unitMapperFactory)


def _stringWrapMF(baseMF):
	"""returns a factory that that stringifies floats and makes N/A from
	Nones coming out of baseMF and passes everything else through.
	"""
	def factory(colDesc):
		handler = baseMF(colDesc)
		if colDesc["displayHint"].get("sf", None):
			fmtstr = "%%.%df"%int(colDesc["displayHint"]["sf"])
		fmtstr = "%s"
		if handler:
			def realHandler(val):
				res = handler(val)
				if isinstance(res, float):
					return fmtstr%res
				else:
					if res is None:
						return "N/A"
					else:
						return res
			return realHandler
	return factory

_registerHTMLMF(_stringWrapMF(valuemappers.datetimeMapperFactory))


def humanDatesFactory(colDesc):
	format, unit = {"humanDate": ("%Y-%m-%d %H:%M:%S", ""),
		"humanDay": ("%Y-%m-%d", "") }.get(
			colDesc["displayHint"].get("type"), (None, None))
	if format and colDesc["dbtype"] in ("date", "timestamp"):
		colDesc["unit"] = unit
		def coder(val):
			if val is None:
				return "N/A"
			else:
				colDesc["datatype"], colDesc["arraysize"] = "char", "*"
				colDesc["xtype"] = "adql:TIMESTAMP"
				colDesc["unit"] = ""
				try:
					return val.strftime(format)
				except ValueError:  # probably too old a date, fall back to a hack
					return val.isoformat()
		return coder
_registerHTMLMF(humanDatesFactory)


def humanTimesFactory(colDesc):
	if colDesc["displayHint"].get("type")=="humanTime":
		sf = int(colDesc["displayHint"].get("sf", 0))
		fmtStr = "%%02d:%%02d:%%0%d.%df"%(sf+3, sf)
		def coder(val):
			if val is None:
				return "N/A"
			else:
				if isinstance(val, (datetime.time, datetime.datetime)):
					return fmtStr%(val.hours, val.minutes, val.second)
				elif isinstance(val, datetime.timedelta):
					hours = val.seconds//3600
					minutes = (val.seconds-hours*3600)//60
					seconds = (val.seconds-hours*3600-minutes*60)+val.microseconds/1e6
					return fmtStr%(hours, minutes, seconds)
		return coder
_registerHTMLMF(humanTimesFactory)


def jdMapperFactory(colDesc):
	"""maps JD, MJD, unix timestamp, and julian year columns to 
	human-readable datetimes.

	MJDs are caught by inspecting the UCD.
	"""
	if (colDesc["displayHint"].get("type")=="humanDate"
			and colDesc["dbtype"] in ("double precision", "real")):

		if colDesc["unit"]=="d":
			if "mjd" in colDesc["ucd"].lower() or colDesc["xtype"]=="mjd":
				converter = stc.mjdToDateTime
			else:
				converter = stc.jdnToDateTime
		elif colDesc["unit"]=="s":
			converter = datetime.datetime.utcfromtimestamp
		elif colDesc["unit"]=="yr":
			converter = stc.jYearToDateTime
		else:
			return None

		def fun(val):
			if val is None:
				return "N/A"
			return utils.formatISODT(converter(val))
		colDesc["datatype"], colDesc["arraysize"] = "char", "*"
		colDesc["xtype"] = "adql:TIMESTAMP"
		colDesc["unit"] = ""
		return fun
_registerHTMLMF(jdMapperFactory)


def _sizeMapperFactory(colDesc):
	"""is a factory for formatters for file sizes and similar.
	"""
	if colDesc["unit"]!="byte":
		return
	sf = int(colDesc["displayHint"].get("sf", 1))
	def coder(val):
		if val is None:
			return "N/A"
		else:
			return utils.formatSize(val, sf)
	return coder
_registerHTMLMF(_sizeMapperFactory)


def _barMapperFactory(colDesc):
	if colDesc["displayHint"].get("type")!="bar":
		return
	def coder(val):
		if val:
			return T.hr(style="width: %dpx"%int(val), title="%.2f"%val,
				class_="scoreBar")
		return ""
	return coder
_registerHTMLMF(_barMapperFactory)


def _productMapperFactory(colDesc):
	if colDesc["displayHint"].get("type")!="product":
		return
	if colDesc["displayHint"].get("nopreview"):
		mouseoverHandler = None
	else:
		mouseoverHandler = "insertPreview(this, null)"
	fixedArgs = ""
	def coder(val):
		if val:
			return T.a(href=products.makeProductLink(val)+fixedArgs,
				onmouseover=mouseoverHandler,
				class_="productlink")[re.sub(r"\?.*", "", 
					os.path.basename(urllib.unquote_plus(str(val)[4:])))]
		else:
			return ""
	return coder
_registerHTMLMF(_productMapperFactory)


def _simbadMapperFactory(colDesc):
	"""is a mapper yielding links to simbad.

	To make this work, you need to furnish the OutputField with a
	select="array[alphaFloat, deltaFloat]" or similar.

	You can give a coneMins displayHint to specify the search radius in
	minutes.
	"""
	if colDesc["displayHint"].get("type")!="simbadlink":
		return
	radius = float(colDesc["displayHint"].get("coneMins", "1"))
	def coder(data):
		alpha, delta = data[0], data[1]
		if alpha and delta:
			return T.a(href="http://simbad.u-strasbg.fr/simbad/sim-coo?Coord=%s"
				"&Radius=%f"%(urllib.quote("%.5fd%+.5fd"%(alpha, delta)),
					radius))["[Simbad]"]
		else:
			return ""
	return coder
_registerHTMLMF(_simbadMapperFactory)


def _bibcodeMapperFactory(colDesc):
	if colDesc["displayHint"].get("type")!="bibcode":
		return
	def coder(data):
		if data:
			for item in data.split(","):
				yield T.a(href=base.getConfig("web", "adsMirror")+
					"/cgi-bin/nph-bib_query?bibcode="+urllib.quote(item.strip()))[
					item.strip()]
				yield ", "
		else:
			yield ""
	return coder
_registerHTMLMF(_bibcodeMapperFactory)


def _keepHTMLMapperFactory(colDesc):
	if colDesc["displayHint"].get("type")!="keephtml":
		return
	def coder(data):
		if data:
			return T.raw(data)
		return ""
	return coder
_registerHTMLMF(_keepHTMLMapperFactory)


def _imageURLMapperFactory(colDesc):
	if colDesc["displayHint"].get("type")!="imageURL":
		return
	width = colDesc["displayHint"].get("width")
	def coder(data):
		if data:
			res = T.img(src=data, alt="Image at %s"%data)
			if width:
				res(width=width)
			return res
		return ""
	return coder
_registerHTMLMF(_imageURLMapperFactory)


def _urlMapperFactory(colDesc):
	if colDesc["displayHint"].get("type")!="url":
		return

	anchorText = colDesc.original.getProperty("anchorText", None)
	if anchorText:
		def makeAnchor(data):
			return anchorText
	else:
		def makeAnchor(data): #noflake: conditional definition
			return urllib.unquote(
				urlparse.urlparse(data)[2].split("/")[-1])

	def coder(data):
		if data:
			return T.a(href=data)[makeAnchor(data)]
		return ""
	return coder
_registerHTMLMF(_urlMapperFactory)


def _booleanCheckmarkFactory(colDesc):
	"""inserts mappers for values with displayHint type=checkmark.

	These render a check mark if the value is python-true, else nothing.
	"""
	if colDesc["displayHint"].get("type")!="checkmark":
		return
	def coder(data):
		if data:
			return u"\u2713"
		return ""
	return coder
_registerHTMLMF(_booleanCheckmarkFactory)


_registerHTMLMF(valuemappers._pgSphereMapperFactory)

#  Insert new, more specific factories here


class HeadCellsMixin(object):
	"""A mixin providing renders for table headings.

	The class mixing in must give the SerManager used in a serManager
	attribute.
	"""
	def data_fielddefs(self, ctx, ignored):
		return self.serManager.table.tableDef.columns

	def render_headCell(self, ctx, colDef):
		cd = self.serManager.getColumnByName(colDef.key)
		cont = colDef.getLabel()
		desc = cd["description"]
		if not desc:
			desc = cont
		tag = ctx.tag(title=desc)[T.xml(cont)]
		if cd["unit"]:
			tag[T.br, "[%s]"%cd["unit"]]
		note = cd["note"]
		if note:
			noteURL = "#note-%s"%note.tag
			ctx.tag[T.sup[T.a(href=noteURL)[note.tag]]]
		return tag


class HeadCells(rend.Page, HeadCellsMixin):
	def __init__(self, serManager):
		self.serManager = serManager

	docFactory = loaders.stan(
		T.tr(data=T.directive("fielddefs"), render=rend.sequence) [
			T.th(pattern="item", render=T.directive("headCell"), 
				class_="thVertical")
		])


_htmlMetaBuilder = common.HTMLMetaBuilder()


class HTMLDataRenderer(rend.Fragment):
	"""A base class for rendering tables and table lines.

	Both HTMLTableFragment (for complete tables) and HTMLKeyValueFragment
	(for single rows) inherit from this.
	"""
	def __init__(self, table, queryMeta):
		self.table, self.queryMeta = table, queryMeta
		super(HTMLDataRenderer, self).__init__()
		self._computeDefaultTds()
		self._computeHeadCellsStan()

	def _compileRenderer(self, source):
		"""returns a function object from source.

		Source must be the function body of a renderer.  The variable data
		contains the entire row, and the thing must return a string or at
		least stan (it can use T.tag).
		"""
		code = ("def format(data):\n"+
			utils.fixIndentation(source, "  ")+"\n")
		return rmkfuncs.makeProc("format", code, "", None, 
			queryMeta=self.queryMeta, source=source, T=T)

	def _computeSerializationRules(self):
		"""creates the serialization manager and the formatter sequence.

		These are in the attributes serManager and formatterSeq, respectively.
		formatterSeq consists of triples of (name, formatter, fullRow), where 
		fullRow is true if the formatter wants to be passed the full row rather
		than just the column value.
		"""
		self.serManager = valuemappers.SerManager(self.table, withRanges=False,
			mfRegistry=_htmlMFRegistry, acquireSamples=False)
		self.formatterSeq = []
		for index, (desc, field) in enumerate(
				zip(self.serManager, self.table.tableDef)):
			formatter = self.serManager.mappers[index]
			if isinstance(field, svcs.OutputField):
				if field.wantsRow:
					desc["wantsRow"] = True
				if field.formatter:
					formatter = self._compileRenderer(field.formatter)
			self.formatterSeq.append(
				(desc["name"], formatter, desc.get("wantsRow", False)))

	def _computeDefaultTds(self):
		"""leaves a sequence of children for each row in the
		defaultTds attribute.

		This calls _computeSerializationRules.  The function was
		(and can still be) used for stan-based serialization of HTML tables,
		but beware that that is dead slow.  The normal rendering doesn't
		use defaultTds any more.
		"""
		self._computeSerializationRules()
		self.defaultTds = []
		for (name, formatter, wantsRow) in self.formatterSeq:
			if wantsRow:
				self.defaultTds.append(
					T.td(formatter=formatter, render=T.directive("useformatter")))
			else:
				self.defaultTds.append(T.td(
					data=T.slot(unicode(name)),
					formatter=formatter,
					render=T.directive("useformatter")))

	def render_footnotes(self, ctx, data):
		"""renders the footnotes as a definition list.
		"""
		if self.serManager.notes:
			yield T.hr(class_="footsep")
			yield T.dl(class_="footnotes")[[
				T.xml(note.getContent(targetFormat="html", 
					macroPackage=self.serManager.table.tableDef))
				for tag, note in sorted(self.serManager.notes.items())]]

	def render_useformatter(self, ctx, data):
		attrs = ctx.tag.attributes
		formatVal = attrs["formatter"]
		if formatVal is None:
			formatVal = str
		del ctx.tag.attributes["formatter"]
		val = formatVal(data)
		if val is None:
			val = "N/A"
		return ctx.tag[val]

	def _computeHeadCellsStan(self):
		self.headCells = HeadCells(self.serManager)
		self.headCellsStan = T.xml(self.headCells.renderSynchronously())

	def render_headCells(self, ctx, data):
		"""returns the header line for this table as an XML string.
		"""
# The head cells are prerendered and memoized since they might occur 
# quite frequently in long tables.
		return ctx.tag[self.headCellsStan]

	def data_fielddefs(self, ctx, data):
		return self.table.tableDef.columns

	def render_meta(self, ctx, data):
		metaKey = ctx.tag.children[0]
		if self.table.getMeta(metaKey, propagate=False):
			ctx.tag.clear()
			_htmlMetaBuilder.clear()
			return ctx.tag[self.table.buildRepr(metaKey, _htmlMetaBuilder)]
		else:
			return ""


class HTMLTableFragment(HTMLDataRenderer):
	"""A nevow renderer for result tables.
	"""
	rowsPerDivision = 25

	def _getRowFormatter(self):
		"""returns a callable returning a rendered row in HTML (as used for the
		stan xml tag).
		"""
		source = [
			"def formatRow(row, rowAttrs=''):",
			"  res = ['<tr%s>'%rowAttrs]",]
		for index, (name, _, wantsRow) in enumerate(self.formatterSeq):
			if wantsRow:
				source.append("  val = formatters[%d](row)"%index)
			else:
				source.append("  val = formatters[%d](row[%s])"%(index, repr(name)))
			source.extend([
#				"  import code;code.interact(local=locals())",
				"  if val is None:",
				"    val = 'N/A'",
				"  if isinstance(val, basestring):",
				"    serFct = escapeForHTML",
				"  else:",
				"    serFct = flatten",
				"  res.append('<td>%s</td>'%serFct(val))",])
		source.extend([
			"  res.append('</tr>')",
			"  return ''.join(res)"])

		return utils.compileFunction("\n".join(source), "formatRow", {
				"formatters": [p[1] for p in self.formatterSeq],
				"escapeForHTML": common.escapeForHTML,
				"flatten": flat.flatten})

	def render_rowSet(self, ctx, items):
		# slow, use render_tableBody
		return ctx.tag(render=rend.mapping)[self.defaultTds]

	def render_tableBody(self, ctx, data):
		"""returns HTML-rendered table rows in chunks of rowsPerDivision.

		We don't use stan here since we can concat all those tr/td much faster
		ourselves.
		"""
		rowAttrsIterator = itertools.cycle([' class="data"', ' class="data even"'])
		formatRow = self._getRowFormatter()
		rendered = []
		yield T.xml("<tbody>")
		for row in self.table:
			rendered.append(formatRow(row, rowAttrsIterator.next()))
			if len(rendered)>=self.rowsPerDivision:
				yield T.xml("\n".join(rendered))
				yield self.headCellsStan
				rendered = []
		yield T.xml("\n".join(rendered)+"\n</tbody>")

	docFactory = loaders.stan(T.div(class_="tablewrap")[
		T.div(render=T.directive("meta"), class_="warning")["_warning"],
		T.table(class_="results") [
				T.thead(render=T.directive("headCells")),
				T.tbody(render=T.directive("tableBody"))],
			T.invisible(render=T.directive("footnotes")),
		]
	)


class HTMLKeyValueFragment(HTMLDataRenderer, HeadCellsMixin):
	"""A nevow renderer for single-row result tables.
	"""
	def data_firstrow(self, ctx, data):
		return self.table.rows[0]

	def makeDocFactory(self):
		return loaders.stan([
			T.div(render=T.directive("meta"), class_="warning")["_warning"],
			T.table(class_="keyvalue", render=rend.mapping,
					data=T.directive("firstrow")) [
				[[T.tr[
						T.th(data=colDef, render=T.directive("headCell"),
							class_="thHorizontal"),
						td],
					T.tr(class_="keyvaluedesc")[T.td(colspan=2)[
						colDef.description]]]
					for colDef, td in zip(self.serManager.table.tableDef.columns, 
						self.defaultTds)]],
			T.invisible(render=T.directive("footnotes")),
			])
	
	docFactory = property(makeDocFactory)


def writeDataAsHTML(data, outputFile, acquireSamples=False):
	"""writes data's primary table to outputFile.  

	(acquireSamples is actually ignored; it is just present for compatibility
	with the other writers until I rip out the samples stuff altogether).
	"""
	if isinstance(data, rsc.Data):
		data = data.getPrimaryTable()
	fragment = HTMLTableFragment(data, svcs.emptyQueryMeta)
	outputFile.write(flat.flatten(fragment))


formats.registerDataWriter("html", writeDataAsHTML, "text/html", "HTML")
