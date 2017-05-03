"""
Common functions and classes for services and cores.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import re
import os

from nevow import inevow
from nevow import loaders

import pkg_resources

from gavo import base


class Error(base.Error):
	def __init__(self, msg, rd=None, hint=None):
		self.rd = rd
		base.Error.__init__(self, msg, hint=hint)


class BadMethod(Error):
	"""signifies that a HTTP 405 should be returned by the dispatcher.
	"""
	def __str__(self):
		return "This resource cannot respond to the HTTP '%s' method"%self.msg


class UnknownURI(Error):
	"""signifies that a HTTP 404 should be returned by the dispatcher.
	"""

class ForbiddenURI(Error):
	"""signifies that a HTTP 403 should be returned by the dispatcher.
	"""

class Authenticate(Error):
	"""is raised when an authentication should be performed.

	Authenticates are optionally constructed with the realm the user 
	shall authenticate in.  If you leave the realm out, the DC-wide default
	will be used.
	"""
	def __init__(self, realm=base.getConfig("web", "realm")):
		self.realm = realm
		Error.__init__(self, "This is a request to authenticate against %s"%realm)


class WebRedirect(Error):
	"""is raised when the user agent should look somwhere else.

	WebRedirectes are constructed with the destination URL that can be
	relative (to webRoot) or absolute (starting with http).
	"""
	def __init__(self, dest):
		self.rawDest = dest
		dest = str(dest)
		if not dest.startswith("http"):
			dest = base.getConfig("web", "serverURL")+base.makeSitePath(dest)
		self.dest = dest
		Error.__init__(self, "This is supposed to redirect to %s"%dest)


def parseServicePath(serviceParts):
	"""returns a tuple of resourceDescriptor, serviceName.

	A serivce id consists of an inputsDir-relative path to a resource 
	descriptor, a slash, and the name of a service within this descriptor.

	This function returns a tuple of inputsDir-relative path and service name.
	It raises a gavo.Error if sid has an invalid format.  The existence of
	the resource or the service are not checked.
	"""
	return "/".join(serviceParts[:-1]), serviceParts[-1]


class QueryMeta(dict):
	"""A class keeping information on the query environment.

	It is constructed with a plain dictionary (there are alternative
	constructors for nevow contexts and requests are below) mapping 
	certain keys (you'll currently have to figure out which) to values, 
	mostly strings, except for the keys listed in listKeys, which should 
	be sequences of strings.
	
	If you pass an empty dict, some sane defaults will be used.  You
	can get that "empty" query meta as common.emptyQueryMeta, but make
	sure you don't mutate it.

	QueryMetas constructed from request will have the user and password
	items filled out.

	If you're using nevow formal, you should set the formal_data item
	to the dictionary created by formal.  This will let people use
	the parsed parameters in templates.
	"""
	
	# a set of keys handled by query meta to be ignored in parameter
	# lists because they are used internally.  This covers everything 
	# QueryMeta interprets, but also keys by introduced by certain gwidgets
	# and the nevow infrastructure
	metaKeys = set(["_DBOPTIONS", "_FILTER", "_OUTPUT", "_charset_", "_ADDITEM",
		"__nevow_form__", "_FORMAT", "_VERB", "_TDENC", "formal_data",
		"_SET", "_TIMEOUT", "_VOTABLE_VERSION"])

	# a set of keys that has sequences as values (needed for construction
	# from nevow request.args)
	listKeys = set(["_ADDITEM", "_DBOPTIONS_ORDER", "_SET"])

	def __init__(self, initArgs=None):
		if initArgs is None:
			initArgs = {}
		self.ctxArgs = initArgs
		self["formal_data"] = {}
		self["user"] = self["password"] = None
		self._fillOutput(initArgs)
		self._fillDbOptions(initArgs)
		self._fillSet(initArgs)

	@classmethod
	def fromNevowArgs(cls, nevowArgs):
		"""constructs a QueryMeta from a nevow web arguments dictionary.
		"""
		args = {}
		for key, value in nevowArgs.iteritems():
			# defense against broken legacy code: listify if necessay
			if not isinstance(value, list):
				value = [value]

			if key in cls.listKeys:
				args[key] = value
			else:
				if value:
					args[key] = value[0]
		return cls(args)

	@classmethod
	def fromRequest(cls, request):
		"""constructs a QueryMeta from a nevow request.

		In addition to getting information from the arguments, this
		also sets user and password.
		"""
		res = cls.fromNevowArgs(request.args)
		res["user"], res["password"] = request.getUser(), request.getPassword()
		return res
	
	@classmethod
	def fromContext(cls, ctx):
		"""constructs a QueryMeta from a nevow context.
		"""
		return cls.fromRequest(inevow.IRequest(ctx))

	def _fillOutput(self, args):
		"""interprets values left by the OutputFormat widget.
		"""
		self["format"] = args.get("_FORMAT", "HTML")
		try:
# prefer fine-grained "verbosity" over _VERB or VERB
# Hack: malformed _VERBs result in None verbosity, which is taken to
# mean about "use fields of HTML".  Absent _VERB or VERB, on the other
# hand, means VERB=2, i.e., a sane default
			if "verbosity" in args:
				self["verbosity"] = int(args["verbosity"])
			elif "_VERB" in args:  # internal verb parameter
				self["verbosity"] = int(args["_VERB"])*10
			elif "VERB" in args:   # verb parameter for SCS and such
				self["verbosity"] = int(args["VERB"])*10
			else:
				self["verbosity"] = 20
		except ValueError:
			self["verbosity"] = "HTML"  # VERB given, but not an int.

		self["tdEnc"] = base.getConfig("ivoa", "votDefaultEncoding")=="td"
		if "_TDENC" in args:
			try:
				self["tdEnc"] = base.parseBooleanLiteral(args["_TDENC"])
			except ValueError:
				pass

		try:
			self["VOTableVersion"] = tuple(int(v) for v in
				args["_VOTABLE_VERSION"].split("."))
		except:  # simple ignore malformed version specs
			pass

		self["additionalFields"] = args.get("_ADDITEM", [])

	def _fillSet(self, args):
		"""interprets the output of a ColumnSet widget.
		"""
		self["columnSet"] = None
		if "_SET" in args:
			self["columnSet"] = set(args["_SET"])

	def _fillDbOptions(self, args):
		self["dbSortKeys"] = [s.strip() 
			for s in args.get("_DBOPTIONS_ORDER", []) if s.strip()]

		try:
			self["dbLimit"] = int(args["_DBOPTIONS_LIMIT"])
		except (ValueError, KeyError):
			self["dbLimit"] = base.getConfig("db", "defaultLimit")
		if "MAXREC" in args:
			try:
				self["dbLimit"] = int(args["MAXREC"])
			except ValueError:
				pass

		try:
			self["timeout"] = int(args["_TIMEOUT"])
		except (ValueError, KeyError):
			self["timeout"] = base.getConfig("web", "sqlTimeout")

	def overrideDbOptions(self, sortKeys=None, limit=None):
		if sortKeys is not None:
			self["dbSortKeys"] = sortKeys
		if limit is not None:
			self["dbLimit"] = int(limit)

	def asSQL(self):
		"""returns the dbLimit and dbSortKey values as an SQL fragment.
		"""
		frag, pars = [], {}
		sortKeys = self["dbSortKeys"]
		dbLimit = self["dbLimit"]
		if sortKeys:
			# Ok, we need to do some emergency securing here.  There should be
			# pre-validation that we're actually seeing a column key, but
			# just in case let's make sure we're seeing an SQL identifier.
			# (We can't rely on dbapi's escaping since we're not talking values here)
			frag.append("ORDER BY %s"%(",".join(
				re.sub("[^A-Za-z0-9_]+", "", key) for key in sortKeys)))
		if dbLimit:
			frag.append("LIMIT %(_matchLimit)s")
			pars["_matchLimit"] = int(dbLimit)+1
		return " ".join(frag), pars

	def getQueryPars(self):
		if not "formal_data" in self:
			return {}
		return dict((k, v) for k, v in self["formal_data"].iteritems()
			if not k in self.metaKeys and v and v!=[None])


emptyQueryMeta = QueryMeta()


def getTemplatePath(key):
	"""see loadSystemTemplate.
	"""
	userPath = os.path.join(base.getConfig("rootDir"), "web/templates", key)
	if os.path.exists(userPath):
		return userPath
	else:
		resPath = "resources/templates/"+key
		if pkg_resources.resource_exists('gavo', resPath):
			return pkg_resources.resource_filename('gavo', resPath)


def loadSystemTemplate(key):
	"""returns a nevow template for system pages from key.

	path is interpreted as relative to gavo_root/web/templates (first)
	and package internal (last).  If no template is found, None is
	returned (this harmonizes with the fallback in CustomTemplateMixin).
	"""
	try:
		tp = getTemplatePath(key)
		if tp is not None:
			return loaders.xmlfile(tp)
	except IOError:
		pass
