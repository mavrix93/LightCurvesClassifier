"""
Functions taking strings and returning python values.

All of them accept None and return None for Nullvalue processing.

All of them leave values alone if they already have the right type.

This is usually used in conjunction with 
base.typesystems.ToPythonCodeConverter.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import datetime
import re
import time

from gavo import utils
from gavo.stc import parseSimpleSTCS
from gavo.utils import pgsphere
from gavo.utils import identity #noflake: exported name

@utils.document
def parseInt(literal):
	"""returns an int from a literal, or None if literal is None or an empty
	string.

	>>> parseInt("32")
	32
	>>> parseInt("")
	>>> parseInt(None)
	"""
	if literal is None or (isinstance(literal, basestring
			) and not literal.strip()):
		return
	return int(literal)


_inf = float("Inf")
@utils.document
def parseFloat(literal):
	"""returns a float from a literal, or None if literal is None or an empty
	string.

	Temporarily, this includes a hack to work around a bug in psycopg2.

	>>> parseFloat("   5e9 ")
	5000000000.0
	>>> parseFloat(None)
	>>> parseFloat("  ")
	>>> parseFloat("wobbadobba")
	Traceback (most recent call last):
	ValueError: could not convert string to float: wobbadobba
	"""
	if (literal is None or 
			(isinstance(literal, basestring) and not literal.strip())):
		return None
	res = float(literal)
	# XXX TODO: NaN hack to work around psycopg2 serialization bug.  Fix there!
	if res!=res:
		return "NaN"
	if res==_inf:
		return "Inf"
	return res

_trueLiterals = set(["true", "yes", "t", "on", "enabled", "1"])
_falseLiterals = set(["false", "no", "f", "off", "disabled", "0"])

@utils.document
def parseBooleanLiteral(literal):
	"""returns a python boolean from some string.

	Boolean literals are strings like True, false, on, Off, yes, No in
	some capitalization.
	"""
	if literal is None or isinstance(literal, bool):
		return literal
	literal = literal.lower()
	if literal in _trueLiterals:
		return True
	elif literal in _falseLiterals:
		return False
	else:
		raise ValueError(
			"'%s' is no recognized boolean literal."%literal)


def parseUnicode(literal):
	if literal is None:
		return
	return unicode(literal)


def parseDefaultDate(literal):
	if literal is None or isinstance(literal, datetime.date):
		return literal
	return datetime.date(*time.strptime(literal, '%Y-%m-%d')[:3])


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
	return utils.parseISODT(literal)


def parseDefaultTime(literal):
	if literal is None or isinstance(literal, datetime.time):
		return literal
	return datetime.time(*time.strptime(literal, '%H:%M:%S')[3:6])


def parseCooPair(soup):
	"""returns a pair of RA, DEC floats if they can be made out in soup
	or raises a value error.

	No range checking is done (yet), i.e., as long as two numbers can be
	made out, the function is happy.

	>>> parseCooPair("23 12")
	(23.0, 12.0)
	>>> parseCooPair("23.5,-12.25")
	(23.5, -12.25)
	>>> parseCooPair("3.75 -12.125")
	(3.75, -12.125)
	>>> parseCooPair("3 25,-12 30")
	(51.25, -12.5)
	>>> map(str, parseCooPair("12 15 30.5 +52 18 27.5"))
	['183.877083333', '52.3076388889']
	>>> parseCooPair("3.39 -12 39")
	Traceback (most recent call last):
	ValueError: Invalid time with sepChar None: '3.39'
	>>> parseCooPair("12 15 30.5 +52 18 27.5e")
	Traceback (most recent call last):
	ValueError: 12 15 30.5 +52 18 27.5e has no discernible position in it
	>>> parseCooPair("QSO2230+44.3")
	Traceback (most recent call last):
	ValueError: QSO2230+44.3 has no discernible position in it
	"""
	soup = soup.strip()

	def parseFloatPair(soup):
		mat = re.match("(%s)\s*[\s,/]\s*(%s)$"%(utils.floatRE, 
			utils.floatRE), soup)
		if mat:
			return float(mat.group(1)), float(mat.group(2))

	def parseTimeangleDms(soup):
		timeangleRE = r"(?:\d+\s+)?(?:\d+\s+)?\d+(?:\.\d*)?"
		dmsRE = "[+-]?\s*(?:\d+\s+)?(?:\d+\s+)?\d+(?:\.\d*)?"
		mat = re.match("(%s)\s*[\s,/]?\s*(%s)$"%(timeangleRE, dmsRE), soup)
		if mat:
			try:
				return utils.hmsToDeg(mat.group(1)), utils.dmsToDeg(
					mat.group(2))
			except utils.Error, msg:
				raise utils.logOldExc(ValueError(str(msg)))

	for func in [parseFloatPair, parseTimeangleDms]:
		res = func(soup)
		if res:
			return res
	raise ValueError("%s has no discernible position in it"%soup)


def parseSPoint(soup):
	"""returns an SPoint for a coordinate pair.

	The coordinate pair can be formatted in a variety of ways; see parseCooPair.
	Input is always in degrees.
	"""
	if soup is None or isinstance(soup, pgsphere.SPoint):
		return soup
	return pgsphere.SPoint.fromDegrees(*parseCooPair(soup))


@utils.memoized
def getDefaultValueParsers():
	"""returns a dict containing all exported names from this module.

	This is useful with typesystems.ToPythonCodeConverter; see
	rscdef.column.Parameter for an example.

	This is always the same dict; thus, if you change it, copy it first.
	"""
	all = set(__all__)
	return dict((n,v) for n,v in globals().iteritems() if n in all)


def _test():
	import doctest, literals
	doctest.testmod(literals)


if __name__=="__main__":
	_test()


__all__ = ["parseInt", "parseFloat", "parseBooleanLiteral", "parseUnicode",
	"parseDefaultDate", "parseDefaultTime", "parseDefaultDatetime",
	"parseCooPair", "getDefaultValueParsers", "parseSPoint", "parseSimpleSTCS"]
