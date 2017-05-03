"""
Some utility functions to deal with FITS files.

Note: pyfits is not thread-safe at least up to version 3.0.8.  We therefore
provide the fitsLock context manager here that you should use to protect
places where you use pyfits in a core (or a similar spot).
"""

#c Copyright 2008-2016, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


# I'm wasting a lot of effort on handling gzipped FITS files, which is
# something that's not terribly common in the end.  Maybe we should
# cut the crap and let people with gzipped FITSes do their stuff manually?


from __future__ import with_statement

import datetime
import gzip
import itertools
import os
import re
import tempfile
import threading
import warnings
from contextlib import contextmanager

from . import codetricks
from . import excs
from . import misctricks
from . import ostricks

# Make sure we get the numpy version of pyfits.  This is the master
# import that all others should use (from gavo.utils import pyfits).
# see also utils/__init__.py
os.environ["NUMERIX"] = "numpy"
try:
	import numpy
	import pyfits  # not "from gavo.utils" (this is the original)
except ImportError:  
	# pyfits is not installed; don't die, since the rest of gavo.utils
	# will still work.
	pyfits = misctricks.NotInstalledModuleStub( #noflake: exported name
		"pyfits and/or numpy")

else:
	# I need some parts of pyfits' internals, and it's version-dependent
	# where they are found
	def _TempHDU(*args):  #noflake: conditional definition
		raise excs.ReportableError("Incompatible pyfits version."
			"  Please complain to the maintainers.")

	if hasattr(pyfits, "core") and hasattr(pyfits.core, "_TempHDU"):
		_TempHDU = pyfits.core._TempHDU #noflake: conditional definition
	elif hasattr(pyfits, "_TempHDU"):
		_TempHDU = pyfits._TempHDU #noflake: conditional definition
	elif hasattr(pyfits.Header, "fromstring"):
		class _TempHDU(object): #noflake: conditional definition
			"""a wrapper around modern pyfits to provide some ancient whacko
			functionality."""
			def __init__(self):
				self._raw = ""

			def setupHDU(self):
				self.header = pyfits.Header.fromstring(self._raw)
				return self

	# various pyfits versions muck around with python's warnings system,
	# and they invariably get it wrong.  Take pyfits out of warnings
	# if that's necessary
	try:
		from pyfits import core as pyfitscore
		warnings.showwarning = pyfitscore.showwarning
		warnings.formatwarning = pyfitscore.formatwarning
	except (ImportError, AttributeError), ex:
		# let's hope we have a non-affected version
		pass


# We monkeypatch new versions of pyfits to support some old interfaces
# -- the removed deprecated interfaces too quickly, and we want to
# support pyfitses that don't have the new interfaces yet.  And then
# we monkeypatch some old versions to have newer, saner interfaces.

if not hasattr(pyfits.Header, "has_key"):
	def _header_has_key(self, key):
		return key in self
	pyfits.Header.has_key = _header_has_key
	del _header_has_key

if not hasattr(pyfits.Header, "ascardlist"):
	def _ascardlist(self):
		return self.cards
	pyfits.Header.ascardlist = _ascardlist
	del _ascardlist

if not hasattr(pyfits.Header, "append"):
	def _append(self, card, end=False):
		self.ascard.append(card, bottom=end)
	pyfits.Header.append = _append
	del _append

_FITS_TABLE_LOCK = threading.RLock()

@contextmanager
def fitsLock():
	_FITS_TABLE_LOCK.acquire()
	try:
		yield
	finally:
		_FITS_TABLE_LOCK.release()


CARD_SIZE = 80

END_CARD = 'END'+' '*(CARD_SIZE-3)

FITS_BLOCK_SIZE = CARD_SIZE*36


class FITSError(Exception):
	pass


# pyfits is a bit too liberal in throwing depreciation warnings.  Filter them
# for now TODO: Figure out a system to check them now and then
warnings.filterwarnings('ignore', category=DeprecationWarning)
try:
	warnings.filterwarnings('ignore', category=pyfits.PyfitsDeprecationWarning)
except AttributeError: # pyfits too old to produce these: Good.
	pass

def padCard(input, length=CARD_SIZE):
	"""pads input (a string) with blanks until len(result)%80=0

	The length keyword argument lets you adjust the "card size".  Use
	this to pad headers with length=FITS_BLOCK_SIZE

	>>> padCard("")
	''
	>>> len(padCard("end"))
	80
	>>> len(padCard("whacko"*20))
	160
	>>> len(padCard("junkodumnk"*17, 27))%27
	0
	"""
# This is like pyfits._pad, but I'd rather not depend on pyfits internals
# to much.
	l = len(input)
	if not l%length:
		return input
	return input+' '*(length-l%length)


def readHeaderBytes(f, maxHeaderBlocks=40):
	"""returns the bytes beloning to a FITS header starting at the current
	position within the file f.

	If the header is not complete after reading maxHeaderBlocks blocks,
	a FITSError is raised.
	"""
	parts = []

	while True:
		block = f.read(FITS_BLOCK_SIZE)
		if not block:
			raise EOFError('Premature end of file while reading header')

		parts.append(block)
		endCardPos = block.find(END_CARD)
		if not endCardPos%CARD_SIZE:
			break

		if len(parts)>=maxHeaderBlocks:
			raise FITSError("No end card found within %d blocks"%maxHeaderBlocks)
	return "".join(parts)


def readPrimaryHeaderQuick(f, maxHeaderBlocks=40):
	"""returns a pyfits header for the primary hdu of the opened file f.

	This is mostly code lifted from pyfits._File._readHDU.  The way
	that class is made, it's hard to use it with stuff from a gzipped
	source, and that's why this function is here.  It is used in the quick
	mode of fits grammars.

	This function is adapted from pyfits.
	"""
	hdu = _TempHDU()
	hdu._raw = readHeaderBytes(f, maxHeaderBlocks)
	hdu._extver = 1  # We only do PRIMARY

	hdu._new = 0
	hdu = hdu.setupHDU()
	return hdu.header


def parseCards(aString):
	"""returns a list of pyfits Cards parsed from aString.

	This will raise a ValueError if aString's length is not divisible by 80.  
	It may also raise pyfits errors for malformed cards.

	Empty (i.e., all-whitespace) cards are ignored.  If an END card is
	encountered processing is aborted.
	"""
	cards = []
	if len(aString)%CARD_SIZE:
		raise ValueError("parseCards argument has impossible length %s"%(
			len(aString)))
	for offset in range(0, len(aString), CARD_SIZE):
		rawCard = aString[offset:offset+CARD_SIZE]
		if rawCard==END_CARD:
			break
		if not rawCard.strip():
			continue
		cards.append(pyfits.Card().fromstring(rawCard))
	return cards
		

def serializeHeader(hdr):
	"""returns the FITS serialization of a FITS header hdr.
	"""
	parts = []
	for card in hdr.ascardlist():
		r = card.ascardimage('ignore')
		assert not len(r)%CARD_SIZE
		parts.append(r)
	serForm = "".join(parts)+padCard('END')
	return padCard(serForm, length=FITS_BLOCK_SIZE)


def replacePrimaryHeader(inputFile, newHeader, targetFile, bufSize=100000):
	"""writes a FITS to targetFile having newHeader as the primary header,
	where the rest of the data is taken from inputFile.

	inputFile must be a file freshly opened for reading, targetFile one 
	freshly opened for writing.

	This function is (among other things) a workaround for pyfits' misfeature of
	unscaling scaled data in images when extending a header.
	"""
	readPrimaryHeaderQuick(inputFile)
	targetFile.write(serializeHeader(newHeader))
	while True:
		buf = inputFile.read(bufSize)
		if not buf:
			break
		targetFile.write(buf)


def replacePrimaryHeaderInPlace(fitsName, newHeader):
	"""replaces the primary header of fitsName with newHeader.

	Doing this, it tries to minimize the amount of writing necessary; if
	fitsName has enough space for newHeader, just the header is written,
	and newHeader is extended if necessary.  Only if newHeader is longer than
	the existing header is fitsName actually copied.  We try to be safe in
	this case, only overwriting the old entry when the new data is safely
	on disk.

	gzipped inputs used to be supported here, but they aren't any more.
	"""
	if fitsName.endswith(".gz"):
		raise NotImplementedError("replacePrimaryHeaderInPlace no longer"
			" supports gzipped files.")

	serializedNew = serializeHeader(newHeader)
	with open(fitsName) as inputFile:
		serializedOld = readHeaderBytes(inputFile)
		inputFile.seek(0)
		
		if len(serializedNew)<len(serializedOld):
			# the new header is shorter than the old one; pad it with empty
			# cards, then make sure the end card is in the last block
			serializedNew = serializedNew+(
				len(serializedOld)-len(serializedNew))*" "
			serializedNew = serializedNew.replace(END_CARD, " "*len(END_CARD))
			serializedNew = serializedNew[:-len(END_CARD)]+END_CARD
			assert len(serializedNew)==len(serializedOld)

		if len(serializedNew)==len(serializedOld):
			# header lengths match (after possible padding); just write
			# the new header and be done
			with open(fitsName, "r+") as targetFile:
				targetFile.seek(0)
				targetFile.write(serializedNew)

		else:
			# New header is longer than the old one, write the whole mess.
			with ostricks.safeReplaced(fitsName) as targetFile:
				replacePrimaryHeader(inputFile, newHeader, targetFile)


# enforced sequence of well-known keywords, and whether they are mandatory
STANDARD_CARD_SEQUENCE = [
	("SIMPLE", True),
	("BITPIX", True),
	("NAXIS", True),
	("NAXIS1", False),
	("NAXIS2", False),
	("NAXIS3", False),
	("NAXIS4", False),
	("EXTEND", False),
	("BZERO", False),
	("BSCALE", False),
]

def _iterForcedPairs(seq):
	"""helps _enforceHeaderConstraints.
	"""
	if seq is None:
		return
	for item in seq:
		if isinstance(item, tuple):
			yield item
		else:
			yield (item, False)


def _enforceHeaderConstraints(cardList, cardSequence):
	"""returns a pyfits header containing the cards in cardList with FITS
	sequence constraints satisfied.

	This may raise a FITSError if mandatory cards are missing.

	This will only work correctly for image FITSes with less than five 
	dimensions.

	On cardSequence, see sortHeaders (except that this function always
	requries sequences of pairs).
	"""
# I can't use pyfits.verify for this since cardList may not refer to
# a data set that's actually in memory
	cardsAdded, newCards = set(), []
	cardDict = dict((card.key, card) for card in cardList)

	for kw, mandatory in itertools.chain(
			STANDARD_CARD_SEQUENCE,  _iterForcedPairs(cardSequence)):
		if isinstance(kw, pyfits.Card):
			newCards.append(kw)
			continue

		if kw in cardsAdded:
			continue

		try:
			newCards.append(cardDict[kw])
			cardsAdded.add(kw)
		except KeyError:
			if mandatory:
				raise FITSError("Mandatory card '%s' missing"%kw)

	for card in cardList:  # use cardList rather than cardDict to maintain
		                     # cardList order
		if card.key not in cardsAdded or card.key=='':
			newCards.append(card)
	return pyfits.Header(newCards)


def sortHeaders(header, commentFilter=None, historyFilter=None,
		cardSequence=None):
	"""returns a pyfits header with "real" cards first, then history, then
	comment cards.

	Blanks in the input are discarded, and one blank each is added in
	between the sections of real cards, history and comments.

	Header can be an iterable yielding Cards or a pyfits header.

	Duplicate history or comment entries will be swallowed.

	cardSequence, if present, is a sequence of (item, mandatory) pairs.
	There item can be a card name, in which case the corresponding
	card will be inserted at this point in the sequence.  If mandatory is
	True, a missing card is an error.  Keywords already in
	fitstools.STANDARD_CARD_SEQUENCE are ignored.

	Item can also a pyfits.Card instance; it will be put into the header
	as-is.

	As a shortcut, a sequence item may be something else then a tuple;
	it will then be combined with a False to make one.

	These days, if you think you need this, have a look at 
	fitstricks.makeHeaderFromTemplate first.
	"""
	commentCs, historyCs, realCs = [], [], []
	if hasattr(header, "ascardlist"):
		iterable = header.ascardlist()
	else:
		iterable = header
	for card in iterable:
		if card.key=="COMMENT":
			commentCs.append(card)
		elif card.key=="HISTORY":
			historyCs.append(card)
		else:
			realCs.append(card)

	newCards = []
	for card in realCs:
		newCards.append(card)
	
	historySeen = set()
	if historyCs:
		newCards.append(pyfits.Card(key=""))
	for card in historyCs:
		if historyFilter is None or historyFilter(card.value):
			if card.value not in historySeen:
				newCards.append(card)
				historySeen.add(card.value)

	commentsSeen = set()
	if commentCs:
		newCards.append(pyfits.Card(key=""))
	for card in commentCs:
		if commentFilter is None or commentFilter(card.value):
			if card.value not in commentsSeen:
				commentsSeen.add(card.value)
				newCards.append(card)

	return _enforceHeaderConstraints(newCards, cardSequence)


def openGz(fitsName, tempDir=None):
	"""returns the hdus for the gzipped fits fitsName.

	Scrap that as soon as we have gzipped fits support (i.e. newer pyfits)
	in debian.
	"""
	handle, pathname = tempfile.mkstemp(suffix="fits", dir=tempDir)
	f = os.fdopen(handle, "w")
	f.write(gzip.open(fitsName).read())
	f.close()
	hdus = pyfits.open(pathname)
	hdus.readall()
	os.unlink(pathname) 
	return hdus


def writeGz(hdus, fitsName, compressLevel=5, mode=0664):
	"""writes and gzips hdus into fitsName.  As a side effect, hdus will be 
	closed.

	Appearently, not even recent versions of pyfits support writing of
	zipped files (which is a bit tricky, admittedly).  So, we'll probably
	have to live with this kludge for a while.
	"""
	handle, pathname = tempfile.mkstemp(suffix="fits")
	with codetricks.silence():
		hdus.writeto(pathname, clobber=True)
	os.close(handle)
	rawFitsData = open(pathname).read()
	os.unlink(pathname)
	handle, pathname = tempfile.mkstemp(suffix="tmp", 
		dir=os.path.dirname(fitsName))
	os.close(handle)
	dest = gzip.open(pathname, "w", compressLevel)
	dest.write(rawFitsData)
	dest.close()
	os.rename(pathname, fitsName)
	os.chmod(fitsName, mode)


def openFits(fitsName):
		"""returns the hdus for fName.

		(gzip detection is tacky, and we should look at the magic).
		"""
		if os.path.splitext(fitsName)[1].lower()==".gz":
			return openGz(fitsName)
		else:
			return pyfits.open(fitsName)


class PlainHeaderManipulator:
	"""A class that allows header manipulation of fits files
	without having to touch the data.

	This class exists because pyfits insists on scaling scaled image data
	on reading it.  While we can scale back on writing, this is something
	I'd rather not do.  So, I have this base class to facilate the 
	HeaderManipulator that can handle gzipped fits files as well.
	"""
	def __init__(self, fName):
		self.hdus = pyfits.open(fName, "update")
		self.add_comment = self.hdus[0].header.add_comment
		self.add_history = self.hdus[0].header.add_history
		self.add_blank = self.hdus[0].header.add_blank
		self.update = self.hdus[0].header.update
	
	def updateFromList(self, kvcList):
		for key, value, comment in kvcList:
			self.hdus[0].header.update(key, value, comment=comment)

	def close(self):
		self.hdus.close()


class GzHeaderManipulator(PlainHeaderManipulator):
	"""is a class that allows header manipulation of fits files without
	having to touch the data even for gzipped files.

	See PlainHeaderManipulator.  We only provide a decoration here that
	transparently gzips and ungzips compressed fits files.
	"""
	def __init__(self, fName, compressLevel=5):
		self.origFile = fName
		handle, self.uncompressedName = tempfile.mkstemp(
			suffix="fits")
		destFile = os.fdopen(handle, "w")
		destFile.write(gzip.open(fName).read())
		destFile.close()
		self.compressLevel = compressLevel
		PlainHeaderManipulator.__init__(self, self.uncompressedName)
	
	def close(self):
		PlainHeaderManipulator.close(self)
		destFile = gzip.open(self.origFile, "w", compresslevel=self.compressLevel)
		destFile.write(open(self.uncompressedName).read())
		destFile.close()
		os.unlink(self.uncompressedName)


def HeaderManipulator(fName):
	"""returns a header manipulator for a FITS file.

	(it's supposed to look like a class, hence the uppercase name)
	It should automatically handle gzipped files.
	"""
	if fName.lower().endswith(".gz"):
		return GzHeaderManipulator(fName)
	else:
		return PlainHeaderManipulator(fName)


def getPrimarySize(fName):
	"""returns x and y size a fits image.
	"""
	hdr = readPrimaryHeaderQuick(open(fName))
	return hdr["NAXIS1"], hdr["NAXIS2"]


def getAxisLengths(hdr):
	"""returns a sequence of the lengths of the axes of a FITS image
	described by hdr.
	"""
	return [hdr["NAXIS%d"%i] for i in range(1, hdr["NAXIS"]+1)]


def cutoutFITS(hdu, *cuts):
	"""returns a cutout of hdu restricted to cuts.

	hdu is a primary FITS hdu.  cuts is a list of cut specs, each of which is
	a triple (axis, lower, upper).  axis is between 1 and naxis, lower and
	upper a 1-based pixel coordinates of the limits, and "border" pixels
	are included.  Specifications outside of the image are legal and will 
	be cropped back.  Open limits are supported via a specification of
	None.

	If an axis would vanish (i.e. length 0 or less), the function fudges
	things such that the axis gets a length of 1.

	axis is counted here in the FORTRAN/FITS sense, *not* in the C sense,
	i.e., axis=1 cuts along NAXIS1, which is the *last* index in a numpy
	array.

	WCS CRPIXes in hdu's header will be updated.  Axes and specified will
	not be touched.  It is an error to specifiy cuts for an axis twice 
	(behaviour is undefined).

	Note that this will lose all extensions the orginal FITS file might have
	had.
	"""
	cutDict = dict((c[0], c[1:]) for c in cuts)
	slices = []
	newHeader = hdu.header.copy()

	for index, length in enumerate(getAxisLengths(hdu.header)):
		firstPix, lastPix = cutDict.get(index+1, (None, None))

		if firstPix is None:
			firstPix = 1
		if lastPix is None:
			lastPix = length
		firstPix = min(max(1, firstPix), length)
		lastPix = min(length, max(1, lastPix))

		if (firstPix, lastPix)==(1, length):
			slices.append(slice(None, None, None))
		else:
			firstPix -= 1
			newAxisLength = lastPix-firstPix
			if newAxisLength==0:
				newAxisLength = 1
				lastPix = firstPix+1
			slices.append(slice(int(firstPix), int(lastPix), 1))

			newHeader["NAXIS%d"%(index+1)] = newAxisLength
			refpixKey = "CRPIX%d"%(index+1)
			newHeader.update(refpixKey, newHeader[refpixKey]-firstPix)

	slices.reverse()
	newHDU = pyfits.PrimaryHDU(data=hdu.data[tuple(slices)].copy(order='C'),
		header=newHeader)
	return newHDU


def shrinkWCSHeader(oldHeader, factor):
	"""returns a FITS header suitable for a shrunken version of the image
	described by oldHeader.

	This only works for 2d images, scale must be an integer>1.  The function
	assumes no "fractional" pixels are handled, i.e, remainders in divisions
	with factors are discarded.  It is thus a companion for
	iterScaledRows.

	Note that oldHeader must be an actual pyfits header instance; a dictionary
	will not do.

	This is a pretty straight port of wcstools's imutil.c#ShrinkFITSHeader,
	except we clear BZERO and BSCALE and set BITPIX to -32 (float array)
	under the assumption that in the returned image, 32-bit floats are used.
	"""
	assert oldHeader["NAXIS"]==2

	factor = int(factor)
	newHeader = oldHeader.copy()
	newHeader.update("SIMPLE", True,"GAVO DaCHS, %s"%datetime.datetime.utcnow())
	newHeader["NAXIS1"] = oldHeader["NAXIS1"]//factor
	newHeader["NAXIS2"] = oldHeader["NAXIS2"]//factor
	newHeader["BITPIX"] = -32

	try:
		ffac = float(factor)
		newHeader["CRPIX1"] = oldHeader["CRPIX1"]/ffac+0.5
		newHeader["CRPIX2"] = oldHeader["CRPIX2"]/ffac+0.5
		for key in ("CDELT1", "CDELT2",
				"CD1_1", "CD2_1", "CD1_2", "CD2_2"):
			if key in oldHeader:
				newHeader[key] = oldHeader[key]*ffac
	except KeyError: # no WCS, we're fine either way
		pass

	newHeader.update("IMSHRINK", "Image scaled down %s-fold by DaCHS"%factor)

	for hField in ["BZERO", "BSCALE"]:
		if newHeader.has_key(hField):
			del newHeader[hField]

	return newHeader


NUM_CODE = {
		8: 'uint8', 
		16: '>i2', 
		32: '>i4', 
		64: '>i8', 
		-32: '>f4', 
		-64: '>f8'}

def _makeDecoder(hdr):
	"""returns a decoder for the rows of FITS primary image data.

	The decoder is called with an open file and returns the next row.
	You need to keep track of the total number of rows yourself.
	"""
	numType = NUM_CODE[hdr["BITPIX"]]
	rowLength = hdr["NAXIS1"]

	bzero, bscale = hdr.get("BZERO", 0), hdr.get("BSCALE", 1)
	if bzero!=0 or bscale!=1:
		def read(f):
			return numpy.asarray(
				numpy.fromfile(f, numType, rowLength), 'float32')*bscale+bzero
	else:
		def read(f):  #noflake: conditional definition
			return numpy.fromfile(f, numType, rowLength)

	return read


def iterFITSRows(hdr, f):
	"""iterates over the rows of a FITS (primary) image.

	You pass in a FITS header and a file positioned to the start of
	the image data.

	What's returned are 1d numpy arrays of the datatype implied by bitpix.  The
	function understands only very basic FITSes (BSCALE and BZERO are known,
	though, and lead to floats arrays).

	We do this ourselves since pyfits may pull in the whole thing or at least
	mmaps it; both are not attractive when I want to stream-process large
	images.
	"""
	decoder = _makeDecoder(hdr)
	for col in xrange(hdr["NAXIS2"]):
		yield decoder(f)


def _iterSetupFast(inFile, hdr):
	"""helps iterScaledRows for the case of a simple, real-file FITS.
	"""
	if hdr is None:
		hdr = readPrimaryHeaderQuick(inFile)
	if hdr["NAXIS"]==0:
		# presumably a compressed FITS
		return _iterSetupCompatible(inFile, hdr)
	return hdr, iterFITSRows(hdr, inFile)


def _iterSetupCompatible(inFile, hdr, extInd=0):
	"""helps iterScaledRows for when _iterSetupFast will not work.

	Using extInd, you can select a different extension.  extInd=0 
	will automatically select extension 1 if that's a compressed image
	HDU.
	"""
	hdus = pyfits.open(inFile)
	if extInd==0 and len(hdus)>1 and isinstance(hdus[1], pyfits.CompImageHDU):
		extInd = 1
	
	def iterRows():
		for row in hdus[extInd].data[:,:]:
			yield row

	return hdus[extInd].header, iterRows()


def iterScaledRows(inFile, factor=None, destSize=None, hdr=None, slow=False,
		extInd=0):
	"""iterates over numpy arrays of pixel rows within the open FITS
	stream inFile scaled by it integer in factor.

	The arrays are always float32, regardless of the input.  When the
	image size is not a multiple of factor, border pixels are discarded.

	A FITS header for this data can be obtained using shrinkWCSHeader.

	You can pass in either a factor the file is to be scaled down, or
	an approximate size desired.  If both are given, factor takes precedence,
	if none is given, it's an error.

	If you pass in hdr, it will not be read from inFile; the function then
	expects the file pointer to point to the start of the first data block.
	Use this if you've already read the header of a non-seekable FITS.

	extInd lets you select a different extension.  extInd=0 means the first
	image HDU, which may be in extension 1 for compressed images.

	iterScaledRows will try to use a hand-hacked interface guaranteed to
	stream.  This only works for plain, 2D-FITSes from real files.
	iterScaledRows normally notices when it should fall back to
	pyfits code, but if it doesn't you can pass slow=True.
	"""
	if isinstance(inFile, file) and not slow and extInd==0:
		hdr, rows = _iterSetupFast(inFile, hdr)
	else:
		hdr, rows = _iterSetupCompatible(inFile, hdr, extInd)

	if factor is None:
		if destSize is None:
			raise excs.DataError("iterScaledRows needs either factor or destSize.")
		size = max(hdr["NAXIS1"], hdr["NAXIS2"])
		factor = max(1, size//destSize+1)

	factor = int(factor)
	assert factor>0

	rowLength = hdr["NAXIS1"]
	destRowLength = rowLength//factor
	summedInds = range(factor)

	for index in xrange(hdr["NAXIS2"]//factor):
		newRow = numpy.zeros((rowLength,), 'float32')
		for i in summedInds:
			try:
				newRow += rows.next()
			except StopIteration:
				break
		newRow /= factor

		# horizontal scaling via reshaping to a matrix and then summing over
		# its columns...
		newRow = newRow[:destRowLength*factor]
		yield sum(numpy.transpose(
			(newRow/factor).reshape((destRowLength, factor))))


def headerFromDict(d):
	"""returns a primary header sporting the key/value pairs given in the
	dictionary d.

	In all likelihood, this header will *not* work properly as a primary
	header because, e.g., there are certain rules on the sequence of
	header items.  fitstricks.copyFields can make a valid header out
	of what's returned here.

	keys mapped to None are skipped, i.e., you have to do nullvalue handling
	yourself.
	"""
	hdr = pyfits.PrimaryHDU().header
	for key, value in d.iteritems():
		if value is not None:
			hdr.update(key, value)
	return hdr


class WCSAxis(object):
	"""represents a single 1D WCS axis and allows easy metadata discovery.

	You'll usually use the fromHeader constructor.

	The idea of using this rather than pywcs or similar is that this is
	simple and robust.  It doesn't know many of the finer points of WCS,
	though, and in particular it's 1D only.

	However, for the purposes of cutouts it probably should do for the 
	overwhelming majority of non-spatial FITS axes.

	The default pixel coordinates are handled in the FITS sense here,
	i.e., the first pixel has the index 1.  Three are methods that have
	pix0 in their names; these assume 0-based arrays.  All the transforms
	return Nones unchanged.

	To retrieve the metadata shoved in, use the name, crval, crpix, cdelt,
	ctype, cunit, and axisLength attributes.
	"""
	def __init__(self, name, crval, crpix, cdelt,
			ctype="UNKNOWN", cunit="", axisLength=1):
		assert cdelt!=0
		self.crval, self.crpix, self.cdelt = crval, crpix, cdelt
		self.ctype, self.cunit, self.axisLength = ctype, cunit, axisLength
		self.name = name

	def pixToPhys(self, pixCoo):
		"""returns the physical value for a 1-based pixel coordinate.
		"""
		if pixCoo is None:
			return None
		return self.crval+(pixCoo-self.crpix)*self.cdelt

	def pix0ToPhys(self, pix0Coo):
		"""returns the physical value for a 0-based pixel coordinate.
		"""
		if pix0Coo is None:
			return None
		return self.pixToPhys(pix0Coo+1)
	
	def physToPix(self, physCoo):
		"""returns a 1-based pixel coordinate for a physical value.
		"""
		if physCoo is None:
			return None
		return (physCoo-self.crval)/self.cdelt+self.crpix
	
	def physToPix0(self, physCoo):
		"""returns a 0-based pixel coordinate for a physical value.
		"""
		if physCoo is None:
			return None
		return self.physToPix(physCoo)-1

	def getLimits(self):
		"""returns the minimal and maximal physical values this axis 
		takes within the image.
		"""
		limits = self.pixToPhys(1), self.pixToPhys(self.axisLength)
		return min(limits), max(limits)

	@classmethod
	def fromHeader(cls, header, axisIndex, forceSeparable=False):
		"""returns a WCSAxis for the specified axis in header.

		If the axis is mentioned in a transformation matrix (CD or PC),
		a ValueError is raised; this is strictly for 1D coordinates.

		The axisIndex is 1-based; to get a transform for the axis described
		by CTYPE1, pass 1 here.
		"""
		if ("CD%d_%d"%(axisIndex, axisIndex) in header
				or "PC%d_%d"%(axisIndex, axisIndex) in header):
			if not forceSeparable:
				raise ValueError("FITS axis %s appears not separable.  WCSAxis"
					" cannot handle this."%axisIndex)

		def get(key, default):
			return header.get("%s%d"%(key, axisIndex), default)
		
		guessedName = get("CNAME", "").strip()
		if not guessedName:
			guessedName = get("CTYPE", "").split("-", 1)[0].strip()
		if not guessedName or guessedName=="UNKNOWN":
			guessedName = "COO"

		guessedName = "%s_%d"%(guessedName, axisIndex)

		return cls(guessedName, 
			get("CRVAL", 0), get("CRPIX", 0), get("CDELT", 1),
			get("CTYPE", "UNKNOWN").strip(), 
			get("CUNIT", "").strip() or None, 
			get("NAXIS", 1))


class ESODescriptorsError(excs.SourceParseError):
	"""is raised when something goes wrong while parsing ESO descriptors.
	"""


def _makeNamed(name, re):
	return "(?P<%s>%s)"%(name, re)


class _ESODescriptorsParser(object):
	"""an ad-hoc parser for ESO's descriptors.

	These are sometimes in FITS files produced by MIDAS.  What I'm pretending
	to parse here is the contatenation of the cards' values without the
	boundaries.

	The parse is happening at construction time, after which you fetch the result
	in the result attribute.

	I'm adhoccing this.  If someone digs up the docs on what the actual
	grammar is, I'll do it properly.
	"""

	stringPat = "'[^']*'"
	intPat = r"-?\d+"
	floatPat = r"-?\d+\.\d+E[+-]\d+"
	white = r"\s+"
	nextToken = r"\s*"
	headerSep = nextToken+','+nextToken

	headerRE = re.compile(nextToken
		+_makeNamed("colName", stringPat)+headerSep
		+_makeNamed("typeCode", stringPat)+headerSep
		+_makeNamed("startInd", intPat)+headerSep
		+_makeNamed("endInd", intPat)+headerSep
		+stringPat+headerSep
		+stringPat+headerSep
		+stringPat)
	floatRE = re.compile(nextToken+floatPat)
	integerRE = re.compile(nextToken+intPat)

	def __init__(self, data):
		self.data, state = data, "header"
		self.result, self.curPos = {}, 0
		while state!="end":
			try:
				state = getattr(self, "_scan_"+state)()
			except Exception, msg:
				raise ESODescriptorsError(str(msg),
					location="character %s"%self.curPos,
					offending=repr(self.data[self.curPos:self.curPos+20]))

	@classmethod
	def fromFITSHeader(cls, hdr):
		"""returns a parser from the data in the pyfits hdr.
		"""
		descLines, collecting = [], False

		for card in hdr.ascardlist():
			if card.key=="HISTORY":
				if " ESO-DESCRIPTORS END" in card.value:
					collecting = False
				if collecting:
					descLines.append(card.value)
				if " ESO-DESCRIPTORS START" in card.value:
					collecting = True

		return cls("\n".join(descLines))

	def _scan_header(self):
		"""read the next descriptor header.
		"""
		mat = self.headerRE.match(self.data, self.curPos)
		if not mat:
			if not self.data[self.curPos:].strip():
				return "end"
			else:
				raise ValueError("Could not find next header")
		
		self.curPos = mat.end()
		self.curCol = []
		self.curColName = mat.group("colName")[1:-1]
		self.yetToRead = int(mat.group("endInd"))-int(mat.group("startInd"))+1

		if mat.group("typeCode")[1:-1].startswith("R"):
			return "float"
		elif mat.group("typeCode")[1:-1].startswith("I"):
			return "integer"
		else:
			raise ValueError("Unknown type code %s"%mat.group("typeCode"))

	def _scan_harvest(self):
		"""enter a parsed column into result and prepare for the next column.
		"""
		self.result[self.curColName] = self.curCol
		del self.curCol
		del self.curColName
		del self.yetToRead
		return "header"

	def _makeTypeScanner(typeName, literalRE, constructor):
		"""returns a scanner function (invisible to the outside.

		This is a helper method for building the parser class; typeName
		must be the same as the name in _scan_name.  constructor is
		a function that turns string literals into objects of the desired
		type.
		"""
		def scanner(self):
			mat = literalRE.match(self.data, self.curPos)
			if not mat:
				raise ValueError("Expected a %s here"%typeName)
			self.curPos = mat.end()

			self.curCol.append(constructor(mat.group()))
			self.yetToRead -= 1
			if self.yetToRead==0:
				return "harvest"
			else:
				return typeName

		return scanner

	_scan_float = _makeTypeScanner("float", floatRE, float)
	_scan_integer = _makeTypeScanner("integer", integerRE, int)
	
	del _makeTypeScanner


def parseESODescriptors(hdr):
	"""returns parsed ESO descriptors from a pyfits header hdr.

	ESO descriptors are data columns stuck into FITS history lines.
	They were produced by MIDAS.  This implementation was made
	without actual documentation, is largely based on conjecture,
	and is certainly incomplete.

	What's returned is a dictionary mapping column keywords to lists of
	column values.
	"""
	return _ESODescriptorsParser.fromFITSHeader(hdr).result


def _test():
	import doctest, fitstools
	doctest.testmod(fitstools)

if __name__=="__main__":
	_test()
