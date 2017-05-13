"""
Some miscellaneous helpers for making images and such.

As this may turn into a fairly expensive import, this should *not* be imported
by utils.__init__.   Hence, none of these functions are in gavo.api or
gavo.utils.
"""

#c Copyright 2008-2016, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from cStringIO import StringIO

import Image
import numpy


def _normalizeForImage(pixels, gamma):
	"""helps jpegFromNumpyArray and friends.
	"""
	pixels = numpy.flipud(pixels)
	pixMax, pixMin = numpy.max(pixels), numpy.min(pixels)
	return numpy.asarray(numpy.power(
		(pixels-pixMin)/(pixMax-pixMin), gamma)*255, 'uint8')


def jpegFromNumpyArray(pixels, gamma=0.25):
	"""returns a normalized JPEG for numpy pixels.

	pixels is assumed to come from FITS arrays, which are flipped wrt to
	jpeg coordinates, which is why we're flipping here.

	The normalized intensities are scaled by v^gamma; we believe the default
	helps with many astronomical images 
	"""
	f = StringIO()
	Image.fromarray(_normalizeForImage(pixels, gamma)
		).save(f, format="jpeg")
	return f.getvalue()


def colorJpegFromNumpyArrays(rPix, gPix, bPix, gamma=0.25):
	"""as jpegFromNumpyArray, except a color jpeg is built from red, green,
	and blue pixels.
	"""
	pixels = numpy.array([
		_normalizeForImage(rPix, gamma),
		_normalizeForImage(gPix, gamma),
		_normalizeForImage(bPix, gamma)]).transpose(1,2,0)

	f = StringIO()
	Image.fromarray(pixels, mode="RGB").save(f, format="jpeg")
	return f.getvalue()


def scaleNumpyArray(arr, destSize):
	"""returns the numpy array arr scaled down to approximately destSize.
	"""
	origWidth, origHeight = arr.shape
	size = max(origWidth, origHeight)
	scale = max(1, size//destSize+1)
	destWidth, destHeight = origWidth//scale, origHeight//scale

	# There's very similar code in fitstools.iterScaledRows
	# -- it would be nice to refactor things so this can be shared.
	img = numpy.zeros((destWidth, destHeight), 'float32')

	for rowInd in range(destHeight):
		wideRow = (numpy.sum(
			arr[:,rowInd*scale:(rowInd+1)*scale], 1, 'float32'
			)/scale)[:destWidth*scale]
		# horizontal scaling via reshaping to a matrix and then summing over
		# its columns.
		newRow = numpy.sum(
			numpy.transpose(wideRow.reshape((destWidth, scale))), 0)/scale
		img[:,rowInd] = newRow

	return img
