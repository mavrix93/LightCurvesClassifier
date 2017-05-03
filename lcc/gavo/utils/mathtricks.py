"""
Math-related helper functions.
"""

#c Copyright 2008-2016, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import math

from gavo.utils import codetricks

DEG = math.pi/180
ARCSEC = DEG/3600

def findMinimum(f, left, right, minInterval=3e-8):
	"""returns an estimate for the minimum of the single-argument function f 
	on (left,right).

	minInterval is a fourth of the smallest test interval considered.  

	For constant functions, a value close to left will be returned.

	This function should only be used on functions having exactly
	one minimum in the interval.
	"""
# replace this at some point by some better method (Num. Recip. in C, 394f)
# -- this is easy to fool and massively suboptimal.
	mid = (right+left)/2.
	offset = (right-left)/4.
	if offset<minInterval:
		return mid
	if f(left+offset)<=f(mid+offset):
		return findMinimum(f, left, mid, minInterval)
	else:
		return findMinimum(f, mid, right, minInterval)


class getHexToBin(codetricks.CachedResource):
	"""returns a dictionary mapping hex chars to their binary expansions.
	"""
	@classmethod
	def impl(cls):
		return dict(zip(
			"0123456789abcdef",
			["0000", "0001", "0010", "0011", "0100", "0101", "0110", "0111",
			 "1000", "1001", "1010", "1011", "1100", "1101", "1110", "1111",]))
		

def toBinary(anInt, desiredLength=None):
	"""returns anInt as a string with its binary digits, MSB first.

	If desiredLength is given and the binary expansion is shorter,
	the value will be padded with zeros.

	>>> toBinary(349)
	'101011101'
	>>> toBinary(349, 10)
	'0101011101'
	"""
	h2b = getHexToBin()
	res = "".join(h2b[c] for c in "%x"%anInt).lstrip("0")
	if desiredLength is not None:
		res = "0"*(desiredLength-len(res))+res
	return res


def _dotprod3(seq1, seq2, inds=(0,1,2)):
	return sum(seq1[i]*seq2[i] for i in inds)


class Matrix3(object):
	"""A quick and easy 3d matrix.

	This is just so we don't depend on numpy for trivial stuff.  The
	components are stored in a tuple of rows.
	"""
	indices = range(3)

	def __init__(self, row1, row2, row3):
		self.rows = (tuple(row1), tuple(row2), tuple(row3))

	def __eq__(self, other):
		return (isinstance(other, Matrix3)
			and self.rows==other.rows)
	
	def __ne__(self, other):
		return not self.__eq__(other)

	def vecMul(self, vec):
		"""returns the result of right-multiplying self to vec.

		The sequence vec is interpreted as a column vector.
		"""
		return tuple(_dotprod3(self.rows[i], vec) for i in self.indices)

	def matMul(self, mat):
		"""returns the result of multiplying mat to self from the right.
		"""
		cols = mat.getColumns()
		return self.__class__(*tuple(
				tuple(_dotprod3(row, col) for col in cols)
			for row in self.rows))
	
	def getColumns(self):
		"""returns the column vectors of this matrix in a 3-tuple.
		"""
		return tuple(
				tuple(self.rows[rowInd][colInd] for rowInd in self.indices)
			for colInd in self.indices)


def _normalize3(vec):
	len = math.sqrt(_dotprod3(vec, vec))
	return tuple(c/len for c in vec)


def getRotX(angle):
	"""returns a 3-rotation matrix for rotating angle radians around x.
	"""
	c, s = math.cos(angle), math.sin(angle)
	return Matrix3((1, 0, 0), (0, c, s), (0, -s, c))


def getRotZ(angle):
	"""returns a 3-rotation matrix for rotating angle radians around z.
	"""
	c, s = math.cos(angle), math.sin(angle)
	return Matrix3((c, s, 0), (-s, c, 0), (0, 0, 1))


def spherToCart(theta, phi):
	"""returns a 3-cartesian unit vector pointing to longitude theta,
	latitude phi.

	The angles are in rad.
	"""
	cp = math.cos(phi)
	return math.cos(theta)*cp, math.sin(theta)*cp, math.sin(phi)


def cartToSpher(unitvector):
	"""returns spherical coordinates for a 3-unit vector.

	We do not check if unitvector actually *is* a unit vector.  The returned
	angles are in rad.
	"""
	x, y, z = unitvector
	rInXY = math.sqrt(x**2+y**2)
	if abs(rInXY)<1e-9:  # pole
		theta = 0
	else:
		theta = math.atan2(y, x)
	if theta<0:
		theta += 2*math.pi
	phi = math.atan2(z, rInXY)
	return (theta, phi)


def spherDist(vec1, vec2):
	"""returns the spherical distance (in radian) between the unit vectors
	vec1 and vec2.
	"""
	return math.acos(_dotprod3(vec1, vec2))


def _test():
	import doctest, mathtricks
	doctest.testmod(mathtricks)


if __name__=="__main__":
	_test()
