"""
Definition and conversion of units in STC

For every physical quantity we deal with, there is a standard unit defined:

	- angles: deg  (we way want to use rad here)
	- distances: m
	- time: s
	- frequencies: Hz
	- wavelength/energy: m

We keep dictionaries of conversion factors to those units.  Since turning
things around, these factors give "how many bases are in the unit", e.g.
km -> 1000.

The main interface are functions returning converter functions.  Pass
a value in fromUnit to them and receive a value in toUnit.  Simple factors
unfortunately don't cut it here since conversion from wavelength to
frequency needs division of the value.
"""

#c Copyright 2008-2016, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import itertools
import math

from gavo.utils import memoized
from gavo.stc import common


toRad=math.pi/180.
oneAU = 1.49597870691e11   # IAU
onePc = oneAU/2/math.tan(0.5/3600*toRad)
lightspeed = 2.99792458e8  # SI
planckConstant = 4.13566733e-15  # CODATA 2008, in eV s
julianYear = 365.25*24*3600

def makeConverterMaker(label, conversions):
	"""returns a conversion function that converts between any of the units
	mentioned in the dict conversions.
	"""
	def getConverter(fromUnit, toUnit, reverse=False):
		if fromUnit not in conversions or toUnit not in conversions:
			raise common.STCUnitError("One of '%s' or '%s' is no valid %s unit"%(
				fromUnit, toUnit, label))
		fact = conversions[fromUnit]/conversions[toUnit]
		if reverse:
			fact = 1/fact
		def convert(val):
			return fact*val
		return convert
	return getConverter


# Factors like "one kilometer is 1e3 meters"
distFactors = {
	"m": 1.,
	"km": 1e3,
	"mm": 1e-3,
	"AU": oneAU,  
	"pc": onePc,
	"kpc": (1e3*onePc),
	"Mpc": (1e6*onePc),
	"lyr": (lightspeed*julianYear),
}
getDistConv = makeConverterMaker("distance", distFactors)


angleFactors = {
	"deg": 1.,
	"rad": 1/toRad,
	"h": 360./24.,
	"arcmin": 1/60.,
	"arcsec": 1/3600.,
}
getAngleConv = makeConverterMaker("angle", angleFactors)


timeFactors = {
	"s": 1.,
	"h": 3600.,
	"d": (3600.*24),
	"a": julianYear,
	"yr": julianYear,
	"cy": (julianYear*100),
}
getTimeConv = makeConverterMaker("time", timeFactors)


# spectral units have the additional intricacy that a factor is not
# enough when wavelength needs to be converted to a frequency.
freqFactors = {
	"Hz": 1.,
	"kHz": 1e3,
	"MHz": 1e6,
	"GHz": 1e9,
	"eV": 1/planckConstant,
	"keV": 1/planckConstant*1e3,
	"MeV": 1/planckConstant*1e6,
	"GeV": 1/planckConstant*1e9,
	"TeV": 1/planckConstant*1e12,
}
getFreqConv = makeConverterMaker("frequency", freqFactors)

wlFactors = {
	"m": 1.,
	"mm": 1e-3,
	"um": 1e-6,
	"nm": 1e-9,
	"Angstrom": 1e-10,
}
getWlConv = makeConverterMaker("wavelength", wlFactors)

def getSpectralConv(fromUnit, toUnit, reverse=False):
	if fromUnit in wlFactors:
		if toUnit in wlFactors:
			conv = getWlConv(fromUnit, toUnit, reverse)
		else: # toUnit is freq
			fromFunc = getWlConv(fromUnit, "m")
			toFunc = getFreqConv("Hz", toUnit, reverse)
			def conv(val):
				return toFunc(lightspeed/fromFunc(val))
	else:  # fromUnit is freq
		if toUnit in freqFactors:
			conv = getFreqConv(fromUnit, toUnit, reverse)
		else:  # toUnit is wl
			fromFunc = getFreqConv(fromUnit, "Hz", reverse)
			toFunc = getWlConv("m", toUnit)
			def conv(val):
				return toFunc(lightspeed/fromFunc(val))
	return conv


distUnits = set(distFactors) 
angleUnits = set(angleFactors)
timeUnits = set(timeFactors)
spectralUnits = set(wlFactors) | set(freqFactors)

systems = [(distUnits, getDistConv), (angleUnits, getAngleConv),
	(timeUnits, getTimeConv), (spectralUnits, getSpectralConv)]


@memoized
def getBasicConverter(fromUnit, toUnit, reverse=False):
	"""returns a function converting fromUnit values to toUnit values.
	"""
	for units, factory in systems:
		if fromUnit in units and toUnit in units:
			return factory(fromUnit, toUnit, reverse)
	raise common.STCUnitError("No known conversion from '%s' to '%s'"%(
		fromUnit, toUnit))


# the maximal parallax distance as parallax.  This is used in the parallax
# converters to avoid divisions by zero.
maxDistance = 1e7


@memoized
def getParallaxConverter(fromUnit, toUnit, reverse=False):
	"""returns a function converting distances to/from parallaxes.
	"""
	if fromUnit not in angleUnits:
		fromUnit, toUnit, reverse = toUnit, fromUnit, not reverse
	if fromUnit not in angleUnits:
		raise common.STCUnitError("No spatial conversion between %s and %s"%(
			fromUnit, toUnit))
	# first convert angular unit to arcsec, then invert, yielding pc,
	# and convert that to distance unit
	angularConv = getBasicConverter(fromUnit, "arcsec", reverse)
	distanceConv = getBasicConverter("pc", toUnit, reverse)
	if reverse:
		def conv(val):  #noflake: local function
			res = distanceConv(val)
			if res>maxDistance:
				return 0.
			else:
				return angularConv(1./res)
	else:
		def conv(val):  #noflake: local function
			res = angularConv(val)
			if res<1/maxDistance:
				return distanceConv(maxDistance)
			else:
				return distanceConv(1./res)
	return conv


@memoized
def getRedshiftConverter(spaceUnit, timeUnit, toSpace, toTime,
		reverse=False):
	"""returns a function converting redshifts in spaceUnit/timeUnit to
	toSpace/toTime.

	This will actually work for any unit of the form unit1/unit2 as long 
	as unit2 is purely multiplicative.
	"""
	spaceFun = getBasicConverter(spaceUnit, toSpace, reverse)
	timeFun = getBasicConverter(timeUnit, toTime, not reverse)
	def convert(val):
		return spaceFun(timeFun(val))
	return convert


def _expandUnits(fromUnits, toUnits):
	"""makes sure fromUnits and toUnits have the same length.

	This is a helper for vector converters.
	"""
	if isinstance(toUnits, basestring):
		toUnits = (toUnits,)*len(fromUnits)
	if len(fromUnits)!=len(toUnits):
		raise common.STCUnitError(
			"Values in %s cannot be converted to values in %s"%(fromUnits, toUnits))
	return toUnits

@memoized
def getVectorConverter(fromUnits, toUnits, reverse=False):
	"""returns a function converting from fromUnits to toUnits.

	fromUnits is a tuple, toUnits is a tuple of which only the first item
	is interpreted.  This first item must be a tuple or a single string; in the
	latter case, all components are supposed to be of that unit.

	ToUnits may be shorter than fromUnits.  In this case, the additional 
	fromUnits are ignored.  This is mainly for cases in which geometries go
	with SPHER3 positions.

	The resulting functions accepts sequences of len(toUnits) and returns
	tuples of the same length.

	As a special service for Geometries, these spatial converters have 
	additional attributes fromUnit and toUnit giving what transformation
	they implement.
	"""
	if not fromUnits:  # no base unit given, we give up
		def convert(val): #noflake: local function
			return val
		return convert

	toUnits = _expandUnits(fromUnits, toUnits)
	convs = []
	convs.append(getBasicConverter(fromUnits[0], toUnits[0], reverse))
	if len(toUnits)>1:
		convs.append(getBasicConverter(fromUnits[1], toUnits[1], reverse))
	if len(toUnits)>2:
		try:
			convs.append(getBasicConverter(fromUnits[2], toUnits[2], reverse))
		except common.STCUnitError:  # try parallax for the last unit only
			convs.append(getParallaxConverter(fromUnits[2], toUnits[2], reverse))

	def convert(val): #noflake: local function
		if not hasattr(val, "__iter__"):
			# someone sneaked in a scalar.  Sigh
			val = (val,)
		return tuple(f(c) for f, c in itertools.izip(convs, val))
	if reverse:
		convert.fromUnit, convert.toUnit = toUnits, fromUnits
	else:
		convert.fromUnit, convert.toUnit = fromUnits, toUnits
	return convert


@memoized
def getVelocityConverter(fromSpaceUnits, fromTimeUnits, toSpace, toTime,
		reverse=False):
	"""returns a function converting from fromSpaceUnits/fromTimeUnits to
	toSpace/toTime.

	fromXUnits is a tuple, toX may either be a tuple of length fromXUnits or a a
	single string like in getVectorUnits.

	The resulting functions accepts sequences of proper length and returns
	tuples.
	"""
	toSpace = _expandUnits(fromSpaceUnits, toSpace)
	toTime = _expandUnits(fromTimeUnits, toTime)
	convs = tuple(getRedshiftConverter(fs, ft, ts, tt, reverse) 
		for fs, ft, ts, tt in itertools.izip(
			fromSpaceUnits, fromTimeUnits, toSpace, toTime))
	def convert(val):
		return tuple(f(c) for f, c in itertools.izip(convs, val))
	return convert


@memoized
def getUnitConverter(fromCoo, toCoo):
	"""returns a pair unit info and a conversion function to take fromCoo
	to the units of toCoo.

	toCoo may be None, in which case the unit of fromCoo is returned together
	with an identity function.  If the units already match, (None, None) is
	returned.

	The unit info is a dictionary suitable for change().
	"""
	if toCoo is None or toCoo.getUnitArgs() is None:
		return fromCoo.getUnitArgs(), None
	if fromCoo.getUnitArgs() is None:
		return toCoo.getUnitArgs(), None
	if fromCoo.getUnitArgs()==toCoo.getUnitArgs():
		return None, None
	return toCoo.getUnitArgs(), toCoo.getUnitConverter(
		fromCoo.getUnitArgs())


def iterUnitAdapted(baseSTC, sysSTC, attName, dependentName):
	"""iterates over all keys that need to be changed to adapt units in baseSTC's
	attName facet to conform to what sysSTC gives.

	If something in baseSTC is not specified in sysSTC, it is ignored here
	(i.e., it will remain unchanged if the result is used in a change).

	Since units are only on coordinates, and areas inherit these units,
	they are transformed as well, and their name is given by dependentName.
	See also conform.conformUnits.
	"""
	coo = getattr(baseSTC, attName)
	if coo is None:
		return
	overrides, conv = getUnitConverter(coo, getattr(sysSTC, attName))
	if conv is None:  # units are already ok
		return
	overrides.update(coo.iterTransformed(conv))
	yield attName, coo.change(**overrides)
	areas = getattr(baseSTC, dependentName)
	if areas:
		transformed = []
		for a in areas:
			transformed.append(a.adaptValuesWith(conv))
		yield dependentName, tuple(transformed)
