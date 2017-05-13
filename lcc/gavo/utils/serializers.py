"""
A framework for pluggable serialisation of (python) values.

This module collects a set of basic (looking primarily towards
VOTables) serialiser factories.  These are just functions receiving
AnnotatedColumn objects and returning either None ("not responsible")
or a function taking a value and returning a string.  They may change
the AnnotatedColumn objects, for instance, when an MJD (float)
becomes a datetime.

These factories are registered in ValueMapperFactoryRegistry classes;
the one used for "normal" VOTables is the defaultMFRegistry.

Most factories are created here.  However, some depend on advance 
functionality not available here; they will be registered on import of the
respective modules (for instance, stc).

In DaCHS, a second such factory registry is created in web.htmltable.
"""

#c Copyright 2008-2016, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import datetime
import re

from gavo.utils import algotricks
from gavo.utils import typeconversions

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

	def clone(self):
		"""returns a clone of the factory.

		This is a copy, i.e., factories added will not change the original.
		"""
		return self.__class__(self.factories)

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
			mapper = algotricks.identity
		return mapper


defaultMFRegistry = ValueMapperFactoryRegistry()
registerDefaultMF = defaultMFRegistry.registerFactory


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
				res = fmtStr%(val.hour, val.minute, val.second)
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
registerDefaultMF(_timeMapperFactory)


def _byteaMapperFactory(colDesc):
	if colDesc["dbtype"]=="bytea":
		# psycopg2 here returns buffers which are painful in some situations.
		def _(val):
			return str(val)
		return _
registerDefaultMF(_byteaMapperFactory)


_pgTypes = set(["spoint", "spoly", "scircle", "sbox"])

def _pgSphereMapperFactory(colDesc):
	"""A factory for functions turning pgsphere types to STC-S-like stuff.
	"""
	if not (
			colDesc["dbtype"] in _pgTypes
			or colDesc["xtype"]=="adql:POINT"):
		return

	systemString = None
	if colDesc.original.stc:
		systemString = colDesc.original.stc.astroSystem.spaceFrame.refFrame
	if systemString is None:
		systemString = "UNKNOWNFrame"

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
registerDefaultMF(_pgSphereMapperFactory)


def _castMapperFactory(colDesc):
	"""is a factory that picks up castFunctions set up by user casts.
	"""
	if "castFunction" in colDesc:
		return colDesc["castFunction"]
registerDefaultMF(_castMapperFactory)


def _htmlScrubMapperFactory(colDesc):
	if colDesc["displayHint"].get("type")!="keephtml":
		return
	tagPat = re.compile("<[^>]*>")
	def coder(data):
		if data:
			return tagPat.sub("", data)
		return ""
	return coder
registerDefaultMF(_htmlScrubMapperFactory)


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
		type, size, xtype = typeconversions.sqltypeToVOTable(self.original.type)
		self.annotations = {
			"nullvalue": self.original.values and 
				self.original.values.nullLiteral,
			"name": self.original.key,
			"dbtype": self.original.type,
			"xtype": self.original.xtype or xtype,
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
