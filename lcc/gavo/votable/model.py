"""
xmlstan elements of VOTable.
"""

#c Copyright 2008-2016, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from gavo import utils
from gavo.utils import ElementTree
from gavo.utils.stanxml import (
	Element, registerPrefix, getPrefixInfo, schemaURL, escapePCDATA)


NAMESPACES = {
	"1.3": "http://www.ivoa.net/xml/VOTable/v1.3",
	"1.2": "http://www.ivoa.net/xml/VOTable/v1.2",
	"1.1": "http://www.ivoa.net/xml/VOTable/v1.1",
}

# WARNING: if you change the default version of the VOTables generated,
# you'll probably have to adapt them in resources/xsl, too.
registerPrefix("vot", NAMESPACES["1.3"], schemaURL("VOTable-1.3.xsd"))
registerPrefix("vot2", NAMESPACES["1.2"], schemaURL("VOTable-1.2.xsd"))
registerPrefix("vot1", NAMESPACES["1.1"], schemaURL("VOTable-1.1.xsd"))
	

class VOTable(object):
	"""The container for VOTable elements.
	"""
	class _VOTElement(Element):
		_prefix = "vot"
		_local = True

	class _DescribedElement(_VOTElement):
		_a_ID = None
		_a_ref = None
		_a_name = None
		_a_ucd = None
		_a_utype = None
		_mayBeEmpty = True

		def getDesignation(self):
			"""returns some name-like thing for a FIELD or PARAM.
			"""
			if self.name:
				res = self.name
			elif self.ID:
				res = self.ID
			else:
				res = "%s_%s"%(self.__class__.__name__, "%x"%id(self))
			return res.encode("ascii", "ignore")

		def getDescription(self):
			"""returns the description for this element, or an empty string.
			"""
			try:
				return self.iterChildrenOfType(VOTable.DESCRIPTION).next().text_
			except StopIteration:
				return ""


	class _ValuedElement(_DescribedElement):
		_a_unit = None
		_a_xtype = None

	class _TypedElement(_ValuedElement):
		_a_ref = None
		_a_arraysize = None
		_a_datatype = None
		_a_precision = None
		_a_ref = None
		_a_type = None
		_a_width = None
		_a_format = None

		def isScalar(self):
			return self.arraysize is None or self.arraysize=='1'

		def isMultiDim(self):
			return self.arraysize is not None and "x" in self.arraysize

		def hasVarLength(self):
			return self.arraysize and self.arraysize.endswith("*")

		def getLength(self):
			"""returns the number of items one should expect in value, or
			None for variable-length arrays.
			"""
			if self.arraysize is None:
				return 1
			if self.arraysize.endswith("*"):
				return None
			elif self.isMultiDim():
				return reduce(lambda a, b: a*b, map(int, self.arraysize.split("x")))
			else:
				return int(self.arraysize)

		def getShape(self):
			"""returns a numpy-compatible shape.
			"""
			if self.arraysize is None:
				return None

			if self.datatype=="char" and not "x" in self.arraysize:
				# special case: 1d char arrays are just scalar strings
				return None

			if self.arraysize=="*":
				return None  # What should we really return here?

			val = self.arraysize.replace("*", "")
			if "x" in val:
				if val.endswith("x"):  # variable last dimension
					val = val+'1'
				return tuple(int(d) for d in val.split("x"))

			else:
				return (int(val),)

		def _setNULLValue(self, val):
			"""sets the null literal of self to val.
			"""
			valEls = list(self.iterChildrenWithName("VALUES"))
			if valEls:
				valEls[0](null=val)
			else:
				self[VOTable.VALUES(null=val)]

	class _RefElement(_ValuedElement):
		_a_ref = None
		_a_ucd = None
		_a_utype = None
		childSequence = []

	class _ContentElement(_VOTElement):
		"""An element containing tabular data.

		These are usually serialized using some kind of streaming.

		See votable.tablewriter for details.
		"""
		def write(self, file):
			raise NotImplementedError("This _ContentElement cannot write yet")


	class _BinaryDataElement(_ContentElement):
		"""a base class for both BINARY and BINARY2.
		"""
		_childSequence = ["STREAM"]
		encoding = "base64"
		
		def write(self, file):
			# To be able to write incrementally, encode chunks of multiples
			# of base64's block size until the stream is finished.
			blockSize = 57
			buf, bufFil, flushThreshold = [], 0, blockSize*20
			file.write('<%s>'%self.name_)
			file.write('<STREAM encoding="base64">')
			try:
				for data in self.iterSerialized():
					buf.append(data)
					bufFil += len(data)
					if bufFil>flushThreshold:
						curData = ''.join(buf)
						curBlockLen = (len(curData)//blockSize)*blockSize
						file.write(curData[:curBlockLen].encode("base64"))
						buf = [curData[curBlockLen:]]
			finally:
				file.write("".join(buf).encode("base64"))
				file.write("</STREAM>")
				file.write('</%s>'%self.name_)

	class BINARY(_BinaryDataElement):
		pass

	class BINARY2(_BinaryDataElement):
		pass

	class COOSYS(_VOTElement):
		_a_ID = None
		_a_epoch = None
		_a_equinox = None
		_a_system = None

	class VODML(_VOTElement):
		pass
	
	class TYPE(_VOTElement):
		pass

	class ROLE(_VOTElement):
		pass

	class DATA(_VOTElement):
		_childSequence = ["INFO", "TABLEDATA", "BINARY", "BINARY2", "FITS"]
	
	class DEFINITIONS(_VOTElement):
		pass

	class DESCRIPTION(_VOTElement):
		_childSequence = [None]

	class FIELD(_TypedElement):
		_childSequence = ["DESCRIPTION", "VALUES", "LINK"]

	class FIELDref(_RefElement): pass
	
	class FITS(_VOTElement):
		_childSequence = ["STREAM"]
	
	class GROUP(_DescribedElement):
		_mayBeEmpty = True
		_a_ref = None
		_childSequence = ["DESCRIPTION", "VODML", "PARAM", "FIELDref", 
			"PARAMref", "GROUP"]


	class INFO(_ValuedElement):
		_a_ref = None
		_a_value = None
		_childSequence = [None]

		def isEmpty(self):
			return self.value is None

	class INFO_atend(INFO):
		# a bad hack; TAP mandates INFO items below table, and this is
		# the least complicated way to force this.
		name_ = "INFO"
	
	class LINK(_VOTElement):
		_a_ID = None
		_a_action = None
		_a_content_role = None
		_name_a_content_role = "content-role"
		_a_content_type = None
		_name_a_content_type = "content-type"
		_a_gref = None
		_a_href = None
		_a_name = None
		_a_value = None
		_a_title = None
		_childSequence = []
		_mayBeEmpty = True


	class MAX(_VOTElement):
		_a_inclusive = None
		_a_value = None
		_childSequence = []

		def isEmpty(self):
			return self.value is None


	class MIN(_VOTElement):
		_a_inclusive = None
		_a_value = None
		_childSequence = []

		def isEmpty(self):
			return self.value is None


	class OPTION(_VOTElement):
		_a_name = None
		_a_value = None
		_childSequence = ["OPTION"]
		_mayBeEmpty = True


	class PARAM(_TypedElement):
		_mayBeEmpty = True
		_a_value = ""  # supposed to mean "ah, somewhat null"
		               # Needs to be cared for in client code.
		_childSequence = ["VODML", "DESCRIPTION", "VALUES", "LINK"]


	class PARAMref(_RefElement): pass


	class RESOURCE(_VOTElement):
		_a_ID = None
		_a_name = None
		_a_type = None
		_a_utype = None
		_childSequence = ["DESCRIPTION", "DEFINITIONS", "COOSYS", "INFO", "GROUP", 
			"PARAM", "LINK", "TABLE", "INFO_atend", "RESOURCE", "stub"]
		# (stub for delayed overflow warnings and such)

		def writeErrorElement(self, outputFile, exception):
			outputFile.write(
				"""<INFO name="QUERY_STATUS" value="ERROR">%s</INFO>"""%
					escapePCDATA("Error while serializing VOTable,"
						" content is probably incomplete: %s"%
						utils.safe_str(exception)))
			

	class STREAM(_VOTElement):
		_a_actuate = None
		_a_encoding = None
		_a_expires = None
		_a_href = None
		_a_rights = None
		_a_type = None
		_childSequence = [None]


	class TABLE(_DescribedElement):
		"""A TABLE element.

		If you want to access fields by name (getFieldForName), make sure
		name and ids are unique.
		"""
		_a_nrows = None
		_childSequence = ["DESCRIPTION", "INFO", "GROUP", "FIELD", "PARAM", "LINK",
			"DATA", "stub"] # (stub for delayed overflow warnings and such)

		_fieldIndex = None

		@utils.memoized
		def getFields(self):
			return list(self.iterChildrenOfType(VOTable.FIELD))

		def _getFieldIndex(self):
			if self._fieldIndex is None:
				index = {}
				for child in self.getFields():
					if child.name:
						index[child.name] = child
					if child.ID:
						index[child.ID] = child
				self._fieldIndex = index
			return self._fieldIndex

		def getFieldForName(self, name):
			"""returns the FIELD having a name or id of name.

			A KeyError is raised when the field does not exist; if names are
			not unique, the last column with the name specified is returned.
			"""
			return self._getFieldIndex()["name"]


	class TABLEDATA(_ContentElement):
		_childSequence = ["TR"]
		encoding = "utf-8"

		def write(self, file):
			file.write("<TABLEDATA>")
			enc = self.encoding
			try:
				for row in self.iterSerialized():
					file.write(row.encode(enc))
			finally:
				file.write("</TABLEDATA>")
		

	class TD(_VOTElement):
		_a_encoding = None
		_childSequence = [None]
		_mayBeEmpty = True


	class TR(_VOTElement):
		_a_ID = None
		_childSequence = ["TD"]


	class VALUES(_VOTElement):
		_a_ID = None
		_a_null = None
		_a_ref = None
		_a_type = None
		
		def isEmpty(self):
			return self.null is None and Element.isEmpty(self)


	class VOTABLE(_VOTElement):
		_a_ID = None
		_a_version = "1.3"
		_prefix = "vot"
		_supressedPrefix = "vot"
		_mayBeEmpty = True
		# The following is for when the xmlstan tree is processed by 
		# tablewriter.write rather than asETree
		_fixedTagMaterial = ('xmlns="%s" xmlns:xsi="%s"'
				' xsi:schemaLocation="%s %s"')%((
					getPrefixInfo("vot")[0],
					getPrefixInfo("xsi")[0])
				+getPrefixInfo("vot"))
		_childSequence = ["DESCRIPTION", "DEFINITIONS", "INFO", "COOSYS",
			"GROUP", "PARAM", "RESOURCE"]


	class VOTABLE11(VOTABLE):
# An incredibly nasty hack that kinda works due to the fact that
# all elements here are local -- make this your top-level element
# and only use what's legal in VOTable 1.1, and you get a VOTable1.1
# conforming document
		name_ = "VOTABLE"
		_a_version = "1.1"
		_prefix = "vot1"
		_supressedPrefix = "vot1"
		# The following is for when the xmlstan tree is processed by 
		# tablewriter.write rather than asETree
		_fixedTagMaterial = ('xmlns="%s" xmlns:xsi="%s"'
				' xsi:schemaLocation="%s %s"')%((
					getPrefixInfo("vot1")[0],
					getPrefixInfo("xsi")[0])
				+getPrefixInfo("vot1"))

	class VOTABLE12(VOTABLE):
# see VOTABLE11
		name_ = "VOTABLE"
		_a_version = "1.2"
		_prefix = "vot2"
		_supressedPrefix = "vot2"
		# The following is for when the xmlstan tree is processed by 
		# tablewriter.write rather than asETree
		_fixedTagMaterial = ('xmlns="%s" xmlns:xsi="%s"'
				' xsi:schemaLocation="%s %s"')%((
					getPrefixInfo("vot1")[0],
					getPrefixInfo("xsi")[0])
				+getPrefixInfo("vot2"))



def voTag(tagName, version="1.3"):
	"""returns the VOTable QName for tagName.

	You only need this if you want to search in ElementTrees.
	"""
	return ElementTree.QName(NAMESPACES[version], tagName)
