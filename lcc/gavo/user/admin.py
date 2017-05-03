"""
DC administration interface.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import os
import sys

from gavo import base
from gavo import rscdesc  #noflake: for cache registration
from gavo.base import sqlsupport
from gavo.user.common import Arg, exposedFunction, makeParser
from gavo.protocols import uws


class ArgError(base.Error):
	pass


@exposedFunction([
	Arg("user", help="the user name"),
	Arg("password", help="a password for the user"),
	Arg("remarks", help="optional remarks", 
		default="", nargs='?')],
	help="add a user/password pair and a matching group to the DC server")
def adduser(querier, args):
	try:
		querier.query("INSERT INTO dc.users (username, password, remarks)"
			" VALUES (%(user)s, %(password)s, %(remarks)s)", args.__dict__)
	except base.IntegrityError:
		raise base.ui.logOldExc(ArgError("User %s already exists."
			"  Use 'changeuser' command to edit."%args.user))
	querier.query("INSERT INTO dc.groups (username, groupname)"
		" VALUES (%(user)s, %(user)s)", args.__dict__)


@exposedFunction([
	Arg("user", help="the user name to remove")],
	help="remove a user from the DC server")
def deluser(querier, args):
	c = querier.query("DELETE FROM dc.users WHERE username=%(user)s",
		args.__dict__)
	rowsAffected = c.rowcount
	c = querier.query("DELETE FROM dc.groups WHERE username=%(user)s",
		args.__dict__)
	rowsAffected += c.rowcount
	if not rowsAffected:
		sys.stderr.write("Warning: No rows deleted while deleting user %s\n"%
			args.user)


@exposedFunction([
	Arg("user", help="the user name"),
	Arg("password", help="a password for the user"),
	Arg("remarks", help="optional remarks", 
		default="", nargs='?')],
	help="change remarks and/or password for a DC user")
def changeuser(querier, args):
		if args.remarks is None:
			c = querier.query("UPDATE dc.users SET password=%(password)s"
			" WHERE username=%(user)s", args.__dict__)
		else:
			c = querier.query("UPDATE dc.users SET password=%(password)s,"
			" remarks=%(remarks)s WHERE username=%(user)s", args.__dict__)
		if not c.rowcount:
			sys.stderr.write("Warning: No rows changed for user %s\n"%args.user)


@exposedFunction([
	Arg("user", help="a user name"),
	Arg("group", help="the group to add the user to")],
	help="add a user to a group")
def addtogroup(querier, args):
	try:
		querier.query("INSERT INTO dc.groups (username, groupname)"
			" VALUES (%(user)s, %(group)s)", args.__dict__)
	except sqlsupport.IntegrityError:
		raise base.ui.logOldExc(ArgError("User %s doesn't exist."%args.user))


@exposedFunction([
	Arg("user", help="a user name"),
	Arg("group", help="the group to remove the user from")],
	help="remove a user from a group")
def delfromgroup(querier, args):
	c = querier.query("DELETE FROM dc.groups WHERE groupname=%(group)s"
		" and username=%(user)s", args.__dict__)
	if not c.rowcount:
		sys.stderr.write("Warning: No rows deleted while deleting user"
			" %s from group %s\n"%(args.user, args.group))


@exposedFunction(help="list users known to the DC")
def listusers(querier, args):
	data = querier.query("SELECT username, groupname, remarks"
		" FROM dc.users NATURAL JOIN dc.groups ORDER BY username").fetchall()
	curUser = None
	for user, group, remark in data:
		if user!=curUser:
			print "\n%s (%s) --"%(user, remark),
			curUser = user
		print group,
	print


@exposedFunction([
	Arg("-f", help="also remove all jobs in ERROR and ABORTED states (only use"
		" if you are sure what you are doing).", action="store_true",
		dest="includeFailed"),
	Arg("-p", help="also remove all jobs in PENDING states (only use"
		" if you are sure what you are doing).", action="store_true",
		dest="includeForgotten"),
	Arg("--all", help="remove all jobs (this is extremely unfriendly."
		"  Don't use this on public UWSes)", action="store_true",
		dest="includeAll"),
	Arg("--nuke-completed", help="also remove COMPLETEd jobs (this is"
		" unfriendly.  Don't do this on public UWSes).", action="store_true",
		dest="includeCompleted"),],
	help="remove expired UWS jobs")
def cleantap(querier, args):
	from gavo.protocols import tap
	tap.workerSystem.cleanupJobsTable(includeFailed=args.includeFailed,
		includeCompleted=args.includeCompleted,
		includeAll=args.includeAll,
		includeForgotten=args.includeForgotten)


@exposedFunction([
	Arg("jobId", help="id of the job to abort"),
	Arg("helpMsg", help="A helpful message to add to the abort message")],
	help="manually abort a TAP job and send some message to a user")
def tapabort(querier, args):
	from gavo.protocols import tap

	tap.workerSystem.changeToPhase(args.jobId, uws.ERROR, 
			"Job aborted by an administrator, probably because the query\n"
			" should be written differently to be less of a resource hog.\n"
			"  Here's what the administrator had to say:\n\n"+args.helpMsg+
			"\n\nIf you have further questions, just send a mail to "+
			base.getMetaText(base.caches.getRD("//tap").getById("run"), 
				"contact.email"))


@exposedFunction(help="Re-import column information from all RDs"
	" (incl. TAP_SCHEMA; like gavo imp -m <all rds>)")
def allcols(querier, args):
	from gavo import registry
	from gavo import rsc
	from gavo.protocols import tap

	for rdId in registry.findAllRDs():
		rd = base.caches.getRD(rdId)
		tap.unpublishFromTAP(rd, querier.connection)
		for dd in rd:
			rsc.Data.create(dd, connection=querier.connection).updateMeta()
		tap.publishToTAP(rd, querier.connection)


@exposedFunction([Arg(help="identifier of the deleted service",
		dest="svcId")],
	help="Declare an identifier as deleted (for when"
	" you've removed the RD but the identifier still floats on"
	" some registries)")
def declaredel(querier, args):
	import datetime

	from gavo import registry
	from gavo import rsc

	authority, path = registry.parseIdentifier(args.svcId)
	if authority!=base.getConfig("ivoa", "authority"):
		raise base.ReportableError("You can only declare ivo ids from your"
			" own authority as deleted.")
	idParts = path.split("/")
	svcsRD = base.caches.getRD("//services")

	# mark in resources table
	resTable = rsc.TableForDef(svcsRD.getById("resources"),
		connection=querier.connection)
	newRow = resTable.tableDef.getDefaults()
	newRow["sourceRD"] = "/".join(idParts[:-1])
	newRow["resId"] = idParts[-1]
	newRow["deleted"] = True
	newRow["title"] = "Ex "+args.svcId
	newRow["dateUpdated"] = newRow["recTimestamp"] = datetime.datetime.utcnow()
	resTable.addRow(newRow)

	# mark in sets table
	resTable = rsc.TableForDef(svcsRD.getById("sets"),
		connection=querier.connection)
	newRow = resTable.tableDef.getDefaults()
	newRow["sourceRD"] = "/".join(idParts[:-1])
	newRow["renderer"] = "null"
	newRow["resId"] = idParts[-1]
	newRow["setName"] = "ivo_managed"
	newRow["deleted"] = True
	resTable.addRow(newRow)


@exposedFunction([Arg(help="rd#table-id of the table containing the"
	" products that should get cached previews", dest="tableId"),
	Arg("-w", type=str,
		help="width to compute the preview for", dest="width", default="200"),],
	help="Precompute previews for the product interface columns in a table.")
def cacheprev(querier, args):
	from gavo import api
	from gavo.web.productrender import PreviewCacheManager
	from twisted.internet import reactor

	basePath = base.getConfig("inputsDir")
	td = base.resolveId(None, args.tableId)
	table = api.TableForDef(td, connection=querier.connection)
	select = [td.getColumnByName("accref"), td.getColumnByName("mime")]
	rows = table.iterQuery(select , "")

	def runNext(token):
		try:
			row = rows.next()
			res = PreviewCacheManager.getPreviewFor(row["mime"],
				[str(os.path.join(basePath, row["accref"])), str(args.width)]
			)

			if getattr(res, "result", None): # don't add a callback on a 
					# fired deferred or you'll exhaust the stack
				reactor.callLater(0.1, runNext, "continue")
			else:
				res.addCallback(runNext)
			return res
		except StopIteration:
			pass
		except:
			import traceback
			traceback.print_exc()
		reactor.stop()
		return ""

	reactor.callLater(0, runNext, "startup")
	reactor.run()


@exposedFunction([Arg(help="rd#table-id of the table to look at",
	dest="tableId")],
	help="Make suggestions for UCDs of columns not having one (based"
	" on their descriptions; this uses a GAVO web service).")
def suggestucds(querier, args):
	import SOAPpy
	import urllib
	
	wsdlURL = "http://dc.zah.uni-heidelberg.de/ucds/ui/ui/soap/go/go?wsdl"
	proxy = SOAPpy.WSDL.Proxy(urllib.urlopen(wsdlURL).read())
	td = base.resolveId(None, args.tableId)
	for col in td:
		if (not col.ucd or col.ucd=="XXX") and col.description:
			try:
				res = [(row["score"], row["ucd"]) 
					for row in proxy.useService(col.description)]
				res.sort()
				res.reverse()
				print col.name
				for score, ucd in res:
					print "  ", ucd
			except SOAPpy.Types.faultType:
				# remote failure, guess it's "no matches" (TODO: distinguish)
				pass
			

@exposedFunction([Arg(help="rd#table-id of the table of interest", 
	dest="tableId")],
	help="Show the statements to create the indices on a table.")
def indexStatements(querier, args):
	import re
	td = base.resolveId(None, args.tableId)
	for ind in td.indices:
		print "\n".join(re.sub(r"\s+", " ", s) for s in ind.iterCode())


@exposedFunction([Arg(help="Package resource path"
	" (like '/inputs/__system__/scs.rd); for system RDs, the special"
	" //rd-id syntax is supported.",
	dest="path")],
	help="Dump the source of a distribution file; this is useful when you want"
	" to override them and you are running DaCHS from a zipped egg")
def dumpDF(querier, args):
	import pkg_resources
	if args.path.startswith("//"):
		args.path = "inputs/__system__"+args.path[1:]+".rd"
	with pkg_resources.resource_stream('gavo', "resources/"+args.path) as f:
		sys.stdout.write(f.read())


@exposedFunction([Arg(help="XML file", dest="path")],
	help="Validate a file against built-in VO schemas and with built-in"
		" schema validator.")
def xsdValidate(querier, args):
	from gavo.helpers import testtricks
	msgs = testtricks.getXSDErrors(open(args.path).read())
	if not msgs:
		print "-- valid"
	else:
		print msgs


def main():
	with base.AdhocQuerier(base.getWritableAdminConn) as querier:
		args = makeParser(globals()).parse_args()
		args.subAction(querier, args)
