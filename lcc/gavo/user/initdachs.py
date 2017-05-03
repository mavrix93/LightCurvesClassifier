"""
Initial setup for the file system hierarchy.

This module is supposed to create as much of the DaCHS file system environment
as possible.  Take care to give sensible error messages -- much can go wrong
here, and it's nice if the user has a way to figure out what's wrong.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from __future__ import with_statement

import datetime
import os
import sys
import textwrap
import warnings

import psycopg2

from gavo import base
from gavo import utils


def bailOut(msg, hint=None):
	sys.stderr.write("*** Error: %s\n\n"%msg)
	if hint is not None:
		sys.stderr.write(textwrap.fill(hint)+"\n")
	sys.exit(1)


def unindentString(s):
	return "\n".join(s.strip() for s in s.split("\n"))+"\n"


def makeRoot():
	rootDir = base.getConfig("rootDir")
	if os.path.isdir(rootDir):
		return
	try:
		os.makedirs(rootDir)
	except os.error:
		bailOut("Cannot create root directory %s."%rootDir,
			"This usually means that the current user has insufficient privileges"
			" to write to the parent directory.  To fix this, either have rootDir"
			" somewhere you can write to (edit /etc/gavorc) or create the directory"
			" as root and grant it to your user id.")


def makeDirVerbose(path, setGroupTo, makeWritable):
	if not os.path.isdir(path):
		try:
			os.makedirs(path)
		except os.error, err:
			bailOut("Could not create directory %s (%s)"%(
				path, err))  # add hints
		except Exception, msg:
			bailOut("Could not create directory %s (%s)"%(
				path, msg))
	if setGroupTo is not None:
		stats = os.stat(path)
		if stats.st_mode&0060!=060 or stats.st_gid!=setGroupTo:
			try:
				os.chown(path, -1, setGroupTo)
				if makeWritable:
					os.chmod(path, stats.st_mode | 0060)
			except Exception, msg:
				bailOut("Cannot set %s to group ownership %s, group writable"%(
					path, setGroupTo),
					hint="Certain directories must be writable by multiple user ids."
					"  They must therefore belong to the group %s and be group"
					" writeable.  The attempt to make sure that's so just failed"
					" with the error message %s."
					"  Either grant the directory in question to yourself, or"
					" fix permissions manually.  If you own the directory and"
					" sill see permission errors, try 'newgrp %s'"%(
						base.getConfig("group"), msg, base.getConfig("group")))


_GAVO_WRITABLE_DIRS = set([
	"stateDir",
	"cacheDir",
	"logDir",
	"tempDir",
	"uwsWD",])


def makeDirForConfig(configKey, gavoGrpId):
	path = base.getConfig(configKey)
	makeDirVerbose(path, gavoGrpId, configKey in _GAVO_WRITABLE_DIRS)


def makeDefaultMeta():
	destPath = os.path.join(base.getConfig("configDir"), "defaultmeta.txt")
	if os.path.exists(destPath):
		return
	rawData = r"""publisher: Fill Out
		publisherID: ivo://x-unregistred
		contact.name: Fill Out
		contact.address: Ordinary street address.
		contact.email: Your email address
		contact.telephone: Delete this line if you don't want to give it
		creator.name: Could be same as contact.name
		creator.logo: a URL pointing to a small png

		_noresultwarning: Your query did not match any data.

		authority.creationDate: %s
		authority.title: Untitled data center
		authority.shortName: DaCHS standin
		authority.description: This should be a relatively terse \
			description of what you clam authority for.
		authority.referenceURL: (your DC's "contact" page, presumably)
		authority.managingOrg: ivo://x-unregistred/org
		organization.title: Unconfigured organization
		organization.description: Briefly describe the organization you're \
			running the dc for here.
		organization.referenceURL: http://your.institution/home

		site.description: This should be a relatively terse \
			description of your data center.  You must give sensible values \
			for all authority.* things before publishing your registry endpoint.
		"""%(datetime.datetime.utcnow())
	with open(destPath, "w") as f:
		f.write(unindentString(rawData))
	
	# load new new default meta
	from gavo.base import config
	config.makeFallbackMeta()


def prepareWeb(groupId):
	makeDirVerbose(os.path.join(base.getConfig("webDir"), "nv_static"),
		groupId, False)


def _genPW():
	"""returns a random string that may be suitable as a database password.

	The entropy of the generated passwords should be close to 160 bits, so
	the passwords themselves would probably not be a major issue.  Of course,
	within DaCHS they are stored in the file system in clear text...
	"""
	return os.urandom(20).encode("base64")


def makeProfiles(dsn, userPrefix=""):
	"""writes profiles with made-up passwords to DaCHS' config dir.

	This will mess everything up when the users already exist.  We
	should probably provide an option to drop standard users.

	userPrefix is mainly for the test infrastructure.
	"""
	profilePath = base.getConfig("configDir")
	dsnContent = ["database = %s"%(dsn.parsed["dbname"])]
	if "host" in dsn.parsed:
		dsnContent.append("host = %s"%dsn.parsed["host"])
	else:
		dsnContent.append("host = localhost")
	if "port" in dsn.parsed:
		dsnContent.append("port = %s"%dsn.parsed["port"])
	else:
		dsnContent.append("port = 5432")

	for fName, content in [
			("dsn", "\n".join(dsnContent)+"\n"),
			("feed", "include dsn\nuser = %sgavoadmin\npassword = %s\n"%(
				userPrefix, _genPW())),
			("trustedquery", "include dsn\nuser = %sgavo\npassword = %s\n"%(
				userPrefix, _genPW())),
			("untrustedquery", "include dsn\nuser = %suntrusted\npassword = %s\n"%(
				userPrefix, _genPW())),]:
		destPath = os.path.join(profilePath, fName)
		if not os.path.exists(destPath):
			with open(destPath, "w") as f:
				f.write(content)


def createFSHierarchy(dsn, userPrefix=""):
	"""creates the directories required by DaCHS.

	userPrefix is for use of the test infrastructure.
	"""
	makeRoot()
	grpId = base.getGroupId()
	for configKey in ["configDir", "inputsDir", "cacheDir", "logDir", 
			"tempDir", "webDir", "stateDir"]:
		makeDirForConfig(configKey, grpId)
	makeDirVerbose(os.path.join(base.getConfig("inputsDir"), "__system"),
		grpId, False)
	makeDefaultMeta()
	makeProfiles(dsn, userPrefix)
	prepareWeb(grpId)


###################### DB interface
# This doesn't use much of sqlsupport since the roles are just being
# created and some of the operations may not be available for non-supervisors.

class DSN(object):
	"""a psycopg-style DSN, both parsed and unparsed.
	"""
	def __init__(self, dsn):
		self.full = dsn
		self._parse()
		self._validate()

	_knownKeys = set(["dbname", "user", "password", "host", "port", "sslmode"])

	def _validate(self):
		for key in self.parsed:
			if key not in self._knownKeys:
				sys.stderr.write("Unknown DSN key %s will get lost in profiles."%(
					key))
	
	def _parse(self):
		if "=" in self.full:
			self.parsed = utils.parseKVLine(self.full)
		else:
			self.parsed = {"dbname": self.full}
			self.full = utils.makeKVLine(self.parsed)


def _execDB(conn, query, args={}):
	"""returns the result of running query with args through conn.

	No transaction management is being done here.
	"""
	cursor = conn.cursor()
	cursor.execute(query, args)
	return list(cursor)


def _roleExists(conn, roleName):
	return _execDB(conn, 
		"SELECT rolname FROM pg_roles WHERE rolname=%(rolname)s",
		{"rolname": roleName})


def _createRoleFromProfile(conn, profile, privileges):
	cursor = conn.cursor()
	try:
		verb = "CREATE"
		if _roleExists(conn, profile.user):
			verb = "ALTER"
		cursor.execute(
			"%s ROLE %s PASSWORD %%(password)s %s LOGIN"%(
				verb, profile.user, privileges), {
			"password": profile.password,})
		conn.commit()
	except:
		warnings.warn("Could not create role %s (see db server log)"%
			profile.user)
		conn.rollback()
		

def _createRoles(dsn):
	"""creates the roles for the DaCHS profiles admin, trustedquery
	and untrustedquery.
	"""
	from gavo.base import config

	conn = psycopg2.connect(dsn.full)
	for profileName, privileges in [
			("admin", "CREATEROLE"),
			("trustedquery", ""),
			("untrustedquery", "")]:
		_createRoleFromProfile(conn, 
			config.getDBProfile(profileName),
			privileges)

	adminProfile = config.getDBProfile("admin")
	cursor = conn.cursor()
	cursor.execute("GRANT ALL ON DATABASE %s TO %s"%(dsn.parsed["dbname"], 
		adminProfile.user))
	conn.commit()


def _getServerScriptPath(conn):
	"""returns the path where a local postgres server would store its
	contrib scripts.

	This is probably Debian specific.  It's used by the the extension
	script upload.
	"""
	from gavo.base import sqlsupport
	version = sqlsupport.parseBannerString(
		_execDB(conn, "SELECT version()")[0][0])
	name = "/usr/share/postgresql/%s/contrib"%version
	if os.path.isdir(name):
		return name
	name = "/usr/share/postgresql/contrib"
# Try others here?  Which?
	return name


def _readDBScript(conn, scriptPath, sourceName, procName):
	"""tries to execute the sql script in scriptPath within conn.

	sourceName is some user-targeted indicator what package the script
	comes from, procName the name of a procedure left by the script
	so we don't run the script again when it's already run.
	"""
	if not os.path.exists(scriptPath):
		warnings.warn("SQL script file for %s not found.  There are many"
			" reasons why that may be ok, but unless you know what you are"
			" doing, you probably should install the corresponding postgres"
			" extension."%scriptPath)
	from gavo.rscdef import scripting

	cursor = conn.cursor()
	if _execDB(conn, "SELECT * FROM pg_proc WHERE proname=%(procName)s",
			{"procName": procName}):
		# script has already run
		return

	try:
		for statement in scripting.getSQLScriptGrammar().parseString(
				open(scriptPath).read()):
			cursor.execute(statement)
	except:
		import traceback
		traceback.print_exc()
		conn.rollback()
		warnings.warn("SQL script file %s failed.  Try running manually"
			" using psql.  While it hasn't run, the %s extension is not"
			" available."%(scriptPath, sourceName))
	else:
		conn.commit()


def _doLocalSetup(dsn):
	"""executes some commands that need to be executed with superuser
	privileges.
	"""
# When adding stuff here, fix docs/install.rstx, "Owner-only db setup"
	conn = psycopg2.connect(dsn.full)
	for statement in [
			"CREATE OR REPLACE LANGUAGE plpgsql"]:
		cursor = conn.cursor()
		try:
			cursor.execute(statement)
		except psycopg2.DatabaseError, msg:
			warnings.warn("SQL statement '%s' failed (%s); continuing."%(
				statement, msg))
			conn.rollback()
		else:
			conn.commit()


def _readDBScripts(dsn):
	"""loads definitions of pgsphere, q3c and similar into the DB.

	This only works for local installations, and the script location
	is more or less hardcoded (Debian and SuSE work, at least).
	"""
	conn = psycopg2.connect(dsn.full)
	scriptPath = _getServerScriptPath(conn)
	for extScript, pkgName, procName in [
			("pg_sphere.sql", "pgSphere", "spoint_in"),
			("q3c.sql", "q3c", "q3c_ang2ipix")]:
		_readDBScript(conn, 
			os.path.join(scriptPath, extScript), 
			pkgName,
			procName)


def _importBasicResources():
	from gavo import rsc
	from gavo.user import importing

	for rdId in ["//dc_tables", "//services", "//users", 
			"//uws", "//adql", "//tap", "//products", "//obscore",
			"//datalink"]:
		base.ui.notifyInfo("Importing %s"%rdId)
		importing.process(rsc.getParseOptions(), [rdId])


def initDB(dsn):
	"""creates users and tables expected by DaCHS in the database described
	by the DSN dsn.

	Connecting with dsn must give you superuser privileges.
	"""
	_createRoles(dsn)
	_doLocalSetup(dsn)
	_readDBScripts(dsn)
	_importBasicResources()


def parseCommandLine():
	from gavo.imp import argparse
	parser = argparse.ArgumentParser(description="Create or update DaCHS'"
		" file system and database environment.")
	parser.add_argument("-d", "--dsn", help="DSN to use to connect to"
		" the future DaCHS database.  The DSN must let DaCHS connect"
		" to the DB as an administrator.  dbname, host, and port"
		" get copied to the profile, if given.  The DSN looks roughly like"
		' "host=foo.bar user=admin password=secret". If you followed the'
		" installation instructions, you don't need this option.",
		action="store", type=str, dest="dsn", default="gavo")
	parser.add_argument("--nodb", help="Inhibit initialization of the"
		" database (you may want to use this when refreshing the file system"
		" hierarchcy)", action="store_false", dest="initDB")
	return parser.parse_args()


def main():
	"""initializes the DaCHS environment (where that's not already done).
	"""
	opts = parseCommandLine()
	dsn = DSN(opts.dsn)
	createFSHierarchy(dsn)
	if opts.initDB:
		initDB(dsn)
