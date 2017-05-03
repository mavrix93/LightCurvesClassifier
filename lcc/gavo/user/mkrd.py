"""
Creation of resource descriptors

When we get structured data, we can suggest resource descriptors.

Here, we try this for data described through primary FITS headers and 
VOTables.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


# We probably want to turn this around and first create the RD and pass
# that around so the individual analyzers can add, e.g. global metadata.

import datetime
import os
import re
import sys

from gavo import base
from gavo import grammars
from gavo import rscdef
from gavo import votable
from gavo import utils
from gavo.grammars import fitsprodgrammar
from gavo.grammars import fitstablegrammar
from gavo.formats import votableread
from gavo.utils import ElementTree
from gavo.utils import fitstools

MS = base.makeStruct


ignoredFITSHeaders = set(["COMMENT", "SIMPLE", "BITPIX", "EXTEND", 
	"NEXTEND", "SOFTNAME", "SOFTVERS", "SOFTDATE", "SOFTAUTH", "SOFTINST",
	"HISTORY", "BZERO", "BSCALE", "DATAMIN", "DATAMAX"])
wcsKey = re.compile("CD.*|CRVAL.*|CDELT.*|NAXIS.*|CRPIX.*|CTYPE.*|CUNIT.*"
	"|CROTA.*|RADECSYS|AP?_\d_\d|BP?_\d_\d|LATPOLE|LONPOLE")


def isIgnoredKeyword(kw):
	"""returns true if kw should not be translated or put into the table.

	This is important for all WCS keywords when you want to compute
	SIAP bboxes; these keywords must not be translated.
	"""
	return kw in ignoredFITSHeaders or wcsKey.match(kw)


def structToETree(aStruct):
	"""returns an ElementTree for the copyable content of aStruct.

	Note that due to manipulations at parse time and non-copyable content,
	this will, in general, not reproduce the original XML trees.
	"""
	nodeStack = [ElementTree.Element(aStruct.name_)]
	for evType, elName, value in aStruct.iterEvents():
		try:
			if evType=="start":
				nodeStack.append(ElementTree.SubElement(nodeStack[-1], elName))
			elif evType=="end":
				nodeStack.pop()
			elif evType=="value":
				if value is None or value is base.NotGiven:
					continue
				if elName=="content_":
					nodeStack[-1].text = value
				else:
					if not isinstance(value, basestring):
						# TODO: figure out if something is a reference by inspecting
						# the attribute definition; meanwhile, just assume it is:
						value = value.id
					nodeStack[-1].set(elName, value)
			else:
				raise base.Error("Invalid struct event: %s"%evType)
		except:
			base.ui.notifyError("Badness occurred in element %s, event %s,"
				" value %s\n"%(elName, evType, value))
			raise
	return nodeStack[-1]


FT_TYPE_MAP = {
	"B": "bytea",
	"A": "text",
	"I": "smallint",
	"J": "integer",
	"K": "bigint",
	"E": "real",
	"D": "double precision",
}

def getTypeForFTColumn(fitsCol):
	"""returns a DaCHS type for FITS table column.

	This currently ignores array sizes and such.  Well, people can always
	fix things manually.
	"""
	mat = re.match("(\d*)(.)$", fitsCol.format)
	if not mat or not mat.group(2) in FT_TYPE_MAP:
		raise base.ReportableError("FITS type code '%s' of %s not handled"
			" by gavo mkrd; add handling if you can."%(fitsCol.format, fitsCol.name))
	return FT_TYPE_MAP[mat.group(2)]


def makeTableFromFT(rd, srcName, opts):
	from gavo.utils import pyfits
	cols, nameMaps = [], {}
	nameMaker = base.VOTNameMaker()

	for fitsCol in pyfits.open(srcName)[1].columns:
		destName = nameMaker.makeName(fitsCol)
		if destName!=fitsCol.name:
			nameMaps[destName] = fitsCol.name
		cols.append(MS(rscdef.Column,
			type=getTypeForFTColumn(fitsCol),
			name=destName,
			unit=fitsCol.unit,
			ucd="",
			description="FILL IN"))
	table = rscdef.TableDef(rd, id=opts.tableName, onDisk=True,
		columns=cols)
	table.nameMaps = nameMaps
	return table


def makeDataForFT(rd, srcName, opts):
	targetTable = rd.tables[0]
	# nameMaps left by makeTableFromFT
	rmkMaps =[MS(rscdef.MapRule, key=key, content_="vars['%s']"%src) 
		for key, src in targetTable.nameMaps.iteritems()]

	grammar = MS(fitstablegrammar.FITSTableGrammar)
	sources = MS(rscdef.SourceSpec, 
		pattern=["*.fits"], recurse=True)
	rowmaker = MS(rscdef.RowmakerDef, id="gen_rmk", idmaps="*", maps=[rmkMaps])
	make = MS(rscdef.Make, 
		table=targetTable,
		rowmaker=rowmaker)

	return MS(rscdef.DataDescriptor,
		id="import",
		sources=sources,
		grammar=grammar,
		rowmakers=[rowmaker],
		make=make)


def makeTableFromFITS(rd, srcName, opts):
	keyMappings = []
	table = rscdef.TableDef(rd, id=opts.tableName, onDisk=True)
	headerCards = fitstools.openFits(srcName)[0].header.ascardlist()
	for index, card in enumerate(headerCards):
		if isIgnoredKeyword(card.key):
			continue
		colName = re.sub("[^a-z]", "_", card.key.lower())
		if not colName:
			continue

		if isinstance(card.value, basestring):
			type = "text"
		elif isinstance(card.value, int):
			type = "integer"
		else:
			type = "real"

		table.feedObject("column", MS(rscdef.Column,
			name=colName, unit="FILLIN", ucd="FILLIN", type=type,
			description=card.comment))
		keyMappings.append((colName, card.key))
	rd.setProperty("mapKeys", ", ".join("%s:%s"%(v,k) for k,v in keyMappings))
	return table.finishElement()


def makeDataForFITS(rd, srcName, opts):
	targetTable = rd.tables[0]
	dd = rscdef.DataDescriptor(rd, id="import_"+opts.tableName)
	grammar = fitsprodgrammar.FITSProdGrammar(dd)
	grammar.feedObject("qnd", True)
	rowfilter = base.parseFromString(grammars.Rowfilter, """
		<rowfilter procDef="//products#define">
				<bind key="table">"%s"</bind>
				<bind key="owner">"FILLIN"</bind>
				<bind key="embargo">"FILLIN"</bind>
		</rowfilter>"""%(targetTable.getQName()))
	grammar.feedObject("rowfilter", rowfilter)
	grammar.feedObject("mapKeys", MS(grammars.MapKeys,
		content_=rd.getProperty("mapKeys")))
	grammar.finishElement()
	dd.grammar = grammar
	dd.feedObject("sources", MS(rscdef.SourceSpec, 
		pattern=["*.fits"], recurse=True))
	dd.feedObject("rowmaker", MS(rscdef.RowmakerDef, idmaps="*", id="gen_rmk"))
	dd.feedObject("make", MS(rscdef.Make, table=targetTable, rowmaker="gen_rmk"))
	return dd


def makeTableFromVOTable(rd, srcName, opts):
	rawTable = votable.parse(open(srcName)).next()
	return votableread.makeTableDefForVOTable(opts.tableName, 
		rawTable.tableDefinition, onDisk=True)


def makeDataForVOTable(rd, srcName, opts):
	rowmaker = MS(rscdef.RowmakerDef, id="makerows_"+opts.tableName,
		idmaps="*")

	# The qualifiedId monkeying is necessary since otherwise the
	# ReferenceAttribute.unparse thinks it's ok to return the objects raw.
	# Face it: I've not really had serialization in mind when writing all
	# this.
	rowmaker.qualifiedId = rowmaker.id
	rd.tables[0].qualifiedId = rd.tables[0].id

	return MS(rscdef.DataDescriptor,
		grammar=MS(rscdef.getGrammar("voTableGrammar")),
		sources=MS(rscdef.SourceSpec, pattern=srcName),
		rowmaker=rowmaker,
		makes=[MS(rscdef.Make, table=rd.tables[0], rowmaker=rowmaker)])


tableMakers = {
	"FITS": makeTableFromFITS,
	"VOT": makeTableFromVOTable,
	"FT": makeTableFromFT,
}

dataMakers = {
	"FITS": makeDataForFITS,
	"VOT": makeDataForVOTable,
	"FT": makeDataForFT,
}


def makeRD(args, opts):
	from gavo import rscdesc
	rd = rscdesc.RD(None, schema=os.path.basename(opts.resdir),
		resdir=opts.resdir)

	for key, value in [
		("title", "FILL-IN"),
		("creationDate", utils.formatISODT(datetime.datetime.utcnow())),
		("description", "FILL-IN a long text (and maybe do format='plain'"
			" or even format='rst'"),
		("copyright", "Free to use."),
		("creator.name", "Author, S."),
		("creator", ""),
		("creator.name", "Other, A."),
		("subject", "One Keyword"),
		("subject", "Two Words"),
		("content.type", "Catalog"),
		("coverage.waveband", "Optical"),
		("coverage.profile", "AllSky ICRS"),]:
			rd.addMeta(key, value)

	rd.feedObject("table", tableMakers[opts.srcForm](rd, args[0], opts))
	rd.feedObject("data", dataMakers[opts.srcForm](rd, args[0], opts))
	return rd.finishElement()


def indent(elem, level=0):
	i = "\n" + level*"\t"
	if len(elem):
		if not elem.text or not elem.text.strip():
			elem.text = i + "\t"
		if not elem.tail or not elem.tail.strip():
			elem.tail = i
		for child in elem:
			indent(child, level+1)
		if not child.tail or not child.tail.strip():
			child.tail = i
		if not elem.tail or not elem.tail.strip():
			elem.tail = i
	else:
		if level and (not elem.tail or not elem.tail.strip()):
			elem.tail = i


def writePrettyPrintedXML(root):
	indent(root)
	ElementTree.ElementTree(root).write(sys.stdout, encoding="utf-8")


def parseCommandLine():
	from optparse import OptionParser
	parser = OptionParser(usage = "%prog [options] <sample>")
	parser.add_option("-f", "--format", help="Input file format: "
		" FITS, VOT or FT (FITS table)"
		"  Default: Detect from file name", dest="srcForm", default=None,
		action="store", type="str")
	parser.add_option("-t", "--table-name", help="Name of the generated table",
		dest="tableName", default="main", action="store", type="str")
	parser.add_option("-r", "--resdir", help="Override resdir (and schema)",
		dest="resdir", default=os.getcwd(), action="store", type="str")
	opts, args = parser.parse_args()
	if len(args)!=1:
		parser.print_help(file=sys.stderr)
		sys.exit(1)
	if not opts.srcForm:
		ext = os.path.splitext(args[0])[1].lower()
		if ext in set([".xml", ".vot"]):
			opts.srcForm = "VOT"
		elif ext==".fits":
			opts.srcForm = "FITS"
		else:
			sys.stderr.write("Cannot guess format, use -f option: %s\n"%args[0])
			parser.print_help(file=sys.stderr)
			sys.exit(1)
	return opts, args


def main():
	# hack to make id and onDisk copyable so we see them on iterEvent
	rscdef.TableDef._id.copyable = rscdef.TableDef._onDisk.copyable = True
	rscdef.DataDescriptor._id.copyable = True
	opts, args = parseCommandLine()
	rd = makeRD(args, opts)
	rd._metaAttr.copyable = True
	eTree = structToETree(rd)
	writePrettyPrintedXML(eTree)


if __name__=="__main__":
	main()
