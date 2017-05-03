"""
Common definitions for the GAVO VOTable modules.
"""

#c Copyright 2008-2016, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from gavo import utils


NaN = float("NaN")

class VOTableError(utils.Error):
	"""Various VOTable-related errors.
	"""

class BadVOTableLiteral(VOTableError):
	"""Raised when a literal in a VOTable is invalid.
	"""
	def __init__(self, type, literal, hint=None):
		VOTableError.__init__(self, 
			"Invalid literal for %s: '%s'"%(type, repr(literal)),
			hint=hint)
		self.type, self.literal = type, literal
	
	def __str__(self):
		return "Invalid literal for %s: %s"%(self.type, repr(self.literal))

class BadVOTableData(VOTableError):
	"""Raised when something is wrong with a value being inserted into
	a VOTable.
	"""
	def __init__(self, msg, val, fieldName, hint=None):
		VOTableError.__init__(self, msg, hint=hint)
		self.fieldName, self.val = fieldName, repr(val)

	def __getstate__(self):
		return {"msg": self.msg, "val": self.val, "fieldName": self.fieldName}

	def __str__(self):
		return "Field '%s', value %s: %s"%(self.fieldName, self.val, self.msg)

class VOTableParseError(VOTableError):
	"""Raised when something is grossly wrong with the document structure.

	Note that the message passed already contains line and position.  I'd
	like to have them in separate attributes, but the expat library mashes
	them up.  iterparse.getParseError is the canonical way of obtaining these
	when you have no positional information.
	"""


def validateTDComplex(val):
	re, im = map(float, val.split())


def validateVOTInt(val):
	"""raise an error if val is not a legal int for VOTables.

	Actually, this is for tabledata, and after the relaxed 1.3 rules, we allow
	the empty string ("NULL"), too.
	"""
	if val=="":
		return 
	try:
		int(val[2:], 16)
	except ValueError:
		int(val)


def iterflattened(arr):
	"""iterates over all "atomic" values in arr.

	"atomic" means "not list, not tuple".

	TODO: Check if this sequence is compatible with VOTable spec (as it is)
	"""
	for val in arr:
		if isinstance(val, (list, tuple)):
			for subval in val:
				yield subval
		else:
			yield val


def getXtypeCode(field):
	"""returns code that will stringify values of field depending on its
	xtype.

	For None or unknown xtypes, this will return an empty list.  Otherwise,
	it expects the value in a local variable val and will leave the transformed
	value there.
	"""
	if field.xtype=="adql:TIMESTAMP":
		return [
			"if isinstance(val, datetime.datetime):",
			"  val = utils.formatISODT(val)"]

	elif field.xtype=="dachs:DATE":
		return [
			"if isinstance(val, datetime.date):",
			"  val = val.isoformat()"]
		
	elif field.xtype in ["adql:POINT", "adql:REGION"]:
		return [
			"if isinstance(val, pgsphere.PgSAdapter):",
			"  val = val.asSTCS('UNKNOWNFrame')"]

	else:
		return []


class NULLFlags(object):
	"""an interface to the BINARY2 NULL flags.

	Construct it with the number of fields, then use
	"""
	masks = [0x80, 0x40, 0x20, 0x10, 0x08, 0x04, 0x02, 0x01]

	def __init__(self, nFields):
		self.nFields = nFields
		self.nBytes = (self.nFields+7)/8
	
	def serialize(self, nullMap):
		"""returns null bytes for nullMap, which is a sequence of booleans
		with Trues where the field is NULL.

		It is an error to pass in nullMaps with lengths!=nFields.
		"""
		assert len(nullMap)==self.nFields
		bytes, curBits, val = [], 0, 0
		for isNull in nullMap:
			if isNull:
				val = (val<<1)+1
			else:
				val <<= 1
			curBits += 1
			if curBits==8:
				bytes.append(chr(val))
				curBits, val = 0, 0

		if curBits:
			val <<= (8-curBits)
			bytes.append(chr(val))
		return "".join(bytes)
	
	def serializeFromRow(self, row):
		"""returns null bytes for a row, which is a sequence of values.  
		Everything that's None is flagged as NULL.
		"""
		return self.serialize([v is None for v in row])
	
	def deserialize(self, bytes):
		"""returns a sequence of booleans giving for each element in a row
		if there's a NULL there.
		"""
		nulls = []
		for char in bytes:
			byte = ord(char)
			for mask in self.masks:
				if mask&byte:
					nulls.append(True)
				else:
					nulls.append(False)
				if len(nulls)==self.nFields:
					break
		return nulls
	
	def getFromFile(self, file):
		"""returns a sequence of booleans  giving for each element in a row
		if there's a NULL there.
		"""
		return self.deserialize(file.read(self.nBytes))

