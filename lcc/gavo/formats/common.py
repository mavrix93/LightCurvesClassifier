"""
Common code for generation of various data formats.

The main function here is formatData.  It receives a string format id,
a data instance and a destination file.  It dispatches this to formatters 
previously registred using registerDataWriter.

The data writers must take a data instance and a file instance; their
effect must be that a serialized representation of data, or, if the format
does not support this, the data's primary table is written to the file 
instance.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.

import cgi
from cStringIO import StringIO

from gavo import base


PRESERVED_MIMES = set([ # TAP Spec, 2.7.1, similar in DALI
	"text/xml", "application/x-votable+xml", "text/plain"])


_formatDataRegistry = {}
_formatsMIMERegistry = {}


class CannotSerializeIn(base.Error):
	def __init__(self, format):
		self.format = format
		base.Error.__init__(self, format,
			hint="Either you gave an invalid format id or a known format"
			" did not get registred for some reason.  Format codes"
			" known at this point: %s.  You can also try common MIME types"%(
				", ".join(FORMATS_REGISTRY.writerRegistry)))
		self.args = [format]
	
	def __str__(self):
		return "Cannot serialize in '%s'."%self.format


def getMIMEKey(contentType):
	"""makes a DaCHS mime key from a content-type string.

	This is used for retrieving matching mime types and is a triple
	of major and minor mime type and a set of parameter pairs.

	contentType is a string-serialized mime type.
	"""
	media_type, paramdict = cgi.parse_header(contentType)
	try:
		major, minor = media_type.split("/")
	except (ValueError, TypeError):
		raise CannotSerializeIn(contentType)
	return (major, minor, 
			frozenset(paramdict.iteritems()))


class FORMATS_REGISTRY(object):
	"""a registry for data formats that can be produced by DaCHS.

	This works by self-registration of the respective modules on their
	input; hence, if you want to rely on some entry here, be sure
	there's an import somewhere.
	"""
	# format key -> writer function
	writerRegistry = {}
	# format key -> mime type
	formatToMIME = {}
	# format key -> human-readable label
	formatToLabel = {}
	# (major, minor, param pair set) -> format key
	mimeToKey = {}

	@classmethod
	def registerDataWriter(cls, key, writer, mainMime, label, *aliases):
		cls.writerRegistry[key] = writer
		cls.formatToMIME[key] = mainMime
		cls.formatToLabel[key] = label

		cls.mimeToKey[getMIMEKey(mainMime)] = key
		for mime in aliases:
			cls.mimeToKey[getMIMEKey(mime)] = key

	@classmethod
	def getMIMEFor(cls, formatName, orderedFormat=None):
		"""returns a simple MIME type for our formatName (some incoming MIME 
		or an alias).

		Some magic, reserved mimes that need to be preserved from
		the input are recognised and returned in orderedFormat.  This
		is for TAP and related DALI hacks.
		"""
		if orderedFormat in PRESERVED_MIMES:
			return orderedFormat

		if formatName in cls.formatToMIME:
			return cls.formatToMIME[formatName]

		# if it looks like a mime type, return it, otherwise assume it's
		# an unimported format and return a generic mime
		if "/" in formatName:
			return formatName
		else:
			return "application/octet-stream"

	@classmethod
	def getWriterFor(cls, formatName):
		"""returns a writer for formatName.

		writers are what's registred via registerDataWriter; formatName is
		a MIME type or a format alias.  This raises CannotSerializeIn
		if no writer is available.
		"""
		return cls.writerRegistry[cls.getKeyFor(formatName)]

	@classmethod
	def getLabelFor(cls, formatName):
		"""returns a label for formatName (DaCHS key or MIME type).
		"""
		return cls.formatToLabel[cls.getKeyFor(formatName)]

	@classmethod
	def getKeyFor(cls, formatName):
		"""returns a DaCHS format key for formatName (DaCHS key or MIME).

		If formatName is a mime type with parameters, we'll also try
		to get a format with the parameters stripped and silently succeed
		if that works.
		"""
		if formatName in cls.writerRegistry:
			return formatName

		parsed = getMIMEKey(formatName)
		if parsed in cls.mimeToKey:
			return cls.mimeToKey[parsed]
		parsed = (parsed[0], parsed[1], frozenset())
		if parsed in cls.mimeToKey:
			return cls.mimeToKey[parsed]

		raise CannotSerializeIn(formatName)

	@classmethod
	def iterFormats(cls):
		"""iterates over the short names of the available formats.
		"""
		return iter(cls.writerRegistry)


registerDataWriter = FORMATS_REGISTRY.registerDataWriter
getMIMEFor = FORMATS_REGISTRY.getMIMEFor
getWriterFor = FORMATS_REGISTRY.getWriterFor
getLabelFor = FORMATS_REGISTRY.getLabelFor
iterFormats = FORMATS_REGISTRY.iterFormats


def formatData(formatName, table, outputFile, acquireSamples=True):
	"""writes a table to outputFile in the format given by key.

	Table may be a table or a Data instance.   formatName is a format shortcut
	or a MIME type.

	This raises a CannotSerializeIn exception if formatName is not recognized.
	"""
	getWriterFor(formatName)(table, outputFile, acquireSamples=acquireSamples)


def getFormatted(formatName, table, acquireSamples=False):
	"""returns a string containing a representation of table in the
	format given by formatName.

	This is just wrapping formatData; it might use large amounts of memory
	for large data.
	"""
	buffer = StringIO()
	formatData(formatName, table, buffer, acquireSamples)
	return buffer.getvalue()
