"""
Formatting, text manipulation, string constants, and such.
"""

#c Copyright 2008-2016, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import datetime
import math
import os
import random
import re
import string
import time
from email import utils as emailutils

from gavo.utils import codetricks
from gavo.utils import misctricks
from gavo.utils.excs import Error, SourceParseError

floatRE = r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?"
dateRE = re.compile("\d\d\d\d-\d\d-\d\d$")
datetimeRE = re.compile("\d\d\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ?$")
identifierPattern = re.compile("[A-Za-z_][A-Za-z0-9_]*$")
isoTimestampFmt = "%Y-%m-%dT%H:%M:%SZ"
isoTimestampFmtNoTZ = "%Y-%m-%dT%H:%M:%S"
entityrefPat = re.compile("&([^;])+;")

# file names that don't cause headaches in URLs and are otherwise reasonable
# benign (so, let's disallow shell metachars while we're at it).
_SAFE_FILENAME = re.compile("[,-:=@-Z_a-z{}~-]+$")

xmlEntities = {
		'lt': '<',
		'gt': '>',
		'amp': '&',
		'apos': "'",
		'quot': '"',
}


def formatSize(val, sf=1):
	"""returns a human-friendly representation of a file size.
	"""
	if val<1e3:
		return "%d Bytes"%int(val)
	elif val<1e6:
		return "%.*fkiB"%(sf, val/1024.)
	elif val<1e9:
		return "%.*fMiB"%(sf, val/1024./1024.)
	else:
		return "%.*fGiB"%(sf, val/1024./1024./1024)


def makeEllipsis(aStr, maxLen=60):
	"""returns aStr cropped to maxLen if necessary.

	Cropped strings are returned with an ellipsis marker.
	"""
	if len(aStr)>maxLen:
		return aStr[:maxLen-3]+"..."
	return aStr


def makeLeftEllipsis(aStr, maxLen=60):
	"""returns aStr shortened to maxLen by dropping prefixes if necessary.

	Cropped strings are returned with an ellipsis marker.
	>>> makeLeftEllipsis("0123456789"*2, 11)
	'...23456789'
	"""
	if len(aStr)>maxLen:
		return "..."+aStr[-maxLen+3:]
	return aStr


@codetricks.document
def getFileStem(fPath):
	"""returns the file stem of a file path.

	The base name is what remains if you take the base name and split off
	extensions.  The extension here starts with the last dot in the file name,
	except up to one of some common compression extensions (.gz, .xz, .bz2, 
	.Z, .z) is stripped off the end if present before determining the extension.

	>>> getFileStem("/foo/bar/baz.x.y")
	'baz.x'
	>>> getFileStem("/foo/bar/baz.x.gz")
	'baz'
	>>> getFileStem("/foo/bar/baz")
	'baz'
	"""
	for ext in [".gz", ".xz", ".bz2", ".Z", ".z"]:
		if fPath.endswith(ext):
			fPath = fPath[:-len(ext)]
			break
	return os.path.splitext(os.path.basename(fPath))[0]
	

def formatSimpleTable(data, stringify=True):
	"""returns a string containing a text representation of tabular data.

	All columns of data are simply stringified, then the longest member
	determines the width of the text column.  The behaviour if data
	does not contain rows of equal length is unspecified; data must
	contain at least one row.

	If you have serialised the values in data yourself, pass stringify=False.
	"""
	if stringify:
		data = [[str(v) for v in row] for row in data]

	if not data:
		return ""

	colWidthes = [max(len(row[colInd]) for row in data)
		for colInd in range(len(data[0]))]
	fmtStr = "  ".join("%%%ds"%w for w in colWidthes)
	table = "\n".join(fmtStr%tuple(row) for row in data)
	return table


def getRelativePath(fullPath, rootPath, liberalChars=True):
	"""returns rest if fullPath has the form rootPath/rest and raises an
	exception otherwise.

	Pass liberalChars=False to make this raise a ValueError when
	URL-dangerous characters (blanks, amperands, pluses, non-ASCII, and 
	similar) are present in the result.  This is mainly for products.
	"""
	if not fullPath.startswith(rootPath):
		raise ValueError(
			"Full path %s does not start with resource root %s"%(fullPath, rootPath))
	res = fullPath[len(rootPath):].lstrip("/")
	if not liberalChars and not _SAFE_FILENAME.match(res):
		raise ValueError("File path '%s' contains characters known to"
			" the DaCHS authors to be hazardous in URLs.  Please defuse the name"
			" before using it for published names (or see howDoI)."%res)
	return res


def resolvePath(rootPath, relPath):
	"""joins relPath to rootPath and makes sure the result really is
	in rootPath.
	"""
	relPath = relPath.lstrip("/")
	fullPath = os.path.realpath(os.path.join(rootPath, relPath))
	if not fullPath.startswith(rootPath):
		raise ValueError(
			"Full path %s does not start with resource root %s"%(fullPath, rootPath))
	if not os.path.exists(fullPath):
		raise ValueError(
			"Invalid path %s. This should not happend."%(fullPath))
	return fullPath


def fixIndentation(code, newIndent, governingLine=0):
	"""returns code with all whitespace from governingLine removed from
	every line and newIndent prepended to every line.

	governingLine lets you select a line different from the first one
	for the determination of the leading white space.  Lines before that
	line are left alone.

	>>> fixIndentation("  foo\\n  bar", "")
	'foo\\nbar'
	>>> fixIndentation("  foo\\n   bar", " ")
	' foo\\n  bar'
	>>> fixIndentation("  foo\\n   bar\\n    baz", "", 1)
	'foo\\nbar\\n baz'
	>>> fixIndentation("  foo\\nbar", "")
	Traceback (most recent call last):
	Error: Bad indent in line 'bar'
	"""
	codeLines = [line for line in code.split("\n")]
	reserved, codeLines = codeLines[:governingLine], codeLines[governingLine:]
	while codeLines:
		if codeLines[0].strip():
			firstIndent = re.match("^\s*", codeLines[0]).group()
			break
		else:
			reserved.append(codeLines.pop(0))
	if codeLines:
		fixedLines = []
		for line in codeLines:
			if not line.strip():
				fixedLines.append(newIndent)
			else:
				if line[:len(firstIndent)]!=firstIndent:
					raise Error("Bad indent in line %s"%repr(line))
				fixedLines.append(newIndent+line[len(firstIndent):])
	else:
		fixedLines = codeLines
	reserved = [newIndent+l.lstrip() for l in reserved]
	return "\n".join(reserved+fixedLines)


@codetricks.memoized
def _getREForPercentExpression(format):
	"""helps parsePercentExpression.
	"""
	parts = re.split(r"(%\w)", format)
	newReParts = []
	for ind, p in enumerate(parts):
		if p.startswith("%"):
			# the time-parsing hack explained in the docstring:
			if ind+2<len(parts) and parts[ind+1]=="":
				if p[1] in "HMS":
					newReParts.append("(?P<%s>..)"%p[1])
				else:
					raise ValueError(
						"At %s: conversions with no intervening literal not supported."% p)
			else:
				newReParts.append("(?P<%s>.*?)"%p[1])
		else:
			newReParts.append(re.escape(p))
	return re.compile("".join(newReParts)+"$")


def parsePercentExpression(literal, format):
	"""returns a dictionary of parts in the %-template format.

	format is a template with %<conv> conversions, no modifiers are
	allowed.  Each conversion is allowed to contain zero or more characters
	matched stingily.  Successive conversions without intervening literals
	aren't really supported.  There's a hack for strptime-type times, though:
	H, M, and S just eat two characters each if there's no seperator.
	
	This is really only meant as a quick hack to support times like 25:33.

	>>> r=parsePercentExpression("12,xy:33,","%a:%b,%c"); r["a"], r["b"], r["c"]
	('12,xy', '33', '')
	>>> sorted(parsePercentExpression("2357-x", "%H%M-%u").items())
	[('H', '23'), ('M', '57'), ('u', 'x')]
	>>> r = parsePercentExpression("12,13,14", "%a:%b,%c")
	Traceback (most recent call last):
	ValueError: '12,13,14' cannot be parsed using format '%a:%b,%c'
	"""
	mat = _getREForPercentExpression(format).match(literal)
	if not mat:
		raise ValueError("'%s' cannot be parsed using format '%s'"%(
			literal, format))
	return mat.groupdict()


def parseAssignments(assignments):
	"""returns a name mapping dictionary from a list of assignments.

	This is the preferred form of communicating a mapping from external names
	to field names in records to macros -- in a string that contains
	":"-seprated pairs seperated by whitespace, like "a:b  b:c", where
	the incoming names are leading, the desired names are trailing.

	If you need defaults to kick in when the incoming data is None, try
	_parseDestWithDefault in the client function.

	This function parses a dictionary mapping original names to desired names.

	>>> parseAssignments("a:b  b:c")
	{'a': 'b', 'b': 'c'}
	"""
	return dict([(lead, trail) for lead, trail in
		[litPair.split(":") for litPair in assignments.split()]])


@codetricks.document
def hmsToDeg(hms, sepChar=None):
	"""returns the time angle (h m s.decimals) as a float in degrees.

	>>> "%3.8f"%hmsToDeg("22 23 23.3")
	'335.84708333'
	>>> "%3.8f"%hmsToDeg("22:23:23.3", ":")
	'335.84708333'
	>>> "%3.8f"%hmsToDeg("222323.3", "")
	'335.84708333'
	>>> hmsToDeg("junk")
	Traceback (most recent call last):
	ValueError: Invalid time with sepChar None: 'junk'
	"""
	hms = hms.strip()
	try:
		if sepChar=="":
			parts = hms[:2], hms[2:4], hms[4:]
		else:
			parts = hms.split(sepChar)
		if len(parts)==3:
			hours, minutes, seconds = parts
		elif len(parts)==2:
			hours, minutes = parts
			seconds = 0
		else:
			raise ValueError("Too many parts")
		timeSeconds = int(hours)*3600+float(minutes)*60+float(seconds)
	except ValueError:
		raise ValueError("Invalid time with sepChar %s: %s"%(
			repr(sepChar), repr(hms)))
	return timeSeconds/3600/24*360


@codetricks.document
def dmsToDeg(dmsAngle, sepChar=None):
	"""returns the degree minutes seconds-specified dmsAngle as a 
	float in degrees.

	>>> "%3.8f"%dmsToDeg("45 30.6")
	'45.51000000'
	>>> "%3.8f"%dmsToDeg("45:30.6", ":")
	'45.51000000'
	>>> "%3.8f"%dmsToDeg("-45 30 7.6")
	'-45.50211111'
	>>> dmsToDeg("junk")
	Traceback (most recent call last):
	ValueError: Invalid dms value with sepChar None: 'junk'
	"""
	dmsAngle = dmsAngle.strip()
	sign = 1
	if dmsAngle.startswith("+"):
		dmsAngle = dmsAngle[1:].strip()
	elif dmsAngle.startswith("-"):
		sign, dmsAngle = -1, dmsAngle[1:].strip()
	try:
		if sepChar=="":
			parts = dmsAngle[:2], dmsAngle[2:4], dmsAngle[4:]
		else:
			parts = dmsAngle.split(sepChar)
		if len(parts)==3:
			deg, min, sec = parts
		elif len(parts)==2:
			deg, min = parts
			sec = 0
		else:
			raise ValueError("Invalid # of parts")
		arcSecs = sign*(int(deg)*3600+float(min)*60+float(sec))
	except ValueError:
		raise misctricks.logOldExc(
			ValueError("Invalid dms value with sepChar %s: %s"%(
				repr(sepChar), repr(dmsAngle))))
	return arcSecs/3600


def fracHoursToDeg(fracHours):
	"""returns the time angle fracHours given in decimal hours in degrees.
	"""
	return float(fracHours)*360./24.


def degToHms(deg, sepChar=" ", secondFracs=3):
	"""converts a float angle in degrees to an time angle (hh:mm:ss.mmm).

	>>> degToHms(0)
	'00 00 00.000'
	>>> degToHms(122.056, secondFracs=1)
	'08 08 13.4'
	>>> degToHms(-0.056, secondFracs=0)
	'-00 00 13'
	>>> degToHms(-1.056, secondFracs=0)
	'-00 04 13'
	>>> degToHms(359.2222, secondFracs=4, sepChar=":")
	'23:56:53.3280'
	>>> "%.4f"%hmsToDeg(degToHms(256.25, secondFracs=9))
	'256.2500'
	"""
	sign = ""
	if deg<0:
		sign = "-"
		deg = -deg
	rest, hours = math.modf(deg/360.*24)
	rest, minutes = math.modf(rest*60)
	if secondFracs<1:
		secondFracs = -1
	return sign+sepChar.join(["%02d"%int(hours), "%02d"%abs(int(minutes)), 
		"%0*.*f"%(secondFracs+3, secondFracs, abs(rest*60))])


def degToDms(deg, sepChar=" ", secondFracs=2):
	"""converts a float angle in degrees to a sexagesimal string.

	>>> degToDms(0)
	'+0 00 00.00'
	>>> degToDms(-0.25)
	'-0 15 00.00'
	>>> degToDms(-23.50, secondFracs=4)
	'-23 30 00.0000'
	>>> "%.4f"%dmsToDeg(degToDms(-25.6835, sepChar=":"), sepChar=":")
	'-25.6835'
	"""
	sign = '+'
	if deg<0:
		sign = "-"
		deg = -deg
	rest, degs = math.modf(deg)
	rest, minutes = math.modf(rest*60)
	if secondFracs==0:
		secondFracs = -1
	return sepChar.join(["%s%d"%(sign, int(degs)), "%02d"%abs(int(minutes)), 
		"%0*.*f"%(secondFracs+3, secondFracs, abs(rest*60))])


def datetimeToRFC2616(dt):
	"""returns a UTC datetime object in the format requried by http.

	This may crap when you fuzz with the locale.  In general, when handling
	"real" times within the DC, prefer unix timestamps over datetimes and
	use the other *RFC2616 functions.
	"""
	return dt.strftime('%a, %d %b %Y %H:%M:%S GMT')


def parseRFC2616Date(s):
	"""returns seconds since unix epoch representing UTC from the HTTP-compatible
	time specification s.
	"""
	parts = emailutils.parsedate_tz(s)
	return emailutils.mktime_tz(parts)


# The following timegm implementation is due to Frederik Lundh
def _d(y, m, d, days=(0,31,59,90,120,151,181,212,243,273,304,334,365)): 
		return (((y - 1901)*1461)/4 + days[m-1] + d + (
			(m > 2 and not y % 4 and (y % 100 or not y % 400)) and 1))

def timegm(tm, epoch=_d(1970,1,1)): 
		year, month, day, h, m, s = tm[:6] 
		return (_d(year, month, day) - epoch)*86400 + h*3600 + m*60 + s


def formatRFC2616Date(secs=None):
	"""returns an RFC2616 date string for UTC seconds since unix epoch.
	"""
	if secs is None:
		secs = time.time()
	return emailutils.formatdate(secs, localtime=False, usegmt=True)


_isoDTRE = re.compile(r"(?P<year>\d\d\d\d)-?(?P<month>\d\d)-?(?P<day>\d\d)"
		r"(?:[T ](?P<hour>\d\d):?(?P<minute>\d\d):?"
		r"(?P<seconds>\d\d)(?P<secFracs>\.\d*)?Z?(\+00:00)?)?$")


@codetricks.document
def parseISODT(literal):
	"""returns a datetime object for a ISO time literal.

	There's no real timezone support yet, but we accept and ignore various
	ways of specifying UTC.

	>>> parseISODT("1998-12-14")
	datetime.datetime(1998, 12, 14, 0, 0)
	>>> parseISODT("1998-12-14T13:30:12")
	datetime.datetime(1998, 12, 14, 13, 30, 12)
	>>> parseISODT("1998-12-14T13:30:12Z")
	datetime.datetime(1998, 12, 14, 13, 30, 12)
	>>> parseISODT("1998-12-14T13:30:12.224Z")
	datetime.datetime(1998, 12, 14, 13, 30, 12, 224000)
	>>> parseISODT("19981214T133012Z")
	datetime.datetime(1998, 12, 14, 13, 30, 12)
	>>> parseISODT("19981214T133012+00:00")
	datetime.datetime(1998, 12, 14, 13, 30, 12)
	>>> parseISODT("junk")
	Traceback (most recent call last):
	ValueError: Bad ISO datetime literal: junk
	"""
	# temporary hack while ESAVO registry is broken:
	literal = literal.rstrip("Z")
	mat = _isoDTRE.match(literal.strip())
	if not mat:
		raise ValueError("Bad ISO datetime literal: %s"%literal)
	parts = mat.groupdict()
	if parts["hour"] is None:
		parts["hour"] = parts["minute"] = parts["seconds"] = 0
	if parts["secFracs"] is None:
		parts["secFracs"] = 0
	else:
		parts["secFracs"] = "0"+parts["secFracs"]
	return datetime.datetime(int(parts["year"]), int(parts["month"]),
		int(parts["day"]), int(parts["hour"]), int(parts["minute"]), 
		int(parts["seconds"]), int(float(parts["secFracs"])*1000000))


_SUPPORTED_DT_FORMATS =[
	'%Y-%m-%dT%H:%M:%S',
	'%Y-%m-%d %H:%M:%S',
	'%Y-%m-%d',]

def parseDefaultDatetime(literal):
	if literal is None or isinstance(literal, datetime.datetime):
		return literal
	if literal.endswith("Z"):
		literal = literal[:-1]
	# just nuke fractional seconds, they're trouble with strptime.
	literal = literal.split(".")[0]
	for format in _SUPPORTED_DT_FORMATS:
		try:
			return datetime.datetime(
				*time.strptime(literal, format)[:6])
		except ValueError:
			pass
	return parseISODT(literal)


def parseDefaultDate(literal):
	if literal is None or isinstance(literal, datetime.date):
		return literal
	return datetime.date(*time.strptime(literal, '%Y-%m-%d')[:3])


def parseDefaultTime(literal):
	if literal is None or isinstance(literal, datetime.time):
		return literal
	return datetime.time(*time.strptime(literal, '%H:%M:%S')[3:6])


def formatISODT(dt):
	"""returns some ISO8601 representation of a datetime instance.

	The reason for preferring this function over a simple str is that
	datetime's default representation is too difficult for some other
	code (e.g., itself); hence, this code suppresses any microsecond part
	and always adds a Z (where strftime works, utils.isoTimestampFmt produces
	an identical string).

	The behaviour of this function for timezone-aware datetimes is undefined.

	For convenience, None is returned as None

	>>> formatISODT(datetime.datetime(2015, 10, 20, 12, 34, 22, 250))
	'2015-10-20T12:34:22Z'
	>>> formatISODT(datetime.datetime(1815, 10, 20, 12, 34, 22, 250))
	'1815-10-20T12:34:22Z'
	"""
	if dt is None:
		return None
	return dt.replace(microsecond=0, tzinfo=None).isoformat()+"Z"


class NameMap(object):
	"""is a name mapper fed from a simple text file.

	The text file format simply is:

	<target-id> "TAB" <src-id>{whitespace <src-id>}

	src-ids have to be encoded quoted-printable when they contain whitespace
	or other "bad" characters ("="!).  You can have #-comments and empty
	lines.
	"""
	def __init__(self, src, missingOk=False):
		self._parseSrc(src, missingOk)
	
	def __contains__(self, name):
		return name in self.namesDict

	def _parseSrc(self, src, missingOk):
		self.namesDict = {}
		try:
			f = open(src)
		except IOError:
			if not missingOk:
				raise
			else:
				return
		try:
			for ln in f:
				if ln.startswith("#") or not ln.strip():
					continue
				ob, names = re.split("\t+", ln)
				for name in names.lower().split():
					self.namesDict[name.decode("quoted-printable")] = ob
		except ValueError:
			raise misctricks.logOldExc(ValueError(
				"Syntax error in %s: Line %s not understood."%(src, repr(ln))))
		f.close()
	
	def resolve(self, name):
		return self.namesDict[name.lower()]


_STANDARD_ENTITIES = {
		'lt': '<',
		'gt': '>',
		'amp': '&',
		'apos': "'",
		'quot': '"',
}


def _decodeEntityref(matob):
	entRef = matob.group(1)
	if entRef in _STANDARD_ENTITIES:
		return _STANDARD_ENTITIES[entRef]
	elif entRef.startswith("#x"):
		return unichr(int(entRef[2:], 16))
	elif entRef.startswith("#"):
		return unichr(int(entRef[1:]))
	else:
		raise ValueError("Unknown entity reference: &%s;"%entRef)


def replaceXMLEntityRefs(unicodeString):
	return entityrefPat.sub(_decodeEntityref, unicodeString)


def ensureOneSlash(s):
	"""returns s with exactly one trailing slash.
	"""
	return s.rstrip("/")+"/"


def _iterSimpleTextNoContinuation(f):
	"""helps iterSimpleText.
	"""
	for (lineNumber, curLine) in enumerate(f):
		curLine = curLine.strip()
		if curLine and not curLine.startswith("#"):
			yield (lineNumber+1), curLine


@codetricks.document
def iterSimpleText(f):
	"""iterates over physLineNumber, line in f with some usual 
	conventions for simple data files.

	You should use this function to read from simple configuration and/or
	table files that don't warrant a full-blown grammar/rowmaker combo.
	The intended use is somewhat like this::
		
		with open(rd.getAbsPath("res/mymeta")) as f:
			for lineNumber, content in iterSimpleText(f):
				try:
					...
				except Exception, exc:
					sys.stderr.write("Bad input line %s: %s"%(lineNumber, exc))

	The grammar rules are, specifically:

	* leading and trailing whitespace is stripped
	* empty lines are ignored
	* lines beginning with a hash are ignored
	* lines ending with a backslash are joined with the following line;
	  to have intervening whitespace, have a blank in front of the backslash.
	"""
	iter = _iterSimpleTextNoContinuation(f)
	try:
		while True:
			lineNumber, curLine = iter.next()

			while curLine.endswith("\\"):
				try:
					lineNumber, newStuff = iter.next()
				except StopIteration:
					raise SourceParseError("File ends with a backslash",
						location="line %d"%lineNumber)
				curLine = curLine[:-1]+newStuff

			yield lineNumber, curLine
	except StopIteration:  # all done, leave loop
		pass


_RANDOM_STRING_OK_CHARS = string.letters+string.digits+"_.,"

def getRandomString(length):
	"""returns a random string of harmless printable characters.
	"""
	return "".join(
		random.choice(_RANDOM_STRING_OK_CHARS) for c in range(length))


def safe_str(val):
	if isinstance(val, str):
		return val
	elif isinstance(val, unicode):
		return val.encode("ascii", "ignore")
	else:
		return str(val)


def parseAccept(aString):
	"""parses an RFC 2616 accept header and returns a dict mapping media
	type patterns to their (unparsed) parameters.

	If aString is None, an empty dict is returned

	If we ever want to do fancy things with http content negotiation, this
	will be further wrapped to provide something implementing the complex
	RFC 2616 rules; this primitive interface really is intended for telling
	apart browsers (which accept text/html) from other clients (which
	hopefully do not) at this point.

	>>> sorted(parseAccept("text/html, text/*; q=0.2; level=3").items())
	[('text/*', 'q=0.2; level=3'), ('text/html', '')]
	>>> parseAccept(None)
	{}
	"""
	res = {}
	if aString is not None:
		for item in aString.split(","):
			if ";" in item:
				key, params = item.split(";", 1)
			else:
				key, params = item, ""
			res[key.strip()] = params.strip()
	
	return res


def _test():
	import doctest, texttricks
	doctest.testmod(texttricks)


if __name__=="__main__":
	_test()
