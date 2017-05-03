"""
Writing data in FITS binary tables
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from __future__ import with_statement

import os
import tempfile
import threading
import time
from contextlib import contextmanager

import numpy

from gavo import base
from gavo import rsc
from gavo import utils
from gavo.formats import common
from gavo.utils import pyfits


# pyfits obviously is not thread-safe.  We put a lock around table generation
# and hope we'll be fine.
_FITS_TABLE_LOCK = threading.Lock()

@contextmanager
def exclusiveFits():
	_FITS_TABLE_LOCK.acquire()
	try:
		yield
	finally:
		_FITS_TABLE_LOCK.release()


_fitsCodeMap = {
	"short": "I",
	"int": "J",
	"long": "K",
	"float": "E",
	"double": "D",
	"boolean": "L",
	"char": "A",
	"unicodeChar": "A",
}

_typeConstructors = {
	"short": int,
	"int": int,
	"long": int,
	"float": float,
	"double": float,
	"boolean": int,
	"char": str,
	"unicodeChar": str,
}


def _makeStringArray(values, colInd, colDesc):
	"""returns a pyfits-capable column array for strings stored in the colInd-th
	column of values.
	"""
	try:
		arr = numpy.array([str(v[colInd]) for v in values], dtype=numpy.str)
	except UnicodeEncodeError:

		def _(s):
			if s is None:
				return None
			else:
				return s.encode("utf-8")

		arr = numpy.array([_(v[colInd]) for v in values], dtype=numpy.str)
	return "%dA"%arr.itemsize, arr


def _getNullValue(colDesc):
	"""returns a null value we consider ok for a column described by colDesc.

	This is supposed to be in the column data type.
	"""
	nullValue = colDesc["nullvalue"]
	if nullValue is None:
		# enter some reasonable defaults
		if (colDesc["datatype"]=="float"
			or colDesc["datatype"]=="double"):
			nullValue = float("NaN")
		elif colDesc["datatype"]=="text":
			nullValue = ""
	else:
		nullValue = _typeConstructors[colDesc["datatype"]](nullValue)
	
	return nullValue


def _makeValueArray(values, colInd, colDesc):
	"""returns a pyfits-capable column array for non-string values
	stored in the colInd-th column of values.
	"""
	nullValue = _getNullValue(colDesc)

	def mkval(v):
		if v is None:
			if nullValue is None:
				raise ValueError("While serializing a FITS table: NULL"
					" detected in column '%s' but no null value declared"%
					colDesc["name"])
			return nullValue
		else:
			return v

	arr = numpy.array([mkval(v[colInd]) for v in values])
	typecode = _fitsCodeMap[colDesc["datatype"]]
	return typecode, arr


def _makeExtension(serMan):
	"""returns a pyfits hdu for the valuemappers.SerManager instance table.
	"""
	values = list(serMan.getMappedTuples())
	columns = []
	utypes = []

	for colInd, colDesc in enumerate(serMan):
		if colDesc["datatype"]=="char" or colDesc["datatype"]=="unicodeChar":
			makeArray = _makeStringArray
		else:
			makeArray = _makeValueArray
		
		typecode, arr = makeArray(values, colInd, colDesc)
		if typecode in 'ED':
			nullValue = None  # (NaN implied)
		else:
			nullValue = _getNullValue(colDesc)

		columns.append(pyfits.Column(name=str(colDesc["name"]), 
			unit=str(colDesc["unit"]), format=typecode, 
			null=nullValue, array=arr))
		if colDesc["utype"]:
			utypes.append((colInd, str(colDesc["utype"].lower())))

	hdu = pyfits.new_table(pyfits.ColDefs(columns))
	for colInd, utype in utypes:
		hdu.header.update("TUTYP%d"%(colInd+1), utype)

	if not hasattr(serMan.table, "IgnoreTableParams"):
		for param in serMan.table.iterParams():
			if param.value is None:
				continue
		
			key, value, comment = str(param.name), param.value, param.description
			if isinstance(value, unicode):
				value = value.encode('ascii', "xmlcharrefreplace")
			if isinstance(comment, unicode):
				comment = comment.encode('ascii', "xmlcharrefreplace")
			if len(key)>8:
				key = "hierarch "+key

			try:
				hdu.header.update(key=key, value=value, comment=comment)
			except ValueError, ex:
				# do not fail just because some header couldn't be serialised
				base.ui.notifyWarning(
					"Failed to serialise param %s to a FITS header (%s)"%(
						param.name,
						utils.safe_str(ex)))

	return hdu
	

def _makeFITSTableNOLOCK(dataSet, acquireSamples=True):
	"""returns a hdulist containing extensions for the tables in dataSet.

	You must make sure that this function is only executed once
	since pyfits is not thread-safe.
	"""
	tables = [base.SerManager(table, acquireSamples=acquireSamples) 
		for table in dataSet.tables.values()]
	extensions = [_makeExtension(table) for table in tables]
	primary = pyfits.PrimaryHDU()
	primary.header.update("DATE", time.strftime("%Y-%m-%d"), 
		"Date file was written")
	return pyfits.HDUList([primary]+extensions)


def makeFITSTable(dataSet, acquireSamples=False):
	"""returns a hdulist containing extensions for the tables in dataSet.

	This function may block basically forever.  Never call this from
	the main server, always use threads or separate processes (until
	pyfits is fixed to be thread-safe).

	This will add table parameters as header cards on the resulting FITS
	header.
	"""
	with exclusiveFits():
		return _makeFITSTableNOLOCK(dataSet, acquireSamples)


def writeFITSTableFile(hdulist):
	"""returns the name of a temporary file containing the FITS data for
	hdulist.
	"""
	handle, pathname = tempfile.mkstemp(".fits", dir=base.getConfig("tempDir"))

	# if there's more than the primary HDU, EXTEND=True is mandatory; let's
	# be defensive here
	if len(hdulist)>1:
		hdulist[0].header.update("EXTEND", True, "More exts following")

	with utils.silence():
		hdulist.writeto(pathname, clobber=1)
	os.close(handle)
	return pathname


def makeFITSTableFile(dataSet, acquireSamples=True):
	"""returns the name of a temporary file containing a fits file
	representing dataSet.

	The caller is responsible to remove the file.
	"""
	hdulist = makeFITSTable(dataSet, acquireSamples)
	return writeFITSTableFile(hdulist)


def writeDataAsFITS(data, outputFile, acquireSamples=False):
	"""a formats.common compliant data writer.

	This will write out table params as header cards.  To serialise
	those yourself (as is required for spectral data model compliant
	tables), set an attribute IgnoreTableParams (with an arbitrary
	value) on the table.
	"""
	data = rsc.wrapTable(data)
	fitsName = makeFITSTableFile(data, acquireSamples)
	try:
		src = open(fitsName)
		utils.cat(src, outputFile)
		src.close()
	finally:
		os.unlink(fitsName)

common.registerDataWriter("fits", writeDataAsFITS, "application/fits",
	"FITS Binary Table")
