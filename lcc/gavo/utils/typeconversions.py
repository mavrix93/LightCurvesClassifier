"""
Conversions between type systems.

The DC software has to deal with a quite a few type systems (see
base.typesystems). In general, we keep metadata in the SQL type system;
in particular, column's and param's type attribute takes values in that.

In fact, we use a couple of extensions:

	- file -- this corresponds to a file upload from the web (i.e., a pair
		(filename, file object)).  It would be conceivable to turn this into
		blobs at some point, but right now we simply don't touch it.
	- vexpr-float, -text, -date, -mjd -- vizier-like expressions coming in from
		the web.  These are always strings.
	- raw -- handed right through, whatever it is.  For target formats that
		can't do this, usually strings are used.
	- unicode -- this is TEXT in the database, but while normal text will
	  be rendered as byte strings in VOTables (with non-ASCII-characters
	  replaced by ?), unicode will become an array of unicodeChars.

This module contains a base class and the VOTable type system conversion,
as the VOTable module (that should not depend on base) depends on it.
The remaining actual converters are in base.typesystems, as they may depend
on details of base.  Even the SQL converters should be taken from there
when code can rely on gavo.base; this module should be considered an 
implementation detail.
"""

#c Copyright 2008-2016, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


# XXX TODO: Think how this can be "inverted" by just defining types and
# collecting all their aspects in a single class

import re

from gavo.utils import excs


class ConversionError(excs.Error):
	pass


class FromSQLConverter(object):
	"""is an abstract base class for type converters from the SQL type system.

	Implementing classes have to provide a dict simpleMap mapping sql type
	strings to target types, and a method mapComplex that receives a type
	and a length (both strings, derived from SQL array types) and either
	returns None (no matching type) or the target type.

	Implementing classes should also provide a typeSystem attribute giving
	a short name of the type system they convert to.
	"""
	_charTypes = set(["character varying", "varchar", "character", "char"])

	def convert(self, sqlType):
		res = None
		if sqlType in self.simpleMap:
			res = self.simpleMap[sqlType]
		else:
			mat = re.match(r"(.*)[[(](\d+|\*|)[])]", sqlType)
			if mat:
				res = self.mapComplex(mat.group(1), mat.group(2))
		if res is None:
			if sqlType=="raw":
				return "raw"
			raise ConversionError("No %s type for %s"%(self.typeSystem, sqlType))
		return res

	def mapComplex(self, type, length):
		return


class ToVOTableConverter(FromSQLConverter):
	typeSystem = "VOTable"

	simpleMap = {
		"smallint": ("short", "1", None),
		"integer": ("int", "1", None),
		"bigint": ("long", "1", None),
		"real": ("float", "1", None),
		"boolean": ("boolean", "1", None),
		"double precision": ("double", "1", None),
		"text": ("char", "*", None),
		"char": ("char", "1", None),
		"date": ("char", "*", None),
		"timestamp": ("char", "*", "adql:TIMESTAMP"),
		"time": ("char", "*", None),
		"box": ("double", "*", None),
		"vexpr-mjd": ("char", "*", None),
		"vexpr-string": ("char", "*", None),
		"vexpr-date": ("char", "*", None),
		"vexpr-float": ("char", "*", None),
		"file": ("bytea", "*", None),  # this is for (lame) metadata generation
		"pql-float": ("char", "*", None),
		"pql-string": ("char", "*", None),
		"pql-date": ("char", "*", None),
		"pql-int": ("char", "*", None),
		"pql-upload": ("char", "*", None),  # (the upload parameter)
		"raw": ("unsignedByte", "*", None),
		"bytea": ("unsignedByte", "1", None),
		"spoint": ("char", "*", "adql:POINT"),
		"scircle": ("char", "*", "adql:REGION"),
		"sbox": ("char", "*", "adql:REGION"),
		"spoly": ("char", "*", "adql:REGION"),
		"unicode": ("unicodeChar", "*", None),
	}

	def mapComplex(self, type, length):
		if length=='':
			length = '*'
		if type in self._charTypes:
			return "char", length, None
		elif length!=1 and length!='1' and type=="bytea":
			return ("unsignedByte", '*', None)
		elif type=="text" and str(length)!='1':
			return ("char", ".x*", None)
		elif type in self.simpleMap:
			return self.simpleMap[type][0], length, None


class FromVOTableConverter(object):
	typeSystem = "db"
	
	simpleMap = {
		("short", '1'): "smallint",
		("int", '1'): "integer",
		("long", '1'): "bigint",
		("float", '1'): "real",
		("boolean", '1'): "boolean",
		("double", '1'): "double precision",
		("char", "*"): "text",
		("char", '1'): "char",
		("unsignedByte", '1'): "smallint",
		("raw", '1'): "raw",
	}

	xtypeMap = {
		"adql:POINT": "spoint",
		"adql:REGION": "spoly",
		"adql:TIMESTAMP": "timestamp",
	}

	def convert(self, type, arraysize, xtype=None):
		if self.xtypeMap.get(xtype):
			return self.xtypeMap[xtype]
		if arraysize=="1" or arraysize=="" or arraysize is None:
			arraysize = "1"
		if (type, arraysize) in self.simpleMap:
			return self.simpleMap[type, arraysize]
		else:
			return self.mapComplex(type, arraysize)

	def mapComplex(self, type, arraysize):
		if arraysize=="*":
			arraysize = ""
		if type=="char":
			return "text"
		if type=="unicodeChar":
			return "unicode"
		if type=="unsignedByte" and arraysize!="1":
			return "bytea[]"
		if (type, '1') in self.simpleMap:
			return "%s[%s]"%(self.simpleMap[type, '1'], arraysize)
		raise ConversionError("No SQL type for %s, %s"%(type, arraysize))


sqltypeToVOTable = ToVOTableConverter().convert
voTableToSQLType = FromVOTableConverter().convert
