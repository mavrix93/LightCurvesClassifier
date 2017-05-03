"""
A grammar supporting C language boosters (or possibly other mechanisms 
bypassing internal dbtable).

These actually bypass most of our machinery and should only be used if
performance is paramount.  Otherwise, CustomGrammars play much nicer with
the rest of the DC software.

Currently, only one kind of DirectGrammar is supported: C boosters.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import os
import pkg_resources
import re
import shutil
import subprocess

from gavo import base
from gavo import utils
from gavo import rscdef
from gavo.grammars import common


class CBooster(object):
	"""is a wrapper for an import booster written in C using the DC booster
	infrastructure.

	Warning: If you change the booster description, you'll need to touch
	the source to recompile.
	"""
	silence_for_test = False

	def __init__(self, srcName, dataDesc, recordSize=4000, gzippedInput=False,
			autoNull=None, preFilter=None, ignoreBadRecords=False,
			customFlags=""):
		self.dataDesc = dataDesc
		self.recordSize = recordSize
		self.resdir = dataDesc.rd.resdir
		self.srcName = os.path.join(self.resdir, srcName)
		self.autoNull, self.preFilter = autoNull, preFilter
		self.ignoreBadRecords = ignoreBadRecords
		self.gzippedInput = gzippedInput
		self.customFlags = customFlags
		self.bindir = os.path.join(self.resdir, "bin")
		self.binaryName = os.path.join(self.bindir,
			os.path.splitext(os.path.basename(srcName))[0]+"-"+base.getConfig(
				"platform"))
		self._ensureBinary()

	def _copySources(self, wd):
		def getResource(src, dest):
			inF = pkg_resources.resource_stream('gavo', src)
			outF = open(os.path.join(wd, dest), "w")
			outF.write(inF.read())
			outF.close()
			inF.close()
		getResource("resources/src/boosterskel.c", "boosterskel.c")
		getResource("resources/src/boosterskel.h", "boosterskel.h")
		shutil.copyfile(self.srcName, os.path.join(wd, "func.c"))

		# XXX TODO: take this from the embedding data's make;
		# DirectGrammars can't be outside of a data element any more anyway.
		mat = re.search("(?m)^#define QUERY_N_PARS\s+(\d+)", 
			open(self.srcName).read())
		if not mat:
			raise base.ReportableError("Booster function doesn't define QUERY_N_PARS")
		query_n_pars = mat.group(1)

		f = open(os.path.join(wd, "Makefile"), "w")

		if self.dataDesc.grammar.type=="fits":
			f.write("LDFLAGS += -lcfitsio\n")

		f.write("LDFLAGS += -lm\n"
			"CFLAGS += -Wall -DINPUT_LINE_MAX=%d -DQUERY_N_PARS=%s\n"%(
				self.recordSize, query_n_pars))
		if self.autoNull:
			f.write("CFLAGS += -DAUTO_NULL='%s'\n"%self.autoNull.replace(
				"\\", "\\\\"))
		if self.ignoreBadRecords:
			f.write("CFLAGS += -DIGNORE_BAD_RECORDS\n")
		f.write("CFLAGS += -g\n")

		f.write("booster: boosterskel.c func.c\n"
			"\t$(CC) $(CFLAGS) %s -o booster $^ $(LDFLAGS)\n"%self.customFlags)
		f.close()
	
	def _build(self):
		callArgs = {}
		if self.silence_for_test:
			# test instrumentation -- don't worry if the file remains open
			callArgs["stdout"] = open("/dev/null", "w")
		if subprocess.call("make", **callArgs):
			raise base.ReportableError("Booster build failed, messages above.")
	
	def _retrieveBinary(self, od):
		shutil.copyfile("booster", self.binaryName)
		os.chmod(self.binaryName, 0775)

	def _ensureBinary(self):
		"""makes sure the booster binary exists and is up-to-date.
		"""
		if not os.path.exists(self.bindir):
			os.makedirs(self.bindir)
		try:
			if os.path.getmtime(self.srcName)<os.path.getmtime(self.binaryName):
				return
		except os.error:
			pass
		if os.path.exists(self.srcName):
			utils.runInSandbox(self._copySources, self._build, self._retrieveBinary)
		else:
			base.ui.notifyError("Booster source does not exist."
				"  You will not be able to import the enclosing data.",
				hint="Use gavo mkboost to create a skeleton for the booster.")

	def getOutput(self, argName):
		"""returns a pipe you can read the booster's output from.

		As a side effect, it also sets the attribute self.pipe.  We need
		this to be able to retrieve the command status below.
		"""
		if self.preFilter:
			shellCommand = "%s '%s' | %s"%(self.preFilter, argName, self.binaryName)
		elif self.gzippedInput:
			shellCommand = "zcat '%s' | %s"%(argName, self.binaryName)
		else:
			shellCommand = "%s '%s'"%(self.binaryName, argName)

		pipeArgs = {"shell": True, "stdout": subprocess.PIPE}
		if self.silence_for_test:
			# test instrumentation -- don't worry if the file remains open
			pipeArgs["stderr"] = open("/dev/null", "w")
		self.pipe = subprocess.Popen(shellCommand, **pipeArgs)
		return self.pipe.stdout
	
	def getStatus(self):
		return self.pipe.wait()


class DirectGrammar(base.Structure, base.RestrictionMixin):
	"""A user-defined external grammar.

	See the separate document on user-defined code on more on direct grammars.

	Also note the program gavomkboost that can help you generate core for
	the C boosters used by direct grammars.
	"""
	name_ = "directGrammar"

	_cbooster = rscdef.ResdirRelativeAttribute("cBooster", 
		default=base.Undefined,
		description="resdir-relative path to the booster C source.",
		copyable=True)

	_gzippedInput = base.BooleanAttribute("gzippedInput", default=False,
		description="Pipe gzip before booster?",
		copyable=True)

	_autoNull = base.UnicodeAttribute("autoNull", default=None,
		description="Use this string as general NULL value",
		copyable=True)

	_ignoreBadRecords = base.BooleanAttribute("ignoreBadRecords",
		default=False, description="Let booster ignore invalid records?",
		copyable=True)

	_recordSize = base.IntAttribute("recordSize", default=4000,
		description="For bin boosters, read this many bytes to make"
		" up a record; for line-based boosters, this is the maximum"
		" length of an input line.",
		copyable=True)

	_preFilter = base.UnicodeAttribute("preFilter", default=None,
		description="Pipe input through this program before handing it to"
			" the booster; this string is shell-expanded.",
		copyable=True)

	_customFlags = base.UnicodeAttribute("customFlags", default="",
		description="Pass these flags to the C compiler when building the"
		" booster.",
		copyable=True)

	_type = base.EnumeratedUnicodeAttribute("type", default="col", 
		validValues=["col", "bin", "fits", "split"],
		description="Make code for a booster parsing by column indices (col),"
			" by splitting along separators (split), by reading fixed-length"
			" binary records (bin), for from FITS binary tables (fits).",
		copyable=True)

	_splitChar = base.UnicodeAttribute("splitChar", default="|",
		description="For split boosters, use this as the separator",
		copyable=True)

	_mapKeys = base.StructAttribute("mapKeys", childFactory=common.MapKeys,
		default=None, copyable=True, 
		description="For a FITS booster, map DB table column names"
			" to FITS column names (e.g., if the FITS table name flx is to"
			" end up in the DB column flux, say flux:flx).")
	
	_rd = rscdef.RDAttribute()

	isDispatching = False

	def validate(self):
		self._validateNext(DirectGrammar)
		if self.type=='bin':
			if not self.recordSize:
				raise base.StructureError("DirectGrammars reading from binary need"
					" a recordSize attribute")
		if self.mapKeys is not None:
			if self.type!="fits":
				raise base.StructureError("mapKeys is only allowed for FITS"
					" boosters.")

	def onElementComplete(self):
		if self.type=="fits":
			if self.mapKeys:
				self.keyMap = self.mapKeys.maps
			else:
				self.keyMap = {}

	def getBooster(self):
		return CBooster(self.cBooster, self.parent,
			gzippedInput=self.gzippedInput,
			preFilter=self.preFilter,
			autoNull=self.autoNull,
			ignoreBadRecords=self.ignoreBadRecords,
			customFlags=self.customFlags)

	def parse(self, sourceToken, targetData=None):
		booster = self.getBooster()
		makes = self.parent.makes
		if len(makes)!=1:
			raise base.StructureError("Directgrammar only works for data having"
				" exactly one table, but data '%s' has %d"%(
					self.parent.id, len(makes)))

		def copyIn(data):
			data.tables.values()[0].copyIn(booster.getOutput(sourceToken))
			if booster.getStatus():
				raise base.SourceParseError(
					"Booster returned error signature",
					source=sourceToken)
		return copyIn


###################################################
# booster source code generating functions

import sys

def getNameForItem(item):
	return "fi_"+item.name.lower()


# Some pieces to puzzle together the createDumpfile functions
COMMON_MAIN_HEADER = """
/* Common main header */
void createDumpfile(int argc, char **argv)
{
	FILE *destination=stdout;
	char inputLine[INPUT_LINE_MAX];
	int recCount = 0;
/* /Common main header */
"""

NONSEEK_MAIN_INTRO = """
	FILE *inF;

	/* seekable main intro */
	if (argc>2) {
		die(USAGE);
	}
	if (argc==2) {
		if (!(inF = fopen(argv[1], "r"))) {
			die(strerror(errno));
		}
	} else {
		inF = stdin;
	}
  /* /seekable main intro */
"""

COMMON_MAIN_INTRO = """
	/* common main intro */
	writeHeader(destination);
	/* /common main intro */
"""


LOOP_BODY_INTRO = """
		Field *tuple;
		context = inputLine;
		if (!setjmp(ignoreRecord)) {
"""


LOOP_BODY_FOOT = """
			if (!tuple) {
				handleBadRecord("Bad input line at record %d", recCount);
			}
			writeTuple(tuple, QUERY_N_PARS, destination);
			context = NULL;
			recCount ++;
			if (!(recCount%1000)) {
				fprintf(stderr, "%08d\\r", recCount);
				fflush(stderr);
			}
		}
"""


COMMON_MAIN_FOOT = """
	writeEndMarker(destination);
	fprintf(stderr, "%08d records done.\\n", recCount);
}
"""


def _getMakeMacro(item):
	"""returns a maker macro for a column object.
	"""
	try:
		return {
			"integer": "MAKE_INT",
			"smallint": "MAKE_SHORT",
			"double precision": "MAKE_DOUBLE",
			"real": "MAKE_FLOAT",
			"char": "MAKE_CHAR_NULL",
			"bytea": "MAKE_BYTE",
			"text": "MAKE_TEXT",
		}[item.type]
	except KeyError:
		# not a simple case; this could be a place for doing arrays and such
		return "MAKE_somethingelse"


class _CodeGenerator(object):
	"""a base class for code generators.

	You must at least override getItemParser.
	"""
	def __init__(self, grammar, tableDef):
		self.grammar, self.tableDef = grammar, tableDef
		
	def getSetupCode(self):
		"""returns a sequence of C lines for code between an item parser.
		"""
		return []
		
	def getItemParser(self, item, index):
		"""returns code that parses item (a Column instance) at column index
		index.

		You're free to igore index.
		"""
		return []

	def getPreamble(self):
		"""returns a list of lines that make up the top of the booster.
		"""
		return [
		'#include <stdio.h>',
		'#include <math.h>',
		'#include <string.h>',
		'#include <errno.h>',
		'#include "boosterskel.h"',
		'',
		'#define USAGE "Usage: don\'t."',]

	def getPrototype(self):
		"""returns the prototype of the getTuple function.
		"""
		return "Field *getTuple(char *inputLine)"

	def getFooter(self):
		"""returns the code for the createDumpfile method.

		You want to use the C fragments above for that.

		The default returns something that bombs out.
		"""
		return '#error "No getFooter defined in the code generator"'


class _LineBasedCodeGenerator(_CodeGenerator):
	"""a base class for code generators for reading line-based text files.
	"""
	def getFooter(self):
		"""returns the main function of the parser (and possibly other stuff)
		in a string.

		This default implementation works for line-based parsers.
		"""
		return (COMMON_MAIN_HEADER
			+NONSEEK_MAIN_INTRO
			+COMMON_MAIN_INTRO
			+"""
	while (fgets(inputLine, INPUT_LINE_MAX, inF)) {"""
			+LOOP_BODY_INTRO
			+"""
			tuple = getTuple(inputLine);"""
			+LOOP_BODY_FOOT
			+"}\n"
			+COMMON_MAIN_FOOT)


class ColCodeGenerator(_LineBasedCodeGenerator):
	def getItemParser(self, item, index):
		t = item.type
		if "int" in t:
			func = "parseInt"
		elif t in ["real", "float"]:
			func = "parseFloat"
		elif "double" in t:
			func = "parseDouble"
		elif "char" in t:
			func = "parseString"
		elif "bool" in t:
			func = "parseBlankBoolean"
		else:
			func = "parseWhatever"
		return ["%s(inputLine, F(%s), start, len);"%(func, getNameForItem(item))]

	def getPrototype(self):
		"""returns the prototype of the getTuple function.
		"""
		return "Field *getTuple(char *inputLine, int recNo)"


class SplitCodeGenerator(_LineBasedCodeGenerator):
	"""a code generator for parsing files with lineas and separators.
	"""
	def __init__(self, grammar, tableDef):
		self.splitChar = getattr(grammar, "splitChar", "|")
		_CodeGenerator.__init__(self, grammar, tableDef)

	def getPreamble(self):
		return _LineBasedCodeGenerator.getPreamble(self)+[
			"/* delete the next line for POSIX strtok */",
			"#define strtok strtok_u"]

	def getSetupCode(self):
		return _LineBasedCodeGenerator.getSetupCode(self)+[
			'char *curCont;',
			'curCont = strtok(inputLine, "%s");'%self.splitChar]

	def getItemParser(self, item, index):
		t = item.type
		fi = getNameForItem(item)
		if t=="text":
			parse = ["F(%s)->type = VAL_TEXT;"%fi,
				"F(%s)->length = strlen(curCont);"%fi,
				"F(%s)->val.c_ptr = curCont;"%fi,]
		else:
			if t=="smallint":
				cType = "VAL_SHORT"
			elif t=="bigint":
				cType = "VAL_BIGINT"
			elif "int" in t:
				cType = "VAL_INT"
			elif t in ["real", "float"]:
				cType = "VAL_FLOAT"
			elif "double" in t:
				cType = "VAL_DOUBLE"
			elif "char"==t:
				cType = "VAL_CHAR"
			elif "char" in t:
				cType = "VAL_TEXT"
			elif "bool" in t:
				cType = "VAL_BOOL"
			else:
				cType = "###No appropriate type###"
			parse = ["fieldscanf(curCont, %s, %s);"%(fi, cType)]
		parse.append('curCont = strtok(NULL, "%s");'%self.splitChar)
		return parse


class BinCodeGenerator(_CodeGenerator):
	"""a code generator for reading fixed-length binary records.
	"""
	def getItemParser(self, item, index):
		t = item.type
		if t=="integer":
			pline = "%s(%s, *(int32_t*)(line+));"
		elif t=="smallint":
			pline = "%s(%s, *(int16_t*)(line+ ));"
		elif t=="double precision":
			pline = "%s(%s, *(double*)(line+ ));"
		elif t=="real":
			pline = "%s(%s, *(float*)(line+ ));"
		elif t=="char":
			pline = "%s(%s, *(double*)(line+ ), '<nil>');"
		elif t=="bytea":
			pline = "%s(%s, *(double*)(line+ ), '<nil>');"
		else:
			pline = "%s %s"
		return ["/* %s (%s) */"%(item.description, t), 
			pline%(_getMakeMacro(item), getNameForItem(item))]

	def getPreamble(self):
		return _CodeGenerator.getPreamble(self)+[
			"#define FIXED_RECORD_SIZE %d"%self.grammar.recordSize]

	def getFooter(self):
		return (COMMON_MAIN_HEADER
			+"  int bytesRead = 0;\n"
			+NONSEEK_MAIN_INTRO
			+COMMON_MAIN_INTRO
			+"""
	while (1) {
		bytesRead = fread(inputLine, 1, FIXED_RECORD_SIZE, inF);
		if (bytesRead==0) {
			break;
		} else if (bytesRead!=FIXED_RECORD_SIZE) {
			die("Short record: Only %d bytes read.", bytesRead);
		}
		"""
			+LOOP_BODY_INTRO
			+"""
			tuple = getTuple(inputLine, recCount);"""
			+LOOP_BODY_FOOT
			+"}\n"
			+COMMON_MAIN_FOOT)


class FITSCodeGenerator(_CodeGenerator):
	"""A code generator for reading from FITS binary tables.
	"""
	fitsTypes = {
		"B": ("TBYTE", "char"),
		"A": ("TSTRING", "char *"),
		"I": ("TSHORT", "short"),
		"J": ("TLONG", "long"),
		"K": ("TLONGLONG", "long long"),
		"E": ("TFLOAT", "float"),
		"D": ("TDOUBLE", "double")}
	makers = {
		"bigint": "MAKE_BIGINT",
		"bytea": "MAKE_BYTE",
		"text": "MAKE_TEXT",
		"integer": "MAKE_INT",
		"real": "MAKE_FLOAT",
		"double precision": "MAKE_DOUBLE",
	}
	
	def __init__(self, grammar, tableDef):
		from gavo.utils import pyfits
		_CodeGenerator.__init__(self, grammar, tableDef)
		# now fetch the first source to figure out its schema
		if self.grammar.parent.sources is None:
			raise base.StructureError("Cannot make FITS bintable booster without"
				" a source element on the embedding data.")
		try:
			self.fitsTable = pyfits.open(
				self.grammar.parent.sources.iterSources().next())[1]
		except StopIteration:
			raise base.StructureError("Buliding a FITS bintable booster requires"
				" at least one matching source.")
		
		self._computeMatches()
	
	def _computeMatches(self):
		"""adds .fitsIndexForCol and .colForFITSIndex attributes.

		These are matches based on the respective column names, where
		we do a case-insensitive matching for now.

		Nones mean that no corresponding column is present; for FITS columns,
		this means they are ignored.  For table columns, this means that
		stand-in code is generated for filling out later.
		"""
		tableColumns = dict((col.name.lower(), col)
			for col in self.tableDef)
		if len(tableColumns)!=len(self.tableDef.columns):
			raise base.StructureError("Table unsuitable for FITS boosting as"
				" column names identical after case folding are present.",
				hint="Use mapKeys to adapt FITS table names to resolve"
				" the ambiguity")

		self.colForFITSIndex = {}
		for index, fitsCol in enumerate(self.fitsTable.columns):
			columnName = self.grammar.keyMap.get(fitsCol.name, fitsCol.name).lower()
			self.colForFITSIndex[index] = tableColumns.get(columnName)

		self.fitsIndexForColName = {}
		for index, col in self.colForFITSIndex.iteritems():
			if col is None:
				continue
			self.fitsIndexForColName[col.name.lower()] = index
	
	def getItemParser(self, item, index):
		try:
			fitsIndex = self.fitsIndexForColName[item.name.lower()]
			fitsCol = self.fitsTable.columns[fitsIndex]
			castTo = self.fitsTypes[
				self._parseFITSFormat(fitsCol.format, fitsCol.name)[1]
				][1]

			return [
				"/* %s (%s) */"%(item.description, item.type), 
				"if (nulls[%d][rowIndex]) {"%fitsIndex,
				"  MAKE_NULL(%s);"%getNameForItem(item),
				"} else {",
				"	 %s(%s, ((%s*)(data[%d]))[rowIndex]);"%(
					self.makers[item.type], 
					getNameForItem(item),
					castTo,
					fitsIndex),
				"}",]

		except KeyError:
			# no FITS table source column
			return ["MAKE_NULL(%s); /* %s(%s, FILL IN VALUE); */"%(
				getNameForItem(item),
				_getMakeMacro(item), 
				getNameForItem(item))]

	def getPreamble(self):
		return _CodeGenerator.getPreamble(self)+[
			"#include <fitsio.h>",
			"#define FITSCATCH(x) if (x) {fatalFitsError(status);}",
			"void fatalFitsError(int status) {",
			"	if (status==0) {",
			"		return;",
			"	}",
			"	fits_report_error(stderr, status);",
			"	abort();",
			"}",
			]

	def getPrototype(self):
		return "Field *getTuple(void *data[], char *nulls[], int rowIndex)"

	def _parseFITSFormat(self, format, colName):
		"""returns length and typecode for the supported FITS table types.

		All others raise errors.
		"""
		mat = re.match("(\d*)(.)$", format)
		if not mat:
			raise base.ReportableError("FITS type code '%s' of %s not handled"
				" by gavo mkboost; add handling if you can."%(format, colName))
		if not mat.group(2) in self.fitsTypes:
			raise base.ReportableError("FITS type '%s' of %s not handled"
				" by gavo mkboost; add handling if you can."%(
					mat.group(2), colName))
		return int(mat.group(1) or "1"), mat.group(2)

	def _getColDescs(self):
		"""returns a C initializer for an array of FITSColDescs.
		"""
		res = []
		for index, fcd in enumerate(self.fitsTable.columns):
			col = self.colForFITSIndex[index]
			if col is None:
				# table column not part of FITS table, suppress reading
				# my having .cSize=0
				res.append("{.cSize = 0, .fitsType = 0, .index=0}")
				continue

			length, typecode = self._parseFITSFormat(fcd.format, fcd.name)
			
			if typecode=="A":
				# special handling for strings, as we need their size
				# var length strings have been rejected above
				res.append("{.cSize = %d, .fitsType = TSTRING, .index=%d}"%(
					length, index+1))

			else:
				if length!=1:
					raise base.ReportableError("Column %s: Arrays not supported"
						" by gavo mkboost."%fcd.name)
				res.append("{.cSize = sizeof(%s), .fitsType = %s, .index=%d}"%(
					self.fitsTypes[typecode][1], 
					self.fitsTypes[typecode][0],
					index+1))

		return res

	def getFooter(self):
		colDescs = self._getColDescs()
		infoDict = {
			"nCols": len(colDescs),
			"colDescs": "{\n%s\n}"%",\n".join(colDescs),
		}
		return ("""
typedef struct FITSColDesc_s {
	size_t cSize;
	int fitsType;
	int index;  /* in the FITS columns */
} FITSColDesc;

FITSColDesc COL_DESCS[%(nCols)d] = %(colDescs)s;
"""%infoDict+COMMON_MAIN_HEADER
+"""
	fitsfile *fitsInput;
	int ignored, i;
	int status = 0;
	long nRows = 0;
	void *data[%(nCols)d];
	char *nulls[%(nCols)d];

	if (argc>2) {
		die(USAGE);
	}
	if (argc==2) {
		FITSCATCH(fits_open_table(&fitsInput, argv[1], READONLY, &status));
	} else {
		die("FITS tables cannot be read from stdin.");
	}

	FITSCATCH(fits_get_num_rows(fitsInput, &nRows, &status));

	for (i=0; i<%(nCols)d; i++) {
		if (COL_DESCS[i].cSize==0) {
			/* Column not used */
			continue; 

		} else if (COL_DESCS[i].fitsType==TSTRING) {
			char *stringHoldings = NULL;
			if (!(data[i] = malloc(nRows*sizeof(char*)))
				|| !(stringHoldings = malloc(nRows*(COL_DESCS[i].cSize+1)))) {
				die("out of memory");
			} else {
				int k;
				/* Initialize the char* in the data array */
				for (k=0; k<nRows; k++) {
					((char**)(data[i]))[k] = stringHoldings+k*(COL_DESCS[i].cSize+1);
				}
			}

		} else {
			if (!(data[i] = malloc(nRows*COL_DESCS[i].cSize))) {
				die("out of memory");
			}
		}
		if (!(nulls[i] = malloc(nRows*sizeof(char)))) {
			die("out of memory");
		}
		FITSCATCH(fits_read_colnull(fitsInput, COL_DESCS[i].fitsType, 
			COL_DESCS[i].index, 1, 1,
     	nRows, data[i], nulls[i], &ignored, &status));
	}"""%infoDict
		+COMMON_MAIN_INTRO
		+"""	for (i=0; i<nRows; i++) {"""
		+LOOP_BODY_INTRO
		+"""		tuple = getTuple(data, nulls, i);"""
		+LOOP_BODY_FOOT
		+"	}\n"
		+COMMON_MAIN_FOOT)


def getCodeGen(grammar, tableDef):
	"""returns the code generator suitable for making code for grammar.
	"""
	return {
		"bin": BinCodeGenerator,
		"split": SplitCodeGenerator,
		"fits": FITSCodeGenerator,
		"col": ColCodeGenerator,
	}[grammar.type](grammar, tableDef)


def getEnum(td, grammar):
	code = [
		"#define QUERY_N_PARS %d\n"%len(list(td)),
		'enum outputFields {']
	for item in td:
		desc = item.getLabel()
		if not desc:
			desc = item.description
		code.append("\t%-15s  /* %s, %s */"%(getNameForItem(item)+",",
			desc, item.type))
	code.append('};\n')
	return code


def getGetTuple(td, codeGen):
	code = [
		codeGen.getPrototype(),
		"{",
		"\tstatic Field vals[QUERY_N_PARS];"]
	code.extend(indent(codeGen.getSetupCode(), "\t"))
	for index, item in enumerate(td):
		code.extend(indent(codeGen.getItemParser(item, index), "\t"))
	code.extend([
		"\treturn vals;",
		"}"])
	return code


def indent(stringList, indentChar):
	return [indentChar+s for s in stringList]


def buildSource(grammar, td):
	"""returns (possibly incomplete) C source for a booster to read into td.
	"""
	codeGen = getCodeGen(grammar, td)

	code = codeGen.getPreamble()
	code.extend(getEnum(td, grammar))
	code.extend(getGetTuple(td, codeGen))
	code.append(codeGen.getFooter())
	return "\n".join(code)


def getGrammarAndTable(grammarId):
	"""returns a pair of directGrammar and table being fed for a cross-rd
	reference.
	"""
	grammar = base.resolveId(None, grammarId, forceType=DirectGrammar)
	# to figure out the table built, use the parent's make
	makes = grammar.parent.makes
	if len(makes)!=1:
		raise base.StructureError("Directgrammar only works for data having"
			" exactly one table, but data '%s' has %d"%(
				grammar.parent.id, len(makes)))
	tableDef = makes[0].table
	return grammar, tableDef


def parseCmdLine():
	from optparse import OptionParser
	parser = OptionParser(usage = "%prog <id-of-directGrammar>")
	(opts, args) = parser.parse_args()
	if len(args)!=1:
		parser.print_help()
		sys.exit(1)
	return opts, args[0]


def getSource(grammarId):
	"""returns a bytestring containing C source to parse grammarId.
	"""
	grammar, td = getGrammarAndTable(grammarId)
	src = buildSource(grammar, td)
	return src.encode("ascii", "ignore")


def main():
	from gavo import rscdesc #noflake: cache registration
	try:
		opts, grammarId = parseCmdLine()
		print getSource(grammarId)
	except SystemExit, msg:
		sys.exit(msg.code)
