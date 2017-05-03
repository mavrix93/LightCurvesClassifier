"""
Coordinate systems for positions on earth.
"""

#c Copyright 2008-2016, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import math

from gavo.utils import DEG


class WGS84(object):
	"""the WGS84 reference system.
	"""
	a = 6378137.
	f = 1/298.257223563
	GM = 3.986005e14    # m3s-1
	J2 = 0.00108263
	omega = 7.292115e-5 # rad s-1


def _getC_S(phi, refSys):
	"""returns the values of the auxiliary functions C and S.

	phi must be in rad.

	See Astron. Almanac, Appendix K.
	"""
	B = (1-refSys.f)**2
	C = 1/math.sqrt(
		math.cos(phi)**2
		+B*math.sin(phi)**2)
	S = C*B
	return C, S


def geocToGeod(long, phip, rho=1, refSys=WGS84):
	"""returns geodetic coordinates long, phi for geocentric coordinates.

	refSys defaults is the reference system the geodetic coordinates are
	expressed in.

	This will not work at the poles -- patches welcome.

	See Astron. Almanac, Appendix K; we go for the iterative solution
	discussed there.
	"""
	long, phip = long*DEG, phip*DEG
	x = refSys.a*rho*math.cos(phip)*math.cos(long)
	y = refSys.a*rho*math.cos(phip)*math.sin(long)
	z = refSys.a*rho*math.sin(phip)

	e2 = 2*refSys.f-refSys.f**2
	r = math.sqrt(x**2+y**2)
	phi = math.atan2(z, r)

	while True:
		phi1 = phi
		C = 1/math.sqrt((1-e2*math.sin(phi1)**2))
		phi = math.atan2(z+refSys.a*C*e2*math.sin(phi1), r)
		if abs(phi1-phi)<1e-14: # phi is always of order 1
			break
	return long/DEG, phi/DEG, r/math.cos(phi)-refSys.a*C


def geodToGeoc(long, phi, height, refSys=WGS84):
	"""returns geocentric coordinates lambda, phi', rho for geodetic coordinates.

	refSys defaults is the reference system the geodetic coordinates are
	expressed in.

	height is in meter, long, phi in degrees.

	See Astron. Almanac, Appendix K.
	"""
	long, phi = long*DEG, phi*DEG
	C, S = _getC_S(phi, refSys)
	rcp = (C+height/refSys.a)*math.cos(phi)
	rsp = (S+height/refSys.a)*math.sin(phi)
	rho = math.sqrt(rcp**2+rsp**2)
	phip = math.atan2(rsp, rcp)
	return long/DEG, phip/DEG, rho
