"""
"Publishing" service records -- grammar-type stuff and UI.

This module basically turns "publishable things" -- services, resource
records, data items -- into row dictionaries that can be entered into
the database.

This is one half of getting them into the registry.  The other half is
done in identifiers and builders; these take the stuff from the database,
rebuilds actual objects and creates registry records from them.  So,
the content of the service table is not actually used to build resource
records.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import datetime
import itertools
import os
import warnings

import pkg_resources

from gavo import base
from gavo import grammars
from gavo import rsc
from gavo import utils

from gavo.registry import builders
from gavo.registry import common


def makeBaseRecord(res, keepTimestamp=False):
	"""returns a dictionary giving the metadata common to resource records.
	"""
	# bomb out if critical metadata is missing
	base.validateStructure(res)
	# bomb out if, for some reason, we can't come up with a resource record
	# for this guy
	builders.getVOResourceElement(res)

	rec = {}
	rec["ivoid"] = base.getMetaText(res, "identifier")
	rec["shortName"] = base.getMetaText(res, "shortName")
	rec["sourceRD"] = res.rd.sourceId
	rec["resId"] = res.id
	rec["title"] = base.getMetaText(res, "title", propagate=True)
	rec["deleted"] = False
	rec["recTimestamp"] = datetime.datetime.utcnow()
	rec["description"] = base.getMetaText(res, "description")
	rec["authors"] = "; ".join(m.getContent("text") 
		for m in res.iterMeta("creator.name", propagate=True))
	dateUpdated = res.getMeta("datetimeUpdated")

	if keepTimestamp:
		try:
			rec["recTimestamp"] = base.getMetaText(res, "recTimestamp")
		except base.NoMetaKey:
			# not published, nothing to keep
			pass

	if dateUpdated is None:
		rec["dateUpdated"] = datetime.datetime.utcnow()
	else:
		rec["dateUpdated"] = str(dateUpdated)
	return rec


def iterAuthorsAndSubjects(resource, sourceRD, resId):
	"""yields rows for the subjects and authors tables.

	resource is the meta-carrier for the resource to be described,
	sourceRD and resId are its keys in the resources table.
	"""
	for subject in [str(item) for item in resource.getMeta("subject") or (None,)]:
		yield ("subjects", {
			"sourceRD": sourceRD,
			"resId": resId,
			"subject": subject})
	
	# for authors, we support a special notation, separating individual
	# authors with semicolons.
	for authors in resource.iterMeta("creator.name", propagate="True"):
		authors = [s.strip() for s in authors.getContent("text").split(";")]
		for author in authors:
			if not author.startswith("et al"):
				yield ("authors", {
					"sourceRD": sourceRD,
					"resId": resId,
					"author": author})


def iterSvcRecs(service, keepTimestamp=False):
	"""iterates over records suitable for importing into the service list 
	for service.
	"""
	if not service.publications:
		return  # don't worry about missing meta if there are no publications

	rec = makeBaseRecord(service, keepTimestamp)
	rec["owner"] = service.limitTo
	yield ("resources", rec)

	# each publication becomes one interface
	for pub in service.publications:
		try:
			browseable = service.isBrowseableWith(pub.render)
		except AttributeError:  # service is not a ServiceBasedPage
			browseable = False

		intfRec = {
			"sourceRD": rec["sourceRD"],
			"resId": rec["resId"],
			"renderer": pub.render,
			"accessURL":  service.getURL(pub.render, absolute=False),
			"referenceURL": base.getMetaText(service, "referenceURL"),
			"browseable": browseable,
			"deleted": False}
		yield ("interfaces", intfRec)

		for setName in pub.sets:
			intfRec.copy()
			intfRec["setName"] = setName
			yield ("sets", intfRec)

	for pair in iterAuthorsAndSubjects(service, 
			rec["sourceRD"], rec["resId"]):
		yield pair


def iterResRecs(res, keepTimestamp=False):
	"""as iterSvcRecs, just for ResRecs rather than Services.
	"""
	rec = makeBaseRecord(res, keepTimestamp)
	# resource records only make sense if destined for the registry
	rec["setName"] = "ivo_managed"
	rec["renderer"] = "rcdisplay"
	yield ("resources", rec)
	yield ("sets", rec)

	for pair in iterAuthorsAndSubjects(res, 
			rec["sourceRD"], rec["resId"]):
		yield pair


def iterDataRecs(res, keepTimestamp=False):
	"""as iterSvcRecs, just for DataDescriptors rather than Services.
	"""
	rec = makeBaseRecord(res, keepTimestamp)
	yield ("resources", rec)
	for setName in res.registration.sets:
		rec["setName"] = setName
		rec["renderer"] = "rcdisplay"
		yield ("sets", rec.copy())

	for pair in iterAuthorsAndSubjects(res, 
			rec["sourceRD"], rec["resId"]):
		yield pair


class RDRscRecIterator(grammars.RowIterator):
	"""A RowIterator yielding resource records for inclusion into the
	service list for the services defined in the source token RD.
	"""
	def _iterRows(self):
		for svc in self.sourceToken.services:
			self.curSource = svc.id
			for sr in iterSvcRecs(svc, self.grammar.keepTimestamp):
				yield sr

		for res in self.sourceToken.resRecs:
			self.curSource = res.id
			for sr in iterResRecs(res, self.grammar.keepTimestamp):
				yield sr

		for res in itertools.chain(self.sourceToken.tables, self.sourceToken.dds):
			self.curSource = res.id
			if res.registration:
				for sr in iterDataRecs(res, self.grammar.keepTimestamp):
					yield sr
	
	def getLocation(self):
		return "%s#%s"%(self.sourceToken.sourceId, self.curSource)


class RDRscRecGrammar(grammars.Grammar):
	"""A grammar for "parsing" raw resource records from RDs.
	"""
	rowIterator = RDRscRecIterator
	isDispatching = True

	# this is a flag to try and keep the registry timestamps as they are
	# during republication.
	keepTimestamp = False
_rdRscRecGrammar = base.makeStruct(RDRscRecGrammar)


def updateServiceList(rds, metaToo=False, connection=None, onlyWarn=True,
		keepTimestamp=False):
	"""updates the services defined in rds in the services table in the database.
	"""
	recordsWritten = 0
	parseOptions = rsc.getParseOptions(validateRows=True, batchSize=20)
	if connection is None:
		connection = base.getDBConnection("admin")
	dd = common.getServicesRD().getById("tables")
	dd.grammar = _rdRscRecGrammar
	dd.grammar.keepTimestamp = keepTimestamp
	depDD = common.getServicesRD().getById("deptable")
	msg = None
	for rd in rds:
		if rd.sourceId.startswith("/"):
			raise base.Error("Resource descriptor ID must not be absolute, but"
				" '%s' seems to be."%rd.sourceId)
		try:
			data = rsc.makeData(dd, forceSource=rd, parseOptions=parseOptions,
				connection=connection)
			recordsWritten += data.nAffected
			rsc.makeData(depDD, forceSource=rd, connection=connection)

			if metaToo:
				from gavo.protocols import tap
				tap.unpublishFromTAP(rd, connection)
				for dependentDD in rd:
					rsc.Data.create(dependentDD, connection=connection).updateMeta()
				tap.publishToTAP(rd, connection)

		except base.MetaValidationError, ex:
			msg = ("Aborting publication of rd '%s' since meta structure of"
				" %s (id='%s') is invalid:\n * %s")%(
				rd.sourceId, repr(ex.carrier), ex.carrier.id, "\n * ".join(ex.failures))
		except base.NoMetaKey, ex:
			msg = ("Aborting publication of '%s' at service '%s': Resource"
				" record generation failed: %s"%(
				rd.sourceId, ex.carrier.id, str(ex)))
		except Exception, ex:
			base.ui.notifyError("Fatal error while publishing from RD %s: %s"%(
				rd.sourceId, str(ex)))
			raise

		if msg is not None:
			if onlyWarn:
				warnings.warn(msg)
			else:
				raise base.ReportableError(msg)
		msg = None

	connection.commit()
	return recordsWritten


def _purgeFromServiceTables(rdId, conn):
	"""purges all resources coming from rdId from the registry tables.

	This is not for user code that should rely on the tables doing the
	right thing (e.g., setting the deleted flag rather than deleting rows).
	Test code that is not in contact with the actual registry might want 
	this, though (until postgres grows nested transactions).
	"""
	cursor = conn.cursor()
	for tableName in [
			"resources", "interfaces", "sets", "subjects", "res_dependencies",
			"authors"]:
		cursor.execute("delete from dc.%s where sourceRD=%%(rdId)s"%tableName,
			{"rdId": rdId})
	cursor.close()



################ UI stuff

def findAllRDs():
	"""returns ids of all RDs (inputs and built-in) known to the system.
	"""
	rds = []
	inputsDir = base.getConfig("inputsDir")
	for dir, dirs, files in os.walk(inputsDir):
		for file in files:
			if file.endswith(".rd"):
				rds.append(os.path.splitext(
					utils.getRelativePath(os.path.join(dir, file), inputsDir))[0])

	for name in pkg_resources.resource_listdir('gavo', 
			"resources/inputs/__system__"):
		if not name.endswith(".rd"):  # ignore VCS files (and possibly others:-)
			continue
		rds.append(os.path.splitext("__system__/%s"%name)[0])
	return rds


def findPublishedRDs():
	"""returns the ids of all RDs which have been published before.
	"""
	with base.getTableConn() as conn:
		return [r['sourcerd'] for r in conn.queryToDicts(
			"select distinct sourcerd from dc.resources")]


def getRDs(args):
	"""returns a list of RDs from a list of more-or-less RD ids.
	"""
	allRDs = []
	for rdPath in args:
		try:
			allRDs.append(base.caches.getRD(rdPath, doQueries=False))
		except:
			base.ui.notifyError("RD %s faulty, ignored.\n"%rdPath)
	return allRDs


def parseCommandLine():
	import optparse
	parser = optparse.OptionParser(usage="%prog [options] {<rd-name>}")
	parser.add_option("-a", "--all", help="re-publish all RDs that"
		" have been published before (only use with -k unless you know"
		" what you are doing).", dest="all", action="store_true")
	parser.add_option("-m", "--meta-too", help="update meta information, too",
		dest="meta", action="store_true")
	parser.add_option("-k", "--keep-timestamps", help="Preserve the"
		" time stamp of the last record modification.  This may sometimes"
		" be desirable when updating a schema to avoid a reharvesting of"
		" all resource records.", action="store_true", dest="keepTimestamp")
	return parser.parse_args()


def updateRegistryTimestamp():
	"""edits the dateupdated field for the registry service in servicelist.
	"""
	with base.AdhocQuerier(base.getAdminConn) as q:
		regSrv = common.getRegistryService()
		q.query("UPDATE services SET dateupdated=%(now)s"
			" WHERE sourcerd=%(rdId)s AND resId=%(sId)s", {
			"rdId": regSrv.rd.sourceId,
			"sId": regSrv.id,
			"now": datetime.datetime.utcnow(),
		})
	common.getServicesRD().touchTimestamp()


def tryServiceReload():
	"""tries to reload the services RD.

	This only works if there's [web]adminpasswd and[web]serverURL
	set, and both match what the actual server uses.
	"""
	import urllib
	pw = base.getConfig("web", "adminpasswd")
	if pw=="":
		base.ui.notifyWarning("Not reloading services RD on server since"
			" no admin password available.")
		return

	try:
		f = utils.urlopenRemote(base.makeAbsoluteURL("/seffe/__system__/services"),
			urllib.urlencode({"__nevow_form__": "adminOps", "submit": "Reload RD"}),
			creds=("gavoadmin", pw))
		f.read()
	except IOError, ex:
		base.ui.notifyWarning("Could not reload services RD (%s).  This means"
			" that the registry time stamp on the server will be out of date."
			" You should reload //services manually."%ex)
	else:
		base.ui.notifyInfo("Reloaded services RD (registry timestamp up to date)")


def main():
	"""handles the user interaction for gavo publish.
	"""
	from gavo import rscdesc #noflake: register cache
	from gavo.user import plainui
	plainui.SemiStingyPlainUI(base.ui)
	opts, args = parseCommandLine()
	common.getServicesRD().touchTimestamp()
	if opts.all:
		args = findPublishedRDs()
	updateServiceList(getRDs(args), metaToo=opts.meta, 
		keepTimestamp=opts.keepTimestamp)
	tryServiceReload()


if __name__=="__main__":
	main()
