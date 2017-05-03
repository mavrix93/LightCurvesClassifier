"""
Stuff dealing with the upgrade of the database schema.

From software version 0.8.2 on, there is a dc.metastore table with a key
schemaversion.  Each change in the central schema increases the value
(interpreted as an integer) by one, and this module will contain a 
corresponding upgrader.

An upgrader inherits form the Upgrader class.  See there for more details.

This module contains the current schemaversion expected by the software; gavo
upgrade does everything required to bring the what's in the database in sync
with the code (or so I hope).
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import sys

from gavo import base
from gavo import rsc
from gavo import rscdesc  #noflake: for cache registration
from gavo import utils


CURRENT_SCHEMAVERSION = 11


class AnnotatedString(str):
	"""a string with an annotation.
	
	This is (optionally) used to hold SQL statements here; the annotation
	is shown to the user instead of the naked statement when present.
	"""
	def __new__(cls, content, annotation):
		res = str.__new__(cls, content)
		res.annotation = annotation
		return res


def showProgress(msg):
	"""outputs msg to stdout without lf "immediately".
	"""
	sys.stdout.write(msg)
	sys.stdout.flush()


def getDBSchemaVersion():
	"""returns the schemaversion given in the database.

	This will return -1 if no schemaversion is declared.
	"""
	try:
		return int(base.getDBMeta("schemaversion"))
	except (KeyError, base.DBError):
		return -1


class Upgrader(object):
	"""A specification to upgrade from some schema version to another schema 
	version.

	Upgraders live as uninstanciated classes.  Their version attribute gives the
	version their instructions update *from*; their destination version
	therefore is version+1.

	Each upgrader has attributes named u_<seqno>_<something>.  These can
	be either strings, which are then directly executed in the database,
	or class methods, which will be called with a connection argument.  You 
	must not commit this connection.  You must not swallow exceptions
	that have left the connection unready (i.e., require a rollback).

	Note that if you run rsc.makeData, you MUST pass both 
	connection=connection and runCommit=False in order to avoid messing
	people's lives up.

	The individual upgrader classmethods will be run in the sequence
	given by the sequence number.

	The updaters should have 1-line docstrings explaining what they do.

	The update of the schemaversion is done automatically, you don't
	need to worry about it.
	"""
	version = None

	@classmethod
	def updateSchemaversion(cls, connection):
# no docstring, we output our info ourselves
		showProgress("> update schemaversion to %s..."%(cls.version+1))
		base.setDBMeta(connection, "schemaversion", cls.version+1)

	@classmethod
	def iterStatements(cls):
		"""returns strings and classmethods that, in all, perform the necessary
		upgrade.
		"""
		for cmdAttr in (s for s in sorted(dir(cls)) if s.startswith("u_")):
			yield getattr(cls, cmdAttr)
		yield cls.updateSchemaversion


class To0Upgrader(Upgrader):
	"""This is executed when there's no schema version defined in the database.

	The assumption is that the database reflects the status of 0.8, so
	it adds the author column in dc.services if necessary (which it's
	not if the software has been updated to 0.8.1).
	"""
	version = -1

	@classmethod
	def u_000_addauthor(cls, connection):
		"""add an author column to dc.services if necessary"""
		if "authors" in list(connection.queryToDicts(
				"SELECT * FROM dc.resources LIMIT 1"))[0]:
			return
		connection.query("alter table dc.resources add column authors")
		for sourceRD, resId in connection.query("select sourcrd, resid"
				" from dc.resources"):
			try:
				res = base.getRD(sourceRD).getById(resId)
				authors = "; ".join(m.getContent("text") #noflake: used through locals
					for m in res.iterMeta("creator.name", propagate=True))
			except: 
				# don't worry if fetching authors fails; people will notice...
				pass
			else:
				connection.query("update dc.resources set authors=%(authors)s"
					" where resid=%(resId)s and sourcerd=%(sourceRD)s",
					locals())

	@classmethod
	def u_010_makeMetastore(cls, connection):
		"""create the meta store"""
		td = base.caches.getRD("//dc_tables").getById("metastore")
		rsc.TableForDef(td, create=True, connection=connection)


class To1Upgrader(Upgrader):
	version = 0

	@classmethod
	def u_000_update_funcs(cls, connection):
		"""update GAVO server-side functions"""
		rsc.makeData(base.caches.getRD("//adql").getById("make_udfs"),
			connection=connection, runCommit=False)


class To2Upgrader(Upgrader):
	version = 1

	@classmethod
	def _upgradeTable(cls, td, colName, connection):
		col = td.getColumnByName(colName)
		if not col.type=='double precision' or not col.xtype=='mjd':
			# this is not done via the mixin, it appears; give up
			return

		showProgress(td.getQName()+", ")
		connection.execute("ALTER TABLE %s ALTER COLUMN %s"
			" SET DATA TYPE DOUBLE PRECISION USING ts_to_mjd(%s)"%
			(td.getQName(), colName, colName))
		rsc.TableForDef(td, connection=connection, create=False
			).updateMeta()


	@classmethod
	def u_000_siapDateObsToMJD(cls, connection):
		"""change SIAP and SSAP dateObs columns to MJD"""
		mth = base.caches.getMTH(None)
		connection.execute("DROP VIEW IF EXISTS ivoa.obscore")

		for tableName, fieldName in connection.query(
				"SELECT tableName, fieldName FROM dc.columnmeta"
				" WHERE type='timestamp' AND"
				" fieldName LIKE '%%dateObs'"):
			cls._upgradeTable(mth.getTableDefForTable(tableName), fieldName,
				connection)

		from gavo import rsc
		rsc.makeData(base.caches.getRD("//obscore").getById("create"),
			connection=connection, runCommit=False)


class To3Upgrader(Upgrader):
	version = 2

	@classmethod
	def u_000_tapSchema(cls, connection):
		"""add supportedmodels table to tap_schema"""
		rsc.makeData(base.caches.getRD("//tap").getById("createSchema"),
			connection=connection, runCommit=False)
	
	@classmethod
	def u_010_declareObscoreModel(cls, connection):
		"""declare obscore data model if the obscore table is present"""
		if list(connection.query(
				"select * from dc.tablemeta where tablename='ivoa.ObsCore'")):
			from gavo.protocols import tap
			rd = base.caches.getRD("//obscore")
			tap.publishToTAP(rd, connection)
		else:
			showProgress(" (not present)")


class To4Upgrader(Upgrader):
	version = 3

	@classmethod
	def u_000_adqlfunctions(cls, connection):
		"""update ADQL GAVO-defined functions for the postgres planner's benefit"""
		rsc.makeData(base.caches.getRD("//adql").getById("make_udfs"),
			connection=connection, runCommit=False)


class To5Upgrader(Upgrader):
	version = 4
	
	@classmethod
	def u_000_updateObscore(cls, connection):
		"""update obscore to work even when the table is empty"""
		rsc.TableForDef(base.caches.getRD("//obscore").getById("emptyobscore"),
			connection=connection, create=True)
		rsc.makeData(base.caches.getRD("//obscore").getById("create"),
			connection=connection, runCommit=False)


class To6Upgrader(Upgrader):
	version = 5
	
	@classmethod
	def u_000_remetaObscore(cls, connection):
		"""update obscore metadata to fix the erroneous id"""
		rsc.makeData(base.caches.getRD("//obscore").getById("create"),
			connection=connection, runCommit=False, 
			parseOptions=rsc.getParseOptions(metaOnly=True))
	
	u_010_addPreviewColumn = ("ALTER TABLE dc.products ADD COLUMN"
		" preview TEXT DEFAULT 'AUTO'")
	u_020_dedefaultPreviewColumn = ("ALTER TABLE dc.products ALTER COLUMN"
		" preview DROP DEFAULT")
	u_30_addDatalinkColumn = ("ALTER TABLE dc.products ADD COLUMN"
		" datalink TEXT")


class To7Upgrader(Upgrader):
	version = 6

	u_010_addPreviewMIMEColumn = ("ALTER TABLE dc.products ADD COLUMN"
		" preview_mime TEXT")


class To8Upgrader(Upgrader):
	version = 7
	u_010_removeColumnsMeta = ("DROP TABLE dc.columnmeta")


class To9Upgrader(Upgrader):
	version = 8
	u_010_chuckADQLPrefix = AnnotatedString("UPDATE TAP_SCHEMA.columns"
			" SET datatype=substring(datatype from 6)"
			" WHERE datatype LIKE 'adql:%%'",
		"Remove adql: prefix in TAP_SCHEMA.columns.datatype")
	u_020_setSize1OnAtoms = AnnotatedString("UPDATE tap_schema.columns"
		" SET \"size\"=1 WHERE NOT datatype LIKE '%%(*)'",
		"Set size=1 in TAP_SCHEMA.columns for atomic types")
	u_030_removeArrayMarkInText = AnnotatedString("UPDATE tap_schema.columns"
		" SET datatype=replace(datatype, '(*)', '') WHERE datatype LIKE '%%(*)'",
		"Turn VARCHAR(*) into simple VARCHAR (size=NULL already set for those)")


class To10Upgrader(Upgrader):
	version = 9

	@classmethod
	def u_000_dropADQLExamples(cls, connection):
		"""drop old TAP examples tables (gone to _examples meta)"""
		from gavo.user import dropping
		dropping._do_dropTable("tap_schema.examples", connection)
	
	@classmethod
	def u_010_createDLAsyncTable(cls, connection):
		"""import job table for async datalink"""
		from gavo import rsc
		rsc.makeData(base.caches.getRD("//datalink").getById("import"),
			connection=connection, runCommit=False)


class To11Upgrader(Upgrader):
	version = 10

	@classmethod
	def u_000_findMixedinTables(cls, connection):
		"""inform about tables with non-trivial mixins."""
		# in reality, the mixins that really give us a headache here
		# are the ones mixin in products.  Hence, we simply look
		# for tables that have both accref and embargo; that's
		# probably a certain indication.

		print ("\n!! Important: column sequences"
			" of tables with some mixins have changed.")
		print "!! If this affects you, below commands are shown that will re-import"
		print "!! the affected tables.  Some services on top of these tables may"
		print "!! be *broken* until these commands have run."
		print "!! Sorry for this inconvenience; we hope it won't happen again.\n"

		from gavo import registry
		for rdId in registry.findAllRDs():
			if rdId.startswith("__system"):
				continue
			
			try:
				rd = base.caches.getRD(rdId)
			except:
				# ignore broken RDs -- services there are broken anyway
				continue

			ids = set()

			for td in rd.tables:
				try:
					td.getColumnByName("accref") and td.getColumnByName("embargo")
				except base.NotFoundError:
					continue   # table not affected
				else:
					
					if not rsc.TableForDef(td, connection=connection, create=False
							).exists():
						continue

					# table needs re-importing, see if you can find a correponsing 
					# data element
					for dd in rd.dds:
						for make in dd.makes:
							if make.table==td:
								ids.add(dd.id)
			if ids:
				print "gavo imp '%s' %s"%(rd.sourceId,
					" ".join("'%s'"%id for id in ids))

		sys.stderr.write("\nEnd of scan of mixin-affected tables...")


def iterStatements(startVersion, endVersion=CURRENT_SCHEMAVERSION, 
		upgraders=None):
	"""yields all upgraders from startVersion to endVersion in sequence.
	"""
	toRun = []
	for upgrader in utils.iterDerivedClasses(Upgrader, 
			upgraders or globals().values()):
		if startVersion<=upgrader.version<endVersion:
			toRun.append(upgrader)
	toRun.sort(key=lambda upgrader:upgrader.version)
	for upgrader in toRun:
		for statement in upgrader.iterStatements():
			yield statement


def upgrade(forceDBVersion=None, dryRun=False):
	"""runs all updates necessary to bring a database to the
	CURRENT_SCHEMAVERSION.

	Everything is run in one transaction.  Errors lead to the rollback of
	the whole thing.
	"""
	if forceDBVersion is None:
		startVersion = getDBSchemaVersion()
	else:
		startVersion = forceDBVersion

	if startVersion==CURRENT_SCHEMAVERSION:
		return

	with base.getWritableAdminConn() as conn:
		for statement in iterStatements(startVersion, CURRENT_SCHEMAVERSION):
			if callable(statement):
				if statement.__doc__:
					showProgress("> %s..."%statement.__doc__)
				# if no docstring is present, we assume the function will output
				# custom user feedback
				statement(conn)
			else:
				showProgress("> "+getattr(statement, "annotation",
					"executing %s"%utils.makeEllipsis(statement, 60))+"... ")
				conn.execute(statement)
			showProgress(" ok\n")
		if dryRun:
			conn.rollback()
		conn.commit()


def parseCommandLine():
	from gavo.imp import argparse
	parser = argparse.ArgumentParser()
	parser.add_argument("--force-dbversion", help="assume this as the"
		" database's schema version.  If you don't develop DaCHS, you"
		" almost certainly should stay clear of this flag", type=int,
		dest="forceDBVersion", default=None)
	parser.add_argument("--dry-run", help="do not commit at the end of"
		" the upgrade; this will not change anything in the database",
		dest="dryRun", action="store_true")
	return parser.parse_args()


def main():
	args = parseCommandLine()
	upgrade(args.forceDBVersion, args.dryRun)
