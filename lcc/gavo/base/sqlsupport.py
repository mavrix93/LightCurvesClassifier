# -*- encoding: iso-8859-1 -*-
"""
Basic support for communicating with the database server.

This is currently very postgres specific.  If we really wanted to
support some other database, this would need massive refactoring.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import contextlib
import itertools
import os
import random
import re
import threading

import numpy

from gavo import utils
from gavo.base import config

debug = "GAVO_SQL_DEBUG" in os.environ

import psycopg2
import psycopg2.extensions
import psycopg2.pool
psycopg2.extensions.register_type(psycopg2.extensions.UNICODE)
try:
	psycopg2.extensions.register_type(psycopg2.extensions.UNICODEARRAY)
except AttributeError:  # UNICODEARRAY only at psycopg2 >2.0
	pass

from psycopg2.extras import DictCursor #noflake: exported name

class Error(utils.Error):
	pass


_PG_TIME_UNITS = {
	"ms": 0.0001,
	"s": 1.,
	"": 1.,
	"min": 60.,
	"h": 3600.,
	"d": 86400.,}


# Keep track of wether we have installed our extensions
# (this is to not require a DB connection on just importing this)
_PSYCOPG_INITED = False

class SqlSetAdapter(object):
	"""is an adapter that formats python sequences as SQL sets.

	-- as opposed to psycopg2's apparent default of building arrays
	out of them.
	"""
	def __init__(self, seq):
		self._seq = seq

	def prepare(self, conn):
		pass

	def getquoted(self):
		qobjs = []
		for o in self._seq:
			if isinstance(o, unicode):
				qobjs.append(psycopg2.extensions.adapt(str(o)).getquoted()) 
			else:
				qobjs.append(psycopg2.extensions.adapt(o).getquoted()) 
		return '(%s)'%(", ".join(qobjs))

	__str__ = getquoted


class SqlArrayAdapter(object):
	"""An adapter that formats python sequences as SQL arrays

	This makes, in the shameful tradition of VOTable, empty arrays equal to
	NULL.
	"""
	def __init__(self, seq):
		self._seq = seq

	def prepare(self, conn):
		pass

	def getquoted(self):
		if len(self._seq)==0:
			return 'NULL'
		qobjs = [str(psycopg2.extensions.adapt(o).getquoted()) 
			for o in self._seq]
		return 'ARRAY[ %s ]'%(", ".join(qobjs))

	__str__ = getquoted


class FloatableAdapter(object):
	"""An adapter for things that do "float", in particular numpy.float*
	"""
	def __init__(self, val):
		self.val = float(val)

	def prepare(self, conn):
		pass

	def getquoted(self):
		return repr(self.val)

	__str__ = getquoted


class IntableAdapter(object):
	"""An adapter for things that do "int", in particular numpy.int*
	"""
	def __init__(self, val):
		self.val = int(val)

	def prepare(self, conn):
		pass

	def getquoted(self):
		return str(self.val)

	__str__ = getquoted


psycopg2.extensions.register_adapter(tuple, SqlArrayAdapter)
psycopg2.extensions.register_adapter(numpy.ndarray, SqlArrayAdapter)
psycopg2.extensions.register_adapter(list, SqlSetAdapter)
psycopg2.extensions.register_adapter(set, SqlSetAdapter)
psycopg2.extensions.register_adapter(frozenset, SqlSetAdapter)

for numpyType, adapter in [
		("float32", FloatableAdapter), 
		("float64", FloatableAdapter), 
		("float96", FloatableAdapter), 
		("int8", IntableAdapter),
		("int16", IntableAdapter),
		("int32", IntableAdapter),
		("int64", IntableAdapter),]:
	try:
		psycopg2.extensions.register_adapter(
			getattr(numpy, numpyType), adapter)
	except AttributeError:
		# what's not there we don't need to adapt
		pass

from psycopg2 import (OperationalError, #noflake: exported names
	DatabaseError, IntegrityError, ProgrammingError, 
	InterfaceError, DataError, InternalError)
from psycopg2.extensions import QueryCanceledError #noflake: exported name
from psycopg2 import Error as DBError


def registerAdapter(type, adapter):
	psycopg2.extensions.register_adapter(type, adapter)


def registerType(oid, name, castFunc):
	newOID = psycopg2.extensions.new_type(oid, name, castFunc)
	psycopg2.extensions.register_type(newOID)


class DebugCursor(psycopg2.extensions.cursor):
	def execute(self, sql, args=None):
		print "Executing %s %s"%(id(self.connection), sql)
		res = psycopg2.extensions.cursor.execute(self, sql, args)
		print "Finished %s %s"%(id(self.connection), self.query)
		return res
	
	def executemany(self, sql, args=[]):
		print "Executing many", sql
		print "%d args, first one:\n%s"%(len(args), args[0])
		res = psycopg2.extensions.cursor.executemany(self, sql, args)
		print "Finished many", self.query
		return res


class GAVOConnection(psycopg2.extensions.connection):
	"""A psycopg2 connection with some additional methods.

	This derivation is also done so we can attach the getDBConnection
	arguments to the connection; it is used when recovering from
	a database restart.
	"""
	def queryToDicts(self, query, args={}):
		"""iterates over dictionary rows for query.

		This is mainly for ad-hoc queries needing little metadata.

		The dictionary keys are determined by what the database says the
		column titles are; thus, it's usually lower-cased variants of what's
		in the select-list.
		"""
		cursor = self.cursor()
		try:
			cursor.execute(query, args)
			keys = [cd[0] for cd in cursor.description]
			for row in cursor:
				yield dict(zip(keys, row))
		finally:
			cursor.close()

	def query(self, query, args={}):
		"""iterates over result tuples for query.

		This is mainly for ad-hoc queries needing little metadata.
		"""
		cursor = self.cursor()
		try:
			cursor.execute(query, args)
			for row in cursor:
				yield row
		finally:
			cursor.close()
	
	def execute(self, query, args={}):
		"""executes query in a cursor; returns nothing.
		"""
		cursor = self.cursor()
		try:
			cursor.execute(query, args)
		finally:
			cursor.close()


class DebugConnection(GAVOConnection):
	def cursor(self, *args, **kwargs):
		kwargs["cursor_factory"] = DebugCursor
		return psycopg2.extensions.connection.cursor(self, *args, **kwargs)

	def commit(self):
		print "Commit %s"%id(self)
		return GAVOConnection.commit(self)
	
	def rollback(self):
		print "Rollback %s"%id(self)
		return GAVOConnection.rollback(self)


	def getPID(self):
		cursor = self.cursor()
		cursor.execute("SELECT pg_backend_pid()")
		pid = list(cursor)[0][0]
		cursor.close()
		return pid


def getDBConnection(profile, debug=debug, autocommitted=False):
	"""returns a slightly instrumented connection through profile.

	For the standard table connection, there's a pool of those below.
	"""
	if profile is None:
		profile = "trustedquery"
	if isinstance(profile, basestring):
		profile = config.getDBProfile(profile)

	if debug:
		conn = psycopg2.connect(connection_factory=DebugConnection,
			**profile.getArgs())
		print "NEW CONN using %s (%s)"%(profile.name, conn.getPID()), id(conn)
		def closer():
			print "CONNECTION CLOSE", id(conn)
			return DebugConnection.close(conn)
		conn.close = closer
	else:
		try:
			conn = psycopg2.connect(connection_factory=GAVOConnection, 
				**profile.getArgs())
		except OperationalError, msg:
			raise utils.ReportableError("Cannot connect to the database server."
				" The database library reported:\n\n%s"%msg,
				hint="This usually means you must adapt either the access profiles"
				" in $GAVO_DIR/etc or your database config (in particular,"
				" pg_hba.conf).")

	if not _PSYCOPG_INITED:
		_initPsycopg(conn)
	if autocommitted:
		conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
	conn.set_client_encoding("UTF8")

	conn._getDBConnectionArgs = {
		"profile": profile,
		"debug": debug,
		"autocommitted": autocommitted}
	return conn


def _parseTableName(tableName, schema=None):
		"""returns schema, unqualified table name for the arguments.

		schema=None selects the default schema (public for postgresql).

		If tableName is qualified (i.e. schema.table), the schema given
		in the name overrides the schema argument.
		"""
		if schema is None:
			schema = "public"
		if "." in tableName:
			schema, tableName = tableName.split(".")
		return schema.lower(), tableName.lower()


def parseBannerString(bannerString, digits=2):
	"""returns digits from a postgres server banner.

	This hardcodes the response given by postgres 8 and raises a ValueError
	if the expected format is not found.
	"""
	mat = re.match(r"PostgreSQL ([\d.]*)", bannerString)
	if not mat:
		raise ValueError("Cannot make out the Postgres server version from %s"%
			repr(bannerString))
	return ".".join(mat.group(1).split(".")[:digits])


class PostgresQueryMixin(object):
	"""is a mixin containing various useful queries that are postgres specific.

	This mixin expects a parent that mixes is QuerierMixin (that, for now,
	also mixes in PostgresQueryMixin, so you won't need to mix this in).
	"""
	def getServerVersion(self, digits=2):
		"""returns the version of the connection's server to digits numbers.
		"""
		bannerString = list(self.query("SELECT version()"))[0][0]
		return parseBannerString(bannerString, digits)

	def getPrimaryIndexName(self, tableName):
		"""returns the name of the index corresponding to the primary key on 
		(the unqualified) tableName.
		"""
		return ("%s_pkey"%tableName).lower()
	
	def schemaExists(self, schema):
		"""returns True if the named schema exists in the database.
		"""
		matches = self.query("SELECT nspname FROM"
			" pg_namespace WHERE nspname=%(schemaName)s", {
					'schemaName': schema,
			}).fetchall()
		return len(matches)!=0
	
	def hasIndex(self, tableName, indexName, schema=None):
		"""returns True if table tablename has and index called indexName.

		See _parseTableName on the meaning of the arguments.
		"""
		schema, tableName = _parseTableName(tableName, schema)
		res = self.query("SELECT indexname FROM"
			" pg_indexes WHERE schemaname=lower(%(schema)s) AND"
			" tablename=lower(%(tableName)s) AND"
			" indexname=lower(%(indexName)s)", locals()).fetchall()
		return len(list(res))>0

	def _getColIndices(self, relOID, colNames):
		"""returns a sorted tuple of column indices of colNames in the relation
		relOID.

		This really is a helper for foreignKeyExists.
		"""
		colNames = [n.lower() for n in colNames]
		res = [r[0] for r in 
			self.query("SELECT attnum FROM pg_attribute WHERE"
				" attrelid=%(relOID)s and attname IN %(colNames)s",
				locals())]
		res.sort()
		return tuple(res)

	def getForeignKeyName(self, srcTableName, destTableName, srcColNames, 
			destColNames, schema=None):
		"""returns True if there's a foreign key constraint on srcTable's 
		srcColNames using destTableName's destColNames.

		Warning: names in XColNames that are not column names in the respective
		tables are ignored.
		"""
		try:
			srcOID = self.getOIDForTable(srcTableName, schema)
			srcColInds = self._getColIndices( #noflake: used in locals()
				srcOID, srcColNames) 
			destOID = self.getOIDForTable(destTableName, schema)
			destColInds = self._getColIndices( #noflake: used in locals()
				destOID, destColNames)
		except Error: # Some of the items related probably don't exist
			return False
		try:
			res = list(self.query("""
				SELECT conname FROM pg_constraint WHERE
				contype='f'
				AND conrelid=%(srcOID)s
				AND confrelid=%(destOID)s
				AND conkey=%(srcColInds)s::SMALLINT[]
				AND confkey=%(destColInds)s::SMALLINT[]""", locals()))
		except ProgrammingError: # probably columns do not exist
			return False
		if len(res)==1:
			return res[0][0]
		else:
			raise DBError("Non-existing or ambiguos foreign key")

	def foreignKeyExists(self, srcTableName, destTableName, srcColNames, 
			destColNames, schema=None):
		try:
			return self.getForeignKeyName(srcTableName, destTableName, srcColNames,
				destColNames, schema)
		except DBError:
			return False
		return True

	def roleExists(self, role):
		"""returns True if there role is known to the database.
		"""
		matches = self.query("SELECT usesysid FROM pg_user WHERE usename="
			"%(role)s", locals()).fetchall()
		return len(matches)!=0
	
	def getOIDForTable(self, tableName, schema=None):
		"""returns the current oid of tableName.

		tableName may be schema qualified.  If it is not, public is assumed.
		"""
		schema, tableName = _parseTableName(tableName, schema)
		res = list(self.query("SELECT oid FROM pg_class WHERE"
			" relname=%(tableName)s AND"
			" relnamespace=(SELECT oid FROM pg_namespace WHERE nspname=%(schema)s)",
			locals()))
		if len(res)!=1:
			raise Error("Table %s does not exist"%tableName)
		return res[0][0]

	def _rowExists(self, query, pars):
		res = self.query(query, pars).fetchall()
		return len(res)!=0

	def temporaryTableExists(self, tableName):
		"""returns True if a temporary table tablename exists in the table's
		connection.

		*** postgres specific ***
		"""
		return self._rowExists("SELECT table_name FROM"
			" information_schema.tables WHERE"
			" table_type='LOCAL TEMPORARY' AND table_name=%(tableName)s", 
			{'tableName': tableName.lower()})

	def tableExists(self, tableName, schema=None):
		"""returns True if a table tablename exists in schema.

		*** postgres specific ***
		"""
		schema, tableName = _parseTableName(tableName, schema)
		return self._rowExists("SELECT table_name FROM"
			" information_schema.tables WHERE"
			" table_schema=%(schemaName)s AND table_name=%(tableName)s", 
			{'tableName': tableName.lower(), 'schemaName': schema.lower()})

	def viewExists(self, tableName, schema=None):
		schema, tableName = _parseTableName(tableName, schema)
		return self._rowExists("SELECT viewname FROM"
			" pg_views WHERE"
			" schemaname=%(schemaName)s AND viewname=%(tableName)s", 
			{'tableName': tableName.lower(), 'schemaName': schema.lower()})

	def getSchemaPrivileges(self, schema):
		"""returns (owner, readRoles, allRoles) for the relation tableName
		and the schema.
		"""
		res = self.query("SELECT nspacl FROM pg_namespace WHERE"
			" nspname=%(schema)s", locals()).fetchall()
		return self.parsePGACL(res[0][0])

	def getTablePrivileges(self, schema, tableName):
		"""returns (owner, readRoles, allRoles) for the relation tableName
		and the schema.

		*** postgres specific ***
		"""
		res = self.query("SELECT relacl FROM pg_class WHERE"
			" lower(relname)=lower(%(tableName)s) AND"
			" relnamespace=(SELECT oid FROM pg_namespace WHERE nspname=%(schema)s)",
			locals()).fetchall()
		try:
			return self.parsePGACL(res[0][0])
		except IndexError: # Table doesn't exist, so no privileges
			return {}

	_privTable = {
		"arwdRx": "ALL",
		"arwdDxt": "ALL",
		"arwdRxt": "ALL",
		"arwdxt": "ALL",
		"r": "SELECT",
		"UC": "ALL",
		"U": "USAGE",
	}

	def parsePGACL(self, acl):
		"""returns a dict roleName->acl for acl in postgres'
		ACL serialization.
		"""
		if acl is None:
			return {}
		res = []
		for acs in re.match("{(.*)}", acl).group(1).split(","):
			if acs!='':  # empty ACLs don't match the RE, so catch them here
				role, privs, granter = re.match("([^=]*)=([^/]*)/(.*)", acs).groups()
				res.append((role, self._privTable.get(privs, "READ")))
		return dict(res)


	def getACLFromRes(self, thingWithPrivileges):
		"""returns a dict of (role, ACL) as it is defined in thingWithPrivileges.

		thingWithPrivileges is something mixing in rscdef.common.PrivilegesMixin.
		(or has readProfiles and allProfiles attributes containing
		sequences of profile names).
		"""
		res = []
		if hasattr(thingWithPrivileges, "schema"): # it's an RD
			readRight = "USAGE"
		else:
			readRight = "SELECT"

		for profile in thingWithPrivileges.readProfiles:
			res.append((config.getDBProfile(profile).roleName, readRight))
		for profile in thingWithPrivileges.allProfiles:
			res.append((config.getDBProfile(profile).roleName, "ALL"))
		return dict(res)


class StandardQueryMixin(object):
	"""is a mixin containing various useful queries that should work
	agains all SQL systems.

	This mixin expects a parent that mixes is QuerierMixin (that, for now,
	also mixes in StandardQueryMixin, so you won't need to mix this in).

	The parent also needs to mix in something like PostgresQueryMixin (I
	might want to define an interface there once I'd like to support
	other databases).
	"""
	def setSchemaPrivileges(self, rd):
		"""sets the privileges defined on rd to its schema.

		This function will never touch the public schema.
		"""
		schema = rd.schema.lower()
		if schema=="public":
			return
		self._updatePrivileges("SCHEMA %s"%schema,
			self.getSchemaPrivileges(schema), self.getACLFromRes(rd))
	
	def setTablePrivileges(self, tableDef):
		"""sets the privileges defined in tableDef for that table through
		querier.
		"""
		self._updatePrivileges(tableDef.getQName(),
			self.getTablePrivileges(tableDef.rd.schema, tableDef.id),
			self.getACLFromRes(tableDef))
	
	def _updatePrivileges(self, objectName, foundPrivs, shouldPrivs):
		"""is a helper for set[Table|Schema]Privileges.

		Requests for granting privileges not known to the database are
		ignored, but a log entry is generated.
		"""
		for role in set(foundPrivs)-set(shouldPrivs):
			if role:
				self.query("REVOKE ALL PRIVILEGES ON %s FROM %s"%(
					objectName, role))
		for role in set(shouldPrivs)-set(foundPrivs):
			if role:
				if self.roleExists(role):
					self.query("GRANT %s ON %s TO %s"%(shouldPrivs[role], objectName,
						role))
				else:
					utils.sendUIEvent("Warning", 
						"Request to grant privileges to non-existing"
						" database user %s dropped"%role)
		for role in set(shouldPrivs)&set(foundPrivs):
			if role:
				if shouldPrivs[role]!=foundPrivs[role]:
					self.query("REVOKE ALL PRIVILEGES ON %s FROM %s"%(
						objectName, role))
					self.query("GRANT %s ON %s TO %s"%(shouldPrivs[role], objectName,
						role))

	def setTimeout(self, timeout):
		"""sets a timeout on queries.

		timeout is in seconds; timeout=0 disables timeouts (this is what
		postgres does, too)
		"""
		# don't use query here since query may call setTimeout
		cursor = self.connection.cursor()
		try:
			if timeout==-12: # Special instrumentation for testing
				cursor.execute("SET statement_timeout TO 1")
			elif timeout is not None:
				cursor.execute(
					"SET statement_timeout TO %d"%(int(float(timeout)*1000)))
		finally:
			cursor.close()

	def getTimeout(self):
		"""returns the current timeout setting.

		The value is in float seconds.
		"""
		# don't use query here since it may call getTimeout
		cursor = self.connection.cursor()
		try:
			cursor.execute("SHOW statement_timeout")
			rawVal = list(cursor)[0][0]
			mat = re.match("(\d+)(\w*)$", rawVal)
			try:
				return int(mat.group(1))*_PG_TIME_UNITS[mat.group(2)]
			except (ValueError, AttributeError, KeyError):
				raise ValueError("Bad timeout value from postgres: %s"%rawVal)
		finally:
			cursor.close()


def dictifyRowset(descr, rows):
# deprecated -- remove this when SimpleQuerier is gone
	"""turns a standard, tuple-based rowset into a list of dictionaries,
	the keys of which are taken from descr (a cursor.description).
	"""
	keys = [cd[0] for cd in descr]
	return [dict(itertools.izip(keys, row)) for row in rows]


class QuerierMixin(PostgresQueryMixin, StandardQueryMixin):
	"""is a mixin for "queriers", i.e., objects that maintain a db connection.

	The mixin assumes an attribute connection from the parent.
	"""
	defaultProfile = None
	# _reconnecting is used in query
	_reconnecting = False

	def configureConnection(self, settings):
		cursor = self.connection.cursor()
		for key, val in settings:
			cursor.execute("SET %s=%%(val)s"%key, {"val": val})
		cursor.close()

	def runIsolatedQuery(self, query, data={}, silent=False, raiseExc=True,
			timeout=None, asDict=False, settings=()):
		"""runs a query over a connection of its own and returns a rowset of 
		the result if the query is successful.

		Mostly, you'll create all kinds of races if you think you need this.
		Unfortunately, until postgres gets nested transactions, there's little
		I can do.
		"""
		connection = getDBConnection(self.defaultProfile)
		self.configureConnection(settings)
		cursor = connection.cursor()
		try:
			if timeout:  # *** Postgres specific ***
				cursor.execute("SET statement_timeout TO %d"%int(timeout*1000))
			cursor.execute(query, data)
		except DBError, msg:
			cursor.close()
			connection.rollback()
			connection.close()
			if not silent:
				utils.sendUIEvent("Warning", "Failed query %s with"
					" arguments %s (%s)\n"%(repr(cursor.query), data, str(msg).strip()))
			if raiseExc:
				raise
		except:
			connection.rollback()
			connection.close()
			raise
		else:
			try:
				res = cursor.fetchall()
				descr = cursor.description
			except DBError:  # No results to fetch
				res = None
			cursor.close()
			connection.commit()
			connection.close()
			if asDict:
				return dictifyRowset(descr, res)
			else:
				return res

	def enableAutocommit(self):
		self.connection.set_isolation_level(
			psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)

	def _queryReconnecting(self, query, data):
		"""helps query in case of disconnections.
		"""
		self.connection = getDBConnection(
			**self.connection._getDBConnectionArgs)
		self._reconnecting = True
		res = self.query(query, data)
		self._reconnection = False
		return res

	def query(self, query, data={}, timeout=None):
		"""runs a single query in a new cursor and returns that cursor.

		You will see all exceptions, no transaction management is
		done here.

		query will try to re-establish broken connections.
		"""
		if self.connection is None:
			raise utils.ReportableError(
				"SimpleQuerier connection is None.",
				hint="This ususally is because an AdhocQuerier's query method"
				" was used outside of a with block.")

		cursor = self.connection.cursor()
		try:

			if timeout is not None:
				oldTimeout = self.getTimeout()
				self.setTimeout(timeout)
			try:
				cursor.execute(query, data)
			finally:
				if timeout is not None:
					self.setTimeout(oldTimeout)

		except DBError, ex:
			if isinstance(ex, OperationalError) and self.connection.fileno()==-1:
				if not self._reconnecting:
					return self._queryReconnecting(query, data)
			utils.sendUIEvent("Info", "Failed db query: '%s'"%
				getattr(cursor, "query", query))
			raise
		return cursor

	def queryDicts(self, *args, **kwargs):
		"""as query, but returns dicts with the column names.
		"""
		cursor = self.query(*args, **kwargs)
		keys = [d[0] for d in cursor.description]
		for row in cursor:
			yield dict(itertools.izip(keys, row))

	def finish(self):
		self.connection.commit()
		self.connection.close()

	def abort(self):
		self.connection.close()


class UnmanagedQuerier(QuerierMixin):
	"""A simple interface to querying the database through a connection
	managed by someone else.

	You have to pass in the connection, and any committing or rollback
	is your responsibility.
	"""
	def __init__(self, connection):
		self.connection = connection


class AdhocQuerier(QuerierMixin):
	"""A simple interface to querying the database through pooled
	connections.

	These are constructed using the connection getters (getTableConn (default),
	getAdminConn) and then serve as context managers, handing back the connection
	as you exit the controlled block.

	Since they operate through pooled connections, no transaction
	management takes place.  These are typically for read-only things.

	You can use the query method and everything that's in the QuerierMixin.
	"""
	def __init__(self, connectionManager=None):
		if connectionManager is None:
			self.connectionManager = getTableConn
		else:
			self.connectionManager = connectionManager
		self.connection = None
	
	def __enter__(self):
		self._cm = self.connectionManager()
		self.connection = self._cm.__enter__()
		return self
	
	def __exit__(self, *args):
		self.connection = None
		return self._cm.__exit__(*args)


def setDBMeta(conn, key, value):
	"""adds/overwrites (key, value) in the dc.metastore table within
	conn.

	conn must be an admin connection; this does not commit.

	key must be a string, value something unicodeable.
	"""
	conn.execute(
		"INSERT INTO dc.metastore (key, value) VALUES (%(key)s, %(value)s)", {
		'key': key,
		'value': unicode(value)})


def getDBMeta(key):
	"""returns the value for key from within dc.metastore.

	This always returns a unicode string.  Type conversions are the client's
	business.

	If no value exists, this raises a KeyError.
	"""
	with getTableConn() as conn:
		res = list(conn.query("SELECT value FROM dc.metastore WHERE"
			" key=%(key)s", {"key": key}))
		if not res:
			raise KeyError(key)
		return res[0][0]


@contextlib.contextmanager
def savepointOn(connection):
	"""sets up a section protected by a savepoint that will be released
	after use.

	If an exception happens in the controlled section, the connection
	will be rolled back to the savepoint.
	"""
	savepointName = "auto_%s"%(random.randint(0, 2147483647))
	connection.execute("SAVEPOINT %s"%savepointName)
	try:
		yield
		connection.execute("RELEASE SAVEPOINT %s"%savepointName)
	except:
		connection.execute("ROLLBACK TO SAVEPOINT %s"%savepointName)
		connection.execute("RELEASE SAVEPOINT %s"%savepointName)
		raise


@contextlib.contextmanager
def connectionConfiguration(conn, isLocal=True, timeout=None, **runtimeVals):
	"""A context manager setting and resetting runtimeVals in conn.

	You pass just pass keyword arguments corresponding to postgres runtime
	configuration items (as in SET and SHOW).  The manager obtains their previous
	values and restores them before exiting.

	When the controlled body is terminated by a DBError, the settings 
	are not reset.

	If you set isLocal=False, this works for autocommitted connections,
	too (and in that case the reset of the run-time parameters will
	be attempted even when DBErrors occurred.

	Since it's so frequent, you can pass timeout to give a statement_timeout
	in seconds.
	"""
	cursor = conn.cursor()

	if timeout is not None:
		runtimeVals["statement_timeout"] = int(float(timeout)*1000)

	oldVals = {}
	for parName, parVal in runtimeVals.iteritems():
		parVal = str(parVal)
		cursor.execute("SELECT current_setting(%(parName)s)", locals())
		oldVals[parName] = list(cursor)[0][0]
		cursor.execute(
			"SELECT set_config(%(parName)s, %(parVal)s, %(isLocal)s)", locals())
	cursor.close()

	def resetAll(isLocal):
		cursor = conn.cursor()
		for parName, parVal in oldVals.iteritems():
			cursor.execute(
				"SELECT set_config(%(parName)s, %(parVal)s, %(isLocal)s)", 
				locals())
		cursor.close()
		
	try:
		yield
	except DBError: # the connection probably is dirty, do not try to reset
		if not isLocal:
			resetAll(isLocal)
		raise
	except:
		resetAll(isLocal)
		raise
	resetAll(isLocal)


def _initPsycopg(conn):
# collect all DB setup in this function.  XXX TODO: in particular, the
# Box mess from coords (if we still want it)
	global _PSYCOPG_INITED
	from gavo.utils import pgsphere
	pgsphere.preparePgSphere(conn)
	_PSYCOPG_INITED = True


class CustomConnectionPool(psycopg2.pool.ThreadedConnectionPool):
	"""A threaded connection pool that returns connections made via
	profileName.
	"""
	def __init__(self, minconn, maxconn, profileName, autocommitted=True):
# make sure no additional arguments come in, since we don't
# support them.
		self.profileName = profileName
		self.autocommitted = autocommitted
		psycopg2.pool.ThreadedConnectionPool.__init__(
			self, minconn, maxconn)

	def _connect(self, key=None):
		"""creates a new trustedquery connection and assigns it to
		key if not None.

		This is an implementation detail of psycopg2's connection
		pools.
		"""
		conn = getDBConnection(self.profileName)

		if self.autocommitted:
			try:
				conn.set_session(
					autocommit=True, readonly=True)
			except AttributeError:
				# fallback for old psycopg2
				conn.set_isolation_level(
					psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
			except ProgrammingError:
				utils.sendUIEvent("Warning", "Uncommitted transaction escaped; please"
					" investigate and fix")
				conn.commit()


		if key is not None:
			self._used[key] = conn
			self._rused[id(conn)] = key
		else:
			self._pool.append(conn)
		return conn


def _cleanupAfterDBError(ex, conn, pool, poolLock):
	"""removes conn from pool after an error occurred.

	This is a helper for getConnFromPool below.
	"""
	if isinstance(ex, OperationalError) and conn.fileno()==-1: 
		# this is probably a db server restart.  Invalidate all connections
		# immediately.
		utils.sendUIEvent("Warning", "Suspecting a database restart."
			"  Discarding old connection pool, making a new one.")
		with poolLock:
			if pool:
				pool[0].closeall()
				pool.pop()
				return

	# Make sure the connection is closed; something bad happened
	# in it, so we don't want to re-use it
	try:
		pool[0].putconn(conn, close=True)
	except InterfaceError:  
		# Connection already closed
		pass
	except Exception, msg:
		utils.sendUIEvent("Error", 
			"Disaster: %s while force-closing connection"%msg)


def _makeConnectionManager(profileName, minConn=5, maxConn=20,
		autocommitted=True):
	"""returns a context manager for a connection pool for profileName
	connections.
	"""
	pool = []
	poolLock = threading.Lock()

	def getConnFromPool():
		# we delay pool creation since these functions are built during
		# sqlsupport import.  We probably don't have profiles ready
		# at that point.
		if not pool:
			with poolLock:
				pool.append(CustomConnectionPool(minConn, maxConn, profileName,
					autocommitted))

		conn = pool[0].getconn()
		try:
			yield conn
		except Exception, ex:
			# controlled block bombed out, do error handling
			_cleanupAfterDBError(ex, conn, pool, poolLock)
			raise

		else:
			# no exception raised, commit if not autocommitted
			if not autocommitted:
				conn.commit()


		try:
			pool[0].putconn(conn, close=conn.closed)
		except InterfaceError:
			# Connection already closed
			pass

	return contextlib.contextmanager(getConnFromPool)


getUntrustedConn = _makeConnectionManager("untrustedquery")
getTableConn = _makeConnectionManager("trustedquery")
getAdminConn = _makeConnectionManager("admin")

getWritableUntrustedConn = _makeConnectionManager("untrustedquery", 
	autocommitted=False)
getWritableTableConn = _makeConnectionManager("trustedquery", 
	autocommitted=False)
getWritableAdminConn = _makeConnectionManager("admin", 
	autocommitted=False)
