"""
Functions available to rowmaker procs.

Rowmaker procs are compiled in the namespace defined by this module.

Maybe we should allow additional modules to be specified in gavorc?
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import base64
import datetime
import math
import os
import pprint #noflake: exported name
import re #noflake: exported name
import sys #noflake: exported name
import time
import traceback #noflake: exported name
import urllib #noflake: exported name

from gavo import base
from gavo import stc
from gavo import utils
from gavo.base import ( #noflake: exported names
	coords, parseBooleanLiteral, parseInt, sqlmunge,
	makeSitePath, makeAbsoluteURL)
from gavo.base.literals import (identity, #noflake:exported names
	parseInt, parseFloat, parseBooleanLiteral, parseUnicode,
	parseDefaultDate, parseDefaultDatetime, parseDefaultTime, parseCooPair,
	parseSPoint, getDefaultValueParsers)
	
from gavo.rscdef.common import ( #noflake: exported names
	getStandardPubDID, getAccrefFromStandardPubDID,
	getInputsRelativePath)
from gavo.stc import parseSimpleSTCS #noflake: exported name
from gavo.stc.times import ( #noflake: exported names
	dateTimeToJdn, dateTimeToMJD, dateTimeToJYear,
	bYearToDateTime, jdnToDateTime, mjdToDateTime, TTtoTAI, TAItoTT)
from gavo.utils import codetricks
from gavo.utils import ( #noflake: exported names
	dmsToDeg, hmsToDeg, DEG, parseISODT)
from gavo.utils import pgsphere #noflake: exported names


# degrees per mas
DEG_MAS = 1/3600000.
# degrees per arcsec
DEG_ARCSEC = 1/3600.


MS = base.makeStruct


class IgnoreThisRow(Exception):
	"""can be raised by user code to indicate that a row should be
	skipped when building a table.
	"""


def addCartesian(result, alpha, delta):
	"""inserts c_x, c_y, and c_z for the equatorial position alpha, delta
	into result.

	c_x, c_y, and c_z are the cartesian coordinates of the intersection
	point of the radius vector of alpha, delta with the unit sphere.

	alpha and delta already have to be floats, so you probably want
	to use variables here.

	>>> r = {}; addCartesian(r, 25, 30); str(r["c_x"]), str(r["c_y"])
	('0.784885567221', '0.365998150771')
	"""
	result["c_x"], result["c_y"], result["c_z"] = coords.computeUnitSphereCoords(
		alpha, delta)


def combinePMs(result, pma, pmd):
	"""inserts pm_total (in degs/yr) and pm_posang (in degs, east over north)
	into result.

	pma and pmd have to be in degs/yr, with cos(delta) applied to pma.
	"""
	if pma is None or pmd is None:
		tpm = pmpa = None
	else:
		tpm = math.sqrt(pma**2+pmd**2)
		pmpa = math.atan2(pma, pmd)*360/2/math.pi
	result["pm_total"] = tpm
	result["pm_posang"] = pmpa


@utils.document
def getQueryMeta():
	"""returns a query meta object from somewhere up the stack.

	This is for row makers running within a service.  This can be used
	to, e.g., enforce match limits by writing getQueryMeta()["dbLimit"].
	"""
	return codetricks.stealVar("queryMeta")

@utils.document
def parseTime(literal, format="%H:%M:%S"):
	"""returns a datetime.timedelta object for literal parsed according
	to format.

	For format, you can the magic values !!secondsSinceMidnight,
	!!decimalHours or a strptime-like spec using the H, M, and S codes.

	>>> parseTime("89930", "!!secondsSinceMidnight")
	datetime.timedelta(1, 3530)
	>>> parseTime("23.4", "!!decimalHours")
	datetime.timedelta(0, 84240)
	>>> parseTime("3.4:5", "%H.%M:%S")
	datetime.timedelta(0, 11045)
	>>> parseTime("20:04", "%H:%M")
	datetime.timedelta(0, 72240)
	"""
	if format=="!!secondsSinceMidnight":
		return datetime.timedelta(seconds=float(literal))
	elif format=="!!decimalHours":
		return datetime.timedelta(hours=float(literal))
	else:
		# We can't really use prebuilt strptimes since times like 25:21:22.445
		# are perfectly ok in astronomy.
		partDict = utils.parsePercentExpression(literal, format)
		return datetime.timedelta(0, hours=float(partDict.get("H", 0)),
			minutes=float(partDict.get("M", 0)), seconds=float(partDict.get("S", 0)))


@utils.document
def parseDate(literal, format="%Y-%m-%d"):
	"""returns a datetime.date object of literal parsed according to the
	strptime-similar format.

	The function understands the special dateFormat !!julianEp 
	(stuff like 1980.89).
	"""
	if format=="!!julianEp":
		return stc.jYearToDateTime(float(literal))
	return datetime.datetime(*time.strptime(literal, format)[:3])


@utils.document
def parseTimestamp(literal, format="%Y-%m-%dT%H:%M:%S"):
	"""returns a datetime.datetime object of literal parsed according to the
	strptime-similar format.
	"""
	return datetime.datetime(*time.strptime(literal, format)[:6])


@utils.document
def toMJD(literal):
	"""returns a modified julian date made from some datetime representation.

	Valid representations include:

	* MJD (a float smaller than 1e6)
	* JD (a float larger than 1e6)
	* datetime.datetime instances
	* ISO time strings.
	"""
	if literal is None:
		return None
	elif isinstance(literal, str):
		return stc.dateTimeToMJD(parseTimestamp(literal))
	elif isinstance(literal, datetime.datetime):
		return stc.dateTimeToMJD(literal)
	elif literal>1e6:
		return literal-stc.JD_MJD
	else:
		return literal


@utils.document
def makeTimestamp(date, time):
	"""makes a datetime instance from a date and a time.
	"""
	return datetime.datetime(date.year, date.month, date.day)+time


@utils.document
def parseAngle(literal, format, sepChar=None):
	"""converts the various forms angles might be encountered to degrees.

	format is one of hms, dms, fracHour.  For sexagesimal/time angles, 
	you can pass a sepChar (default: split at blanks) that lets you
	specify what separates hours/degrees, minutes, and seconds.

	>>> str(parseAngle("23 59 59.95", "hms"))
	'359.999791667'
	>>> "%10.5f"%parseAngle("-20:31:05.12", "dms", sepChar=":")
	' -20.51809'
	>>> "%010.6f"%parseAngle("21.0209556", "fracHour")
	'315.314334'
	"""
	if format=="dms":
		return utils.dmsToDeg(literal, sepChar=sepChar)
	elif format=="hms":
		return utils.hmsToDeg(literal, sepChar=sepChar)
	elif format=="fracHour":
		return utils.fracHoursToDeg(literal)
	else:
		raise base.Error("Invalid format: %s"%format)


@utils.document
def computeMean(val1, val2):
	"""returns the mean value between two values.

	Beware: Integer division done here for the benefit of datetime calculations.

	>>> computeMean(1.,3)
	2.0
	>>> computeMean(datetime.datetime(2000, 10, 13), 
	...   datetime.datetime(2000, 10, 12))
	datetime.datetime(2000, 10, 12, 12, 0)
	"""
	return val1+(val2-val1)/2


@utils.document
def killBlanks(literal):
	"""returns the string literal with all blanks removed.

	This is useful when numbers are formatted with blanks thrown in.

	Nones are passed through.
	"""
	if literal is None:
		return None
	else:
		return literal.replace(" ", "")


@utils.document
def lastSourceElements(path, numElements):
	"""returns a path made up from the last numElements items in path.
	"""
	newPath = []
	for i in range(int(numElements)):
		path, part = os.path.split(path)
		newPath.append(part)
	newPath.reverse()
	return os.path.join(*newPath)


@utils.document
def scale(val, factor, offset=0):
	"""returns val*factor+offset if val is not None, None otherwise.

	This is when you want to manipulate a numeric value that may be NULL.
	It is a somewhat safer alternative to using nullExcs with scaled values.
	"""
	if val is None:
		return None
	return factor*val+offset


@utils.document
def parseWithNull(literal, baseParser, nullLiteral=base.Undefined,
		default=None, checker=None):
	"""returns default if literal is nullLiteral, else baseParser(literal).

	If checker is non-None, it must be a callable returning True if its
	argument is a null value.
	"""
	if (nullLiteral is not base.Undefined and literal==nullLiteral
		) or literal is None:
		return default
	if checker is not None:
		if checker(literal):
			return default
	res = baseParser(literal)
	if res is None:
		return default
	return res


@utils.document
def getHTTPPar(inputData, parser, single=False, forceUnique=False):
	"""returns a parsed value from inputData.

	inputData may be

	* None -- the function will return None
	* an empty list -- the function will return None
	* a value other than a list -- as if it were a list of length 1
	* a list -- the function will return a list of parsed items

	This is of conveniently and robustly pulling out data from stuff coming
	out of inputKeys without multiplicity.

	If you pass single=True, you'll get exactly one value (or None).  The
	value will be the first one from a sequence.

	If you pass forceUnique=True, a ValueError will be raised if
	inputData is longer than one.
	"""
	if inputData is None:
		return None
	if not isinstance(inputData, list):
		inputData = [inputData]
	if len(inputData)==0:
		return None

	if forceUnique and len(inputData)>1:
		raise ValueError("Inputs for this parameter must not have more than"
			" one value; hovever, %s was passed in."%str(inputData))

	if single:
		return parser(inputData[0])
	else:
		return [parser(v) for v in inputData]


@utils.document
def requireValue(val, fieldName):
	"""returns val unless it is None, in which case a ValidationError
	for fieldName will be raised.
	"""
	if val is None:
		raise base.ValidationError("Value is required but was not provided", 
			fieldName)
	return val


@utils.document
def genLimitKeys(inputKey):
	"""yields _MAX and _MIN inputKeys from a single input key.

	This also tries to sensibly fix descriptions and ucds.
	This is mainly for datalink metaMakers; condDescs may use a 
	similar thing, but that's not exposed to RDs.
	"""
	name = inputKey.name
	ucd = inputKey.ucd or None
	description = inputKey.description

	yield inputKey.change(name=name+"_MIN", 
		ucd=ucd and "par.min;"+ucd,
		description=description.rstrip(".")+", lower limit")
	yield inputKey.change(name=name+"_MAX", 
		ucd=ucd and "par.max;"+ucd,
		description=description.rstrip(".")+", upper limit")


@utils.document
def getFlatName(accref):
	"""returns a unix-compatible file name for an access reference.

	The file name will not contain terrible characters, let alone
	slashes.  This is used to, e.g., keep all previews in one directory.
	"""
	# just in case someone passes in a full file path, strip it
	if accref.startswith("/"):
		accref = utils.getRelativePath(accref,
			base.getConfig("inputsDir"), liberalChars=True)

	return base64.b64encode(accref, "$!")


def addProcDefObject(name, func):
	globals()[name] = func


def makeProc(funcName, code, setupCode, parent, **moreNames):
	"""compiles a function in the rmkfunc's namespace.

	code is a complete function source.  setupCode is executed right away
	in this namespace to add globals.
	"""
	funcNs = globals().copy()
	funcNs["parent"] = parent
	funcNs.update(moreNames)
	if setupCode.strip():
		try:
			exec setupCode.rstrip() in funcNs
		except (SyntaxError, TypeError), ex:
			raise base.ui.logOldExc(
				base.BadCode(setupCode, "setup code", ex))
		except NameError, ex:
			raise base.ui.logOldExc(
				base.BadCode(setupCode, "setup code", ex, 
					hint="This typically happens when you forget to put"
					" quotes around string values."))
	return utils.compileFunction(code.rstrip(), funcName, funcNs, 
		debug=base.DEBUG)


def _test():
	import doctest, rmkfuncs
	doctest.testmod(rmkfuncs)


if __name__=="__main__":
	_test()
