""" 
Global exceptions for the GAVO data center software.

All exceptions escaping modules should inherit from Error in some way.
Exceptions orginating in only one module should usually be defined there,
exceptions should only be defined here if they are raised by more than
one module.

Of course, for certain errors, built-in exceptions (e.g., NotImplemented
or so) may be raised and propagated as well, but these should always
signify internal bugs, never things a user should be confronted with
under normal circumstances.

And then there's stuff like fancyconfig that's supposed to live
independently of the rest.  It's ok if those raise other Exceptions,
but clearly there shouldn't be many of those, or error reporting will
become an even worse nightmare than it already is.
"""


#c Copyright 2008-2016, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


# NOTE -- due to a bug in python 2.5, you need to set the args attribute
# in your constructors, or else they'll bomb on unpickling

from gavo.utils.fancyconfig import NoConfigItem #noflake: exported name


class Error(Exception):
	"""is the base class for all exceptions that can be expected to escape
	a module.

	Apart from the normal message, you can give a "hint" constructor argument.
	"""
	def __init__(self, msg="", hint=None):
		Exception.__init__(self, msg)
		self.args = [msg, hint]
		self.msg = msg
		self.hint = hint

	def __str__(self):
		return self.msg


class StructureError(Error):
	"""is raised if an error occurs during the construction of
	structures.

	You can construct these with pos; this is an opaque object that, when
	stringified, should expand to something that gives the user a rough idea
	of where something went wrong.

	Since you will usually not know where you are in the source document
	when you want to raise a StructureError, xmlstruct will try
	to fill pos in when it's still None when it sees a StructureError.
	Thus, you're probably well advised to leave it blank.
	"""
	def __init__(self, msg, pos=None, hint=None):
		Error.__init__(self, msg, hint=hint)
		self.args = [msg, pos, hint]
		self.pos = pos

	def addPos(self, baseMsg):
		if self.pos is None:
			return baseMsg
		else:
			return "At %s: %s"%(str(self.pos), baseMsg)

	def __str__(self):
		return self.addPos(self.msg)


class LiteralParseError(StructureError):
	"""is raised if an attribute literal is somehow bad.

	LiteralParseErrors are constructed with the name of the attribute
	that was being parsed, the offending literal, and optionally a 
	parse position and a hint.
	"""
	def __init__(self, attName, literal, pos=None, hint=None):
		StructureError.__init__(self, literal, pos=pos, hint=hint)
		self.args = [attName, literal, pos, hint]
		self.attName, self.literal = attName, literal

	def __str__(self):
		return self.addPos(
			"'%s' is not a valid value for %s"%(self.literal, self.attName))


class RestrictedElement(StructureError):
	"""is raised when elements forbidden in restricted RDs are encountered
	when restricted parsing is in effect.
	"""
	def __init__(self, elName, pos=None, hint=None):
		if hint is None:
			hint='If you are actually sure this RD is what you think it it,'
			' you could always gavo imp it from the command line'
		StructureError.__init__(self, "Illegal: "+elName, pos=pos, hint=hint)
		self.args = [elName, pos, hint]
		self.elName = elName

	def __str__(self):
		return self.addPos("'%s' is an illegal attribute or element"
			" when parsing from untrusted sources."%self.elName)


class BadCode(StructureError):
	"""is raised when some code could not be compiled.

	BadCodes are constructed with the offending code, a code type,
	the original exception, and optionally a hint and a position.
	"""
	def __init__(self, code, codeType, origExc, hint=None, pos=None):
		if not hint:
			hint = "The offending code was:\n%s"%code
		StructureError.__init__(self, "Bad code", pos=pos, hint=hint)
		self.args = [code, codeType, origExc, hint, pos]
		self.code, self.codeType = code, codeType
		self.origExc = origExc

	def __repr__(self):
		return self.addPos(
			"Bad source code in %s (%s)"%(
				self.codeType, unicode(self.origExc)))

	def __str__(self):
		return repr(self)


class ValidationError(Error):
	"""is raised when the validation of a field fails.  
	
	ValidationErrors are constructed with a message, a column name,
	and optionally a row (i.e., a dict) and a hint.
	"""
	def __init__(self, msg, colName, row=None, hint=None):
		Error.__init__(self, msg, hint=hint)
		self.args = [msg, colName, row, hint]
		self.msg = msg
		self.colName, self.row = colName, row
	
	def __str__(self):
		recStr = ""
#		if self.row:
#			recStr = ", found in: row %s"%repr(self.row)
		if self.colName:
			return "Field %s: %s%s"%(self.colName, self.msg, recStr)
		else:
			return "Unidentified Field: %s%s"%(self.msg, recStr)
	
	__unicode__ = __str__


class MultiplicityError(ValidationError):
	"""is raised when a singleton is passed in multiple times or vice versa.
	"""

class SourceParseError(Error):
	"""is raised when some syntax error occurs during a source parse.

	They are constructed with the offending input construct (a source line
	or similar, None in a pinch) and the result of the row iterator's getLocator
	call.
	"""
	def __init__(self, msg, offending=None, location="unspecified location",
			source="<unspecified source>", hint=None):
		Error.__init__(self, msg, hint=hint)
		self.args = [msg, offending, location, source]
		self.offending, self.location = offending, location
		self.source = source

	def __str__(self):
		if self.offending:
			return "At %s: %s, offending %s"%(self.location, self.msg, 
				self.offending)
		else:
			return "At %s: %s"%(self.location, self.msg)


class DataError(Error):
	"""is raised when something is wrong with a data set.

	When facing the web, these yield HTTP status 406.
	"""


class ReportableError(Error):
	"""is raised when something decides it can come up with an error message
	that should be presented to the user as-is.

	UIs should, consequently, just dump the payload and not try adornments.
	The content should be treated as a unicode string.
	"""


class NotFoundError(Error):
	"""is raised when something is asked for something that does not exist.

	lookedFor can be an arbitrary object, so be careful when your repr it --
	that may be long.
	"""
	def __init__(self, lookedFor, what, within, hint=None):
		Error.__init__(self, "ignored", hint=hint)
		self.args = [lookedFor, what, within, hint]
		self.lookedFor, self.what = lookedFor, what
		self.within = within

	def __str__(self):
		return "%s %r could not be located in %s"%(
			self.what, self.lookedFor, self.within)


class EmptyData(Error):
	"""is raised within certain protocols to signify a request was successful
	but yielded no data.
	"""


class RDNotFound(NotFoundError):
	"""is raised when an RD cannot be located.
	"""
	def __init__(self, rdId, hint=None):
		NotFoundError.__init__(self, rdId, hint=hint, what="Resource descriptor",
			within="file system")
		self.args = [rdId, hint]


class ExecutiveAction(Exception):
	"""is a base class for exceptions that are supposed to break out of
	deep things and trigger actions higher up.
	"""


class SkipThis(ExecutiveAction):
	"""is caught in rsc.makeData.  You can raise this at any place during
	source processing to skip the rest of this source but the go on.

	You should pass something descriptive as message so upstream can
	potentially report something is skipped.
	"""


try:
	from gavo.imp.pyparsing import ( #noflake: exported name
		ParseBaseException as ParseException)
except ImportError:
	pass
