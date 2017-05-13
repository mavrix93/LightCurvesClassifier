"""
Parsing various forms of tabular data embedded in VOTables.

WARNING: This will fail if the parser exposes namespaces in its
events (utils.iterparse doesn't).
"""

#c Copyright 2008-2016, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from gavo.votable import coding
from gavo.votable import common
from gavo.votable import dec_binary
from gavo.votable import dec_binary2
from gavo.votable import dec_tabledata


class DataIterator(object):
	"""A base for the classes actually doing the iteration.

	You need to give a decoderModule attribute and implement _getRawRow.
	"""
	def __init__(self, tableDefinition, nodeIterator):
		self.nodeIterator = nodeIterator
		self._decodeRawRow = coding.buildDecoder(
				tableDefinition,
				self.decoderModule)

	def __iter__(self):
		while True:
			rawRow = self._getRawRow()
			if rawRow is None:
				break
			yield self._decodeRawRow(rawRow)


class TableDataIterator(DataIterator):
	"""An internal class used by Rows to actually iterate over rows
	in TABLEDATA serialization.
	"""
	decoderModule = dec_tabledata

	def _getRawRow(self):
		"""returns a row in strings or None.
		"""
		# Wait for TR open
		for type, tag, payload in self.nodeIterator:
			if type=="end" and tag=="TABLEDATA":
				return None
			elif type=="start":
				if tag=="TR":
					break
				else:
					raise self.nodeIterator.getParseError(
						"Unexpected element %s"%tag)
			# ignore everything else; we're not validating, and sensible stuff
			# might yet follow (usually, it's whitespace data anyway)

		rawRow = []
		dataBuffer = []
		for type, tag, payload in self.nodeIterator:
			if type=="start":   # new TD
				dataBuffer = []
				if tag!="TD":
					raise self.nodeIterator.getParseError(
						"Unexpected element %s"%tag)

			elif type=="data":  # TD content
				dataBuffer.append(payload)

			elif type=="end":  # could be row end or cell end
				if tag=="TR":
					break
				elif tag=="TD":
					rawRow.append("".join(dataBuffer))
				else:
					assert False
				dataBuffer = []

			else:
				assert False
		return rawRow


class _StreamData(object):
	"""A stand-in for a file that decodes VOTable stream data on
	an as-needed basis.
	"""
	minChunk = 20000  # min length of encoded data decoded at a time
	lastRes = None    # last thing read (convenient for error msgs)

	def __init__(self, nodeIterator):
		self.nodeIterator = nodeIterator
		self.curChunk = "" # binary data already decoded
		self.leftover = "" # undecoded base64 data
		self.fPos = 0      # index of next char to be returned
		self._eof = False  # True when we've seen the </STREAM> event

	def _setEOF(self):
		"""cleans up at end of stream and sets eof flag.
		
		This is called by _fillBuffer exclusively.
		"""
		for evtype, element, payload in self.nodeIterator:
			if evtype!="data":
				break
		self._eof = True

	def _fillBuffer(self, nBytes):
		"""obtains events from node iterator fo fill curChunk.
		"""
		if self._eof:
			return
		destBytes = max(nBytes*2, self.minChunk)
		curBytes, hadLf = 0, False
		encoded = [self.leftover]

		for type, tag, payload in self.nodeIterator:
			if type=="end":   # must be </STREAM> or expat would've crapped.
				self._setEOF()
				break
			assert type=="data"
			encoded.append(payload)
			curBytes += len(payload)
			hadLf = hadLf or "\n" in payload or "\r" in payload
			if hadLf and curBytes>destBytes:
				break
		
		return self._decodeBase64("".join(encoded))

	def _decodeBase64(self, input):
		"""decodes input and sets curChunk, leftover, and fPos accordingly.

		The method behaves slightly differently when the _eof attribute is
		true -- normally, it will leave anything after the last line feed
		alone, but at _eof, it will decode even that.

		It is an error to pass in anything that has no line break unless
		at _eof.
		"""
		if not self._eof:  # put back anything after the last break mid-stream
			try:
				lastBreak = input.rindex("\n")+1
			except ValueError:
				lastBreak = input.rindex("\r")+1
			self.leftover = input[lastBreak:]
			input = input[:lastBreak]

		self.curChunk = self.curChunk[self.fPos:]+input.decode("base64")
		self.fPos = 0

	def read(self, nBytes):
		"""returns a string containing the next nBytes of the input
		stream.

		The function raises an IOError if there's not enough data left.
		"""
		if self.fPos+nBytes>len(self.curChunk):
			self._fillBuffer(nBytes)
		if self.fPos+nBytes>len(self.curChunk):
			raise IOError("No data left")
		self.lastRes = self.curChunk[self.fPos:self.fPos+nBytes]
		self.fPos += nBytes
		return self.lastRes
	
	def atEnd(self):
		return self._eof and self.fPos==len(self.curChunk)


class BinaryIteratorBase(DataIterator):
	"""A base class used by Rows to actually iterate over rows
	in BINARY(2) serialization.

	Since the VOTable binary serialization has no framing, we need to 
	present the data stream coming from the parser as a file to the decoder.  
	"""

	# I need to override __iter__ since we're not actually doing XML parsing
	# here; almost all of our work is done within the stream element.
	def __iter__(self):
		for type, tag, payload in self.nodeIterator:
			if type!="data":
				break
		if not (type=="start" 
				and tag=="STREAM"
				and payload.get("encoding")=="base64"):
			raise common.VOTableError("Can only read BINARY data from base64"
				" encoded streams")
		
		inF = _StreamData(self.nodeIterator)
		while not inF.atEnd():
			row = self._decodeRawRow(inF)
			if row is not None:
				yield row


class BinaryIterator(BinaryIteratorBase):
	decoderModule = dec_binary


class Binary2Iterator(BinaryIteratorBase):
	decoderModule = dec_binary2


def _makeTableIterator(elementName, tableDefinition, nodeIterator):
	"""returns an iterator for the rows contained within node.
	"""
	if elementName=='TABLEDATA':
		return iter(TableDataIterator(tableDefinition, nodeIterator))
	elif elementName=='BINARY':
		return iter(BinaryIterator(tableDefinition, nodeIterator))
	elif elementName=='BINARY2':
		return iter(Binary2Iterator(tableDefinition, nodeIterator))

	else:
		raise common.VOTableError("Unknown table serialization: %s"%
			elementName, hint="We only support TABLEDATA, BINARY2,"
				" and BINARY coding")


class Rows(object):
	"""a wrapper for data within a VOTable.

	Tabledatas are constructed with a model.VOTable.TABLE instance and
	the iterator maintained by parser.parse.  They yield individual
	table lines.

	In reality, __iter__ just dispatches to the various deserializers.
	"""
	def __init__(self, tableDefinition, nodeIterator):
		self.tableDefinition, self.nodeIterator = tableDefinition, nodeIterator
	
	def __iter__(self):
		for type, tag, payload in self.nodeIterator:
			if type=="data": # ignore whitespace (or other stuff...)
				pass
			elif tag=="INFO":
				pass   # XXX TODO: What do we do with those INFOs?
			else:
				return _makeTableIterator(tag, 
					self.tableDefinition, self.nodeIterator)
