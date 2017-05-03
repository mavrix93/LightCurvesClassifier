"""
Conversions between type systems.

The DC software has to deal with a quite a few type systems:

 - Python
 - SQL
 - VOTable
 - XSD
 - Twisted formal
 - numpy

In general, we keep metadata in the SQL type system (although one could
argue one should use the richest one...).  In this module, we want to
collect functionality to get types in other type systems from these
types (and possibly the other way round).

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

We should move all type conversion code here, and probably figure out
a sane way to concentrate value conversion here as well (though that's
probably tricky).
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


# XXX TODO: Think how this can be "inverted" by just defining types and
# collecting all their aspects in a single class

import numpy
import re

from gavo import utils
from gavo.base import common
from gavo.base import literals

class ConversionError(common.Error):
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
		"smallint": ("short", "1"),
		"integer": ("int", "1"),
		"bigint": ("long", "1"),
		"real": ("float", "1"),
		"boolean": ("boolean", "1"),
		"double precision": ("double", "1"),
		"text": ("char", "*"),
		"char": ("char", "1"),
		"date": ("char", "*"),
		"timestamp": ("char", "*"),
		"time": ("char", "*"),
		"box": ("double", "*"),
		"vexpr-mjd": ("double", "1"),
		"vexpr-string": ("char", "*"),
		"vexpr-date": ("char", "*"),
		"vexpr-float": ("double", "1"),
		"file": ("bytea", "*"),  # this is for (lame) metadata generation
		"pql-float": ("double", "1"),
		"pql-string": ("char", "*"),
		"pql-date": ("char", "*"),
		"pql-int": ("int", "1"),
		"pql-upload": ("char", "*"),  # (the upload parameter)
		"raw": ("unsignedByte", "*"),
		"bytea": ("unsignedByte", "1"),
		"spoint": ("char", "*"),  # client code would need to deal with xtype.
		"scircle": ("char", "*"),
		"sbox": ("char", "*"),
		"spoly": ("char", "*"),
		"unicode": ("unicodeChar", "*"),
	}

	def mapComplex(self, type, length):
		if length=='':
			length = '*'
		if type in self._charTypes:
			return "char", length
		elif length!=1 and length!='1' and type=="bytea":
			return ("unsignedByte", '*')
		elif type in self.simpleMap:
			return self.simpleMap[type][0], length


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


class ToXSDConverter(FromSQLConverter):

	typeSystem = "XSD"
	simpleMap = {
		"smallint": "short",
		"integer": "int",
		"bigint": "long",
		"real": "float",
		"boolean": "boolean",
		"double precision": "double",
		"text": "string",
		"unicode": "string",
		"char": "string",
		"date": "date",
		"timestamp": "dateTime",
		"time": "time",
		"raw": "string",
		"vexpr-mjd": "string",
		"vexpr-date": "string",
		"vexpr-float": "string",
		"vexpr-string": "string",
	}

	def mapComplex(self, type, length):
		if type in self._charTypes:
			return "string"


class ToNumpyConverter(FromSQLConverter):

	typeSystem = "numpy"
	simpleMap = {
		"smallint": numpy.int16,
		"integer": numpy.int32,
		"bigint": numpy.int64,
		"real": numpy.float32,
		"boolean": numpy.bool,
		"double precision": numpy.float64,
		"text": numpy.str,
		"unicode": numpy.unicode,
		"char": numpy.str,
		"date": numpy.float32,
		"timestamp": numpy.float64,
		"time": numpy.float32,
	}

	def mapComplex(self, type, length):
		if type in self._charTypes:
			return numpy.str


class ToADQLConverter(FromSQLConverter):
	typeSystem = "adql"

	simpleMap = {
		"smallint": ("SMALLINT", 1),
		"integer": ("INTEGER", 1),
		"bigint": ("BIGINT", 1),
		"real": ("REAL", 1),
		"boolean": ("INTEGER", 1),
		"double precision": ("DOUBLE", 1),
		"text": ("VARCHAR", None),
		"unicode": ("VARCHAR", None),
		"char": ("CHAR", 1),
		"date": ("VARCHAR", None),
		"timestamp": ("TIMESTAMP", 1),
		"time": ("VARCHAR", None),
		"box": ("REGION", 1),
		"spoint": ("POINT", 1),
		"scircle": ("REGION", 1),
		"spoly": ("REGION", 1),
		"sbox": ("REGION", 1),
		"bytea": ("BLOB", None),
	}

	def mapComplex(self, type, length):
		if type in self._charTypes:
			return ("VARCHAR", None)
		if type=="bytea":
			return ("BLOB", None)
		if type in self.simpleMap:
			return self.simpleMap[type][0], length


class ToPythonBase(FromSQLConverter):
	"""The base for converters turning dealing with turning "simple" literals
	into python values.

	These return the identity for most "complex" types that do not have
	plain literals.  

	What is returned here is a name of a function turning a single literal
	into an object of the desired type; all those reside within base.literals.  

	All such functions should be transparent to None (null value) and to
	objects that already are of the desired type.
	"""
	simpleMap = {
		"smallint": "parseInt",
		"integer": "parseInt",
		"bigint": "parseInt",
		"real": "parseFloat",
		"boolean": "parseBooleanLiteral",
		"double precision": "parseFloat",
		"text": "parseUnicode",
		"char": "parseUnicode",
		"unicode": "parseUnicode",
		"date": "parseDefaultDate",
		"timestamp": "parseDefaultDatetime",
		"time": "parseDefaultTime",
		"spoint": "parseSPoint",
		"scircle": "parseSimpleSTCS", 
		"spoly": "parseSimpleSTCS",
		"sbox": "identity",  # hmha, there's no STC-S for this kind of box...
		"bytea": "identity",
		"raw": "identity",
		"file": "identity",
		"box": "identity",
		"vexpr-mjd": "identity",
		"vexpr-string": "identity",
		"vexpr-float": "identity",
		"vexpr-date": "identity",
		"pql-string": "identity",
		"pql-float": "identity",
		"pql-int": "identity",
		"pql-date": "identity",
		"pql-upload": "identity",

	}

	def mapComplex(self, type, length):
		if type in self._charTypes:
			return "parseUnicode"
		else:
			return "identity"  # Anything sufficiently complex is python anyway :-)


class ToPythonCodeConverter(ToPythonBase):
	"""returns code templates to turn literals in variables to python objects.

	This is for the rowmakers' src="xx" specification, where no fancy literal
	processing needs to be done.

	The values of the map are simple string interpolation templates, with a
	single %s for the name of the variable to be converted.  

	The code assumes whatever executes those literals has done the equvialent
	of gavo.base.literals import * or use gavo.base.literals.defaultParsers()
	"""
	typeSystem = "pythonsrc"

	def convert(self, sqlType):
		funcName = ToPythonBase.convert(self, sqlType)
		if funcName=="identity":  # probably pointless performance hack
			return "%s"
		return funcName+"(%s)"


class ToPythonConverter(ToPythonBase):
	"""returns constructors making python values from strings.

	This is only for non-fancy applications with controlled input.  For
	more general circumstances, you'll want to use the parsing infrastructure.

	In particular, this will return the identity for most non-trivial stuff.
	Maybe that's wrong, but it will only change as sane literals are defined.
	"""
	typeSystem = "python"

	def convert(self, sqlType):
		funcName = ToPythonBase.convert(self, sqlType)
		return getattr(literals, funcName)


class ToLiteralConverter(object):
	"""returns a function taking some python value and returning stuff that
	can be parsed using ToPythonCodeConverter.
	"""
	typeSystem = "literal"
	simpleMap = {
		"smallint": str,
		"integer": str,
		"bigint": str,
		"real": str,
		"boolean": str,
		"double precision": str,
		"text": str,
		"char": str,
		"unicode": unicode,
		"date": lambda v: v.isoformat(),
		"timestamp": lambda v: utils.formatISODT(v),
		"time": lambda v: v.isoformat(),
		"spoint": lambda v: "%f,%f"%(v.x/utils.DEG, v.y/utils.DEG),
# XXX TODO Fix those
#		"scircle": str,
#		"spoly": str,
#		"sbox": str,
	}

	def convert(self, type):
		if type in self.simpleMap:
			return self.simpleMap[type]
		return utils.identity


toVOTableConverter = ToVOTableConverter()
sqltypeToVOTable = toVOTableConverter.convert
sqltypeToADQL = ToADQLConverter().convert
sqltypeToXSD = ToXSDConverter().convert
sqltypeToNumpy = ToNumpyConverter().convert
sqltypeToPython = ToPythonConverter().convert
sqltypeToPythonCode = ToPythonCodeConverter().convert
voTableToSQLType = FromVOTableConverter().convert
pythonToLiteral = ToLiteralConverter().convert


def _test():
	import doctest, typesystems
	doctest.testmod(typesystems)

if __name__=="__main__":
	_test()

__all__ = ["sqltypeToVOTable", "sqltypeToXSD", "sqltypeToNumpy",
	"sqltypeToPython", "sqltypeToPythonCode", "voTableToSQLType",
	"ConversionError", "FromSQLConverter", "pythonToLiteral"]
