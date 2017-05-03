"""
Turning values in our tables into strings (e.g., in VOTables or HTML).

A value mapper is a function used for serialization of (python) values
to strings.  Some of this is stuff like making product accrefs into URLs
and hence rather complex stuff.

They are produced by factories that in turn are registered in 
ValueMapperFactoryRegistries.  These can be queried for mappers using
AnnotatedColumn instances

See ValueMapperFactoryRegistry.

The module also defines a defaultMFRegistry.  It should be suitable
for serializing to VOTables and similar data machine-oriented data 
formats.

Right now, there are only two such registries in DaCHS, the other being
htmltable.  Once this changes, we should presumably provide some way
of inheriting from factory registry instances.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import datetime
import re

from gavo import adql
from gavo import stc
from gavo import utils
from gavo.base import typesystems

__docformat__ = "restructuredtext en"


class ValueMapperFactoryRegistry(object):
	"""An object clients can ask for functions fixing up values
	for encoding.

	A mapper factory is just a function that takes an AnnotatedColumn instance.
	It must return either None (for "I don't know how to make a function for this
	combination these column properties") or a callable that takes a value
	of the given type and returns a mapped value.

	To add a mapper, call registerFactory.  To find a mapper for a
	set of column properties, call getMapper -- column properties should
	be an instance of AnnotatedColumn, but for now a dictionary with the
	right keys should mostly do.

	Mapper factories are tried in the reverse order of registration,
	and the first that returns non-None wins, i.e., you should
	register more general factories first.  If no registred mapper declares
	itself responsible, getMapper returns an identity function.  If
	you want to catch such a situation, you can use somthing like
	res = vmfr.getMapper(...); if res is utils.identity ...
	"""
	def __init__(self, factories=None):
		if factories is None:
			self.factories = []
		else:
			self.factories = factories[:]

	def getFactories(self):
		"""returns the list of factories.

		This is *not* a copy.  It may be manipulated to remove or add
		factories.
		"""
		return self.factories

	def registerFactory(self, factory):
		self.factories.insert(0, factory)

	def appendFactory(self, factory):
		self.factories.append(factory)

	def getMapper(self, colDesc):
		"""returns a mapper for values with the python value instance, 
		according to colDesc.

		This method may change colDesc.

		We do a linear search here, so you shouldn't call this function too
		frequently.
		"""
		for factory in self.factories:
			mapper = factory(colDesc)
			if mapper:
				colDesc["winningFactory"] = factory
				break
		else:
			mapper = utils.identity
		return mapper


defaultMFRegistry = ValueMapperFactoryRegistry()
_registerDefaultMF = defaultMFRegistry.registerFactory


def _timeMapperFactory(annCol):
# XXX TODO: Unify with analogous code in web.htmltable
	if (annCol["dbtype"]=="time"
			or annCol["displayHint"].get("type")=="humanTime"):
		sf = int(annCol["displayHint"].get("sf", 0))
		fmtStr = "%%02d:%%02d:%%0%d.%df"%(sf+3, sf)

		def mapper(val):
			if val is None:
				return val
			elif isinstance(val, (datetime.time, datetime.datetime)):
				res = fmtStr%(val.hours, val.minutes, val.second)
			elif isinstance(val, datetime.timedelta):
				hours = val.seconds//3600
				minutes = (val.seconds-hours*3600)//60
				seconds = (val.seconds-hours*3600-minutes*60)+val.microseconds/1e6
				res = fmtStr%(hours, minutes, seconds)
			else:
				return val
			annCol["datatype"], annCol["arraysize"] = "char", "*"
			return res

		return mapper
_registerDefaultMF(_timeMapperFactory)


def datetimeMapperFactory(colDesc):
	import time

# This is too gruesome.  We want some other way of handling this...
# Simplify this, and kick out all the mess we don't want.
	if (colDesc["dbtype"]=="timestamp"
			or colDesc["dbtype"]=="date"
			or colDesc.get("xtype")=="adql:TIMESTAMP"):
		unit = colDesc["unit"]
		if (
				unit=="Y:M:D" 
				or unit=="Y-M-D" 
				or colDesc["displayHint"].get("format")=="humanDate"
				or colDesc.get("xtype")=="adql:TIMESTAMP"):
			fun = lambda val: (val and val.isoformat()) or None
			destType = ("char", "*")
			colDesc["nullvalue"] = ""

		elif (colDesc["ucd"] and "MJD" in colDesc["ucd"].upper()
				) or colDesc["xtype"]=="mjd":
			colDesc["unit"] = "d"
			fun = lambda val: (val and stc.dateTimeToMJD(val))
			destType = ("double", '1')
			colDesc["nullvalue"] = "NaN"

		elif unit=="yr" or unit=="a":
			fun = lambda val: (val and stc.dateTimeToJYear(val))
			def fun(val):
				return (val and stc.dateTimeToJYear(val))
				return str(val)
			destType = ("double", '1')
			colDesc["nullvalue"] = "NaN"

		elif unit=="d":
			fun = lambda val: (val and stc.dateTimeToJdn(val))
			destType = ("double", '1')
			colDesc["nullvalue"] = "NaN"

		elif unit=="s":
			fun = lambda val: (val and time.mktime(val.timetuple()))
			destType = ("double", '1')
			colDesc["nullvalue"] = "NaN"

		elif unit=="iso":
			fun = lambda val: (val and val.isoformat())
			destType = ("char", "*")
			colDesc["nullvalue"] = ""

		else:   # Fishy, but not our fault
			fun = lambda val: (val and stc.dateTimeToJdn(val))
			destType = ("double", '1')
			colDesc["nullvalue"] = "NaN"

		colDesc["datatype"], colDesc["arraysize"] = destType
		return fun
_registerDefaultMF(datetimeMapperFactory)


_pgTypes = set(["spoint", "spoly", "scircle", "sbox"])

def _pgSphereMapperFactory(colDesc):
	"""A factory for functions turning pgsphere types to STC-S-like stuff.
	"""
	if not (
			colDesc["dbtype"] in _pgTypes
			or colDesc["xtype"]=="adql:POINT"):
		return

	if colDesc.original.stc:
		systemString = stc.getSpatialSystem(colDesc.original.stc)
	else:
		systemString = "UNKNOWN"

	def mapper(val):
		if val is None:
			return None
		elif isinstance(val, basestring):  # allow preformatted stuff
			return val
		else:
			return val.asSTCS(systemString)

	if not colDesc["xtype"]:
		if colDesc["dbtype"]=='spoint':
			colDesc["xtype"] = "adql:POINT"
		else:
			colDesc["xtype"] = "adql:REGION"

	colDesc["datatype"], colDesc["arraysize"] = "char", "*"
	return mapper
_registerDefaultMF(_pgSphereMapperFactory)


def _boxMapperFactory(colDesc):
	"""A factory for Boxes.
	"""
	if colDesc["dbtype"]!="box":
		return

	if colDesc.original.stc:
		systemString = stc.getSpatialSystem(colDesc.original.stc)
	else:
		systemString = "UNKNOWN"

	def mapper(val):
		if val is None:
			return ""
		else:
			return "Box %s %s %s %s %s"%((systemString,)+val[0]+val[1])
	colDesc["datatype"], colDesc["arraysize"] = "char", "*"
	return mapper
_registerDefaultMF(_boxMapperFactory)


def _castMapperFactory(colDesc):
	"""is a factory that picks up castFunctions set up by user casts.
	"""
	if "castFunction" in colDesc:
		return colDesc["castFunction"]
_registerDefaultMF(_castMapperFactory)


def _htmlScrubMapperFactory(colDesc):
	if colDesc["displayHint"].get("type")!="keephtml":
		return
	tagPat = re.compile("<[^>]*>")
	def coder(data):
		if data:
			return tagPat.sub("", data)
		return ""
	return coder
_registerDefaultMF(_htmlScrubMapperFactory)


def getMapperRegistry():
	"""returns a copy of the default value mapper registry.
	"""
	return ValueMapperFactoryRegistry(
		defaultMFRegistry.getFactories())


class AnnotatedColumn(object):
	"""A collection of annotations for a column.

	ColumnAnntotations are constructed with columns and retain a
	reference to them ("original").

	In addition, they provide a getitem/setitem interface to a
	dictionary that contains "digested" information on the column.
	This dictionary serves as an accumulator for information useful
	during the serialization process.

	The main reason for this class is that Columns are supposed to be
	immutable; thus, any ephemeral information needs to be kept in a
	different place.  In particular, the mapper factories receive such
	annotations.
	
	As a special service to coerce internal tables to external standards,
	you can pass a votCast dictionary to AnnotatedColumn.  Give any 
	key/value pairs in there to override what AnnotatedColumn guesses 
	or infers.  This is used to force the sometimes a bit funky 
	SCS/SIAP types to standard values.

	The castMapperFactory enabled by default checks for the presence of
	a castFunction in an AnnotatedColumn.  If it is there, it will be used
	for mapping the values, so this is another thing you can have in votCast.
	
	The SerManager tries to obtain votCasts from a such-named
	attribute on the table passed in.

	Though of course clients can access original, the mapping facets should
	only be accessed through getitem/setitem since they may be updated
	wrt what is in original.

	Attributes available via the setitem/getitem interface include:

	- nullvalue -- a suitable nullvalue for this column, if provided by the
	  column's values or otherwise obtained
	- name -- a name for the column
	- dbtype -- the column's database type
	- xtype -- the column's xtype ("adql:TIMESTAMP")
	- datatype, arraysize -- a VOTable type for the column
	- displayHint -- a parsed display hint
	- note -- a reference to a table not (these get entered by SerManager)
	- ucd, utype, unit, description -- as for column
	- id -- a string suitable as XML id (externally managed)
	- votablewrite would evaluate min and max (but right now nothing adds
	  this)
	"""
	def __init__(self, column, votCast=None):
		self.original = column
		self._initAnnotation()
		if votCast is not None:
			self.annotations.update(votCast)

	def _initAnnotation(self):
		type, size = typesystems.sqltypeToVOTable(self.original.type)
		self.annotations = {
			"nullvalue": self.original.values and 
				self.original.values.nullLiteral,
			"name": self.original.key,
			"dbtype": self.original.type,
			"xtype": self.original.xtype,
			"datatype": type,
			"arraysize": size,
			"displayHint": self.original.displayHint,
			"note": None,
			"ucd": self.original.ucd,
			"utype": self.original.utype,
			"unit": self.original.unit, 
			"description": self.original.description,
			# id is managed by SerManager
			"id": None,
		}

	def __getitem__(self, key):
		return self.annotations[key]
	
	def __setitem__(self, key, value):
		self.annotations[key] = value

	def __contains__(self, key):
		return key in self.annotations

	def get(self, key, default=None):
		return self.annotations.get(key, default)


class SerManager(utils.IdManagerMixin):
	"""A wrapper for the serialisation of table data.

	SerManager instances keep information on what values certain columns can
	assume and how to map them to concrete values in VOTables, HTML or ASCII.
	
	They are constructed with a BaseTable instance.

	You can additionally give:

		- withRanges -- ignored, going away
		- acquireSamples -- ignored, going away
		- idManager -- an object mixing in utils.IdManagerMixin.  This is important
			if the ids we are assigning here end up in a larger document.  In that
			case, pass in the id manager of that larger document.  Default is the
			SerManager itself
		- mfRegistry -- a map factory registry.  Default is the defaltMFRegistry,
		  which is suitable for VOTables.
	
	Iterate over a SerManager to retrieve the annotated columns.
	"""
	# Filled out on demand
	_nameDict = None

	def __init__(self, table, withRanges=True, acquireSamples=True,
			idManager=None, mfRegistry=defaultMFRegistry):
		self.table = table
		if idManager is not None:
			self.cloneFrom(idManager)
		self.notes = {}
		self._makeAnnotatedColumns()
		self._makeMappers(mfRegistry)
	
	def __iter__(self):
		return iter(self.annCols)

	def _makeAnnotatedColumns(self):
		self.annCols = []
		for column in self.table.tableDef:
			self.annCols.append(
				AnnotatedColumn(column, self.table.votCasts.get(column.name)))

			# Do not generate an id if the field is already defined somewhere else.
			# (if that happens, STC definitions could be in trouble, so try
			# to avoid it, all right?)
			colId = self.makeIdFor(column, column.id or column.key)
			if colId is not None:
				self.annCols[-1]["id"] = colId

			# if column refers to a note, remember the note
			if column.note:
				try:
					self.notes[column.note.tag] = column.note
					self.annCols[-1]["note"] = column.note
				except (ValueError, utils.NotFoundError): 
					pass # don't worry about missing notes, but don't display them either
	
		self.byName = dict(
			(annCol["name"], annCol) for annCol in self.annCols)

	def _makeMappers(self, mfRegistry):
		"""returns a sequence of functions mapping our columns.

		As a side effect, column properties may change (in particular,
		datatypes).
		"""
		self.mappers = tuple(mfRegistry.getMapper(annCol) for annCol in self)

	def getColumnByName(self, name):
		return self.byName[name]

	def _compileMapFunction(self, funcLines):
		"""helps _make(Dict|Tuple)Factory.
		"""
		return utils.compileFunction(
			"\n".join(funcLines), "buildRec",
			useGlobals=dict(("map%d"%index, mapper) 
				for index, mapper in enumerate(self.mappers)))

	def _makeDictFactory(self):
		"""returns a function that returns a dictionary of mapped values
		for a row dictionary.
		"""
		colLabels = [str(c["name"]) for c in self]
		funDef = ["def buildRec(rowDict):"]
		for index, label in enumerate(colLabels):
			if self.mappers[index] is not utils.identity:
				funDef.append("\trowDict[%r] = map%d(rowDict[%r])"%(
					label, index, label))
		funDef.append("\treturn rowDict")
		return self._compileMapFunction(funDef)

	def _makeTupleFactory(self):
		"""returns a function that returns a tuple of mapped values
		for a row dictionary.
		"""
		funDef = ["def buildRec(rowDict):", "\treturn ("]
		for index, cd in enumerate(self):
			if self.mappers[index] is utils.identity:
				funDef.append("\t\trowDict[%r],"%cd["name"])
			else:
				funDef.append("\t\tmap%d(rowDict[%r]),"%(index, cd["name"]))
		funDef.append("\t)")
		return self._compileMapFunction(funDef)

	def _iterWithMaps(self, buildRec):
		"""helps getMapped(Values|Tuples).
		"""
		colLabels = [f.name for f in self.table.tableDef]
		if not colLabels:
			yield ()
			return
		for row in self.table:
			yield buildRec(row)

	def getMappedValues(self):
		"""iterates over the table's rows as dicts with mapped values.
		"""
		return self._iterWithMaps(self._makeDictFactory())

	def getMappedTuples(self):
		"""iterates over the table's rows as tuples with mapped values.
		"""
		return self._iterWithMaps(self._makeTupleFactory())


def needsQuoting(identifier, forRowmaker=False):
	"""returns True if identifier needs quoting in an SQL statement.
	>>> needsQuoting("RA(J2000)")
	True
	>>> needsQuoting("ABS")
	True
	>>> needsQuoting("r")
	False
	"""
	if utils.identifierPattern.match(identifier) is None:
		return True
	if identifier.lower() in getNameBlacklist(forRowmaker):
		return True
	return False


@utils.memoized
def getNameBlacklist(forRowmaker=False):
	"""returns a set of names not suitable for table column names.

	This comprises SQL reserved words in lower case and, if forRowmaker
	is true, also some names damaging row makers (e.g. python reserved
	words).
	"""
	res = set(k.lower() for k in adql.allReservedWords)
	if forRowmaker:
		import keyword
		from gavo.rscdef import rmkfuncs
		res = (res 
			| set(["result_", "rowdict_"])
			| set(k.lower() for k in keyword.kwlist)
			| set(k.lower() for k in dir(rmkfuncs)))
	return frozenset(res)


class VOTNameMaker(object):
	"""A class for generating db-unique names from VOTable fields.

	This is important to avoid all kinds of weird names the remaining
	infrastructure will not handle.  "Normal" TableDefs assume unquoted
	SQL identifiers as names, and want all names unique.

	Using this class ensures these expectations are met in a reproducible
	way (i.e., given the same table, the same names will be assigned).
	"""
	def __init__(self):
		self.knownNames, self.index = set(getNameBlacklist(True)), 0

	def makeName(self, field):
		preName = re.sub("[^\w]+", "x", (getattr(field, "name", None) 
			or getattr(field, "ID", None)
			or "field%02d"%self.index))
		if not re.match("[A-Za-z_]", preName):
			preName = "col_"+preName
		while preName.lower() in self.knownNames:
			preName = preName+"_"
		self.knownNames.add(preName.lower())
		self.index += 1
		return preName


def _test():
	import doctest, valuemappers
	doctest.testmod(valuemappers)


if __name__=="__main__":
	_test()

