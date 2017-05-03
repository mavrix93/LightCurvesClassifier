"""
A macro mechanism primarily for string replacement in resource descriptors.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from __future__ import with_statement

import datetime
import urllib

from gavo.imp.pyparsing import (
	ZeroOrMore, Forward,
	Regex, Suppress,
	Literal)


from gavo import utils
from gavo.base import attrdef
from gavo.base import common
from gavo.base import complexattrs
from gavo.base import config
from gavo.base import meta
from gavo.base import osinter
from gavo.base import structure


class MacroError(common.StructureError):
	"""is raised when something bad happens during macro expansion.

	It is constructed with an error message, a macro name, and optionally
	a hint and a position.
	"""
	def __init__(self, message, macroName, hint=None, pos=None):
		common.StructureError.__init__(
			self, macroName+" failed", pos=pos, hint=hint)
		self.args = [message, macroName, hint, pos]
		self.macroName, self.message = macroName, message

	def __str__(self):
		return "Error during macro expansion: %s"%(
			self.message)


class MacroExpander(object):
	"""is a generic "macro" expander for scripts of all kinds.

	It is loosely inspired by TeX, but of course much simpler.  See the
	syntax below.

	The macros themselves come from a MacroPackage object.  There are
	a few of these around, implementing different functionality depending
	on the script context (i.e., whether it belongs to an RD, a DD, or
	a Table.

	All macros are just functions receiving and returning strings.  The
	arguments are written as {arg1}{arg2}, where you can escape curly
	braces with a backslash.  There must be no whitespace between
	a macro and its first argument.

	If you need to glue together a macro expansion and text following,
	use the glue sequence \\+

	The main entry point to the class is the expand function below,
	taking a string possibly containing macro calls and returning
	a string.

	The construction of such a macro expander is relatively expensive,
	so it pays to cache them.  MacroPackage below has a getExpander
	method that does the caching for you.
	"""
	def __init__(self, package):
		self.package = package
		self._macroGrammar = self._getMacroGrammar()

	def _execMacro(self, s, loc, toks):
		toks = toks.asList()
		macName, args = toks[0], toks[1:]
		return self.package.execMacro(macName, args)

	def expand(self, aString):
		return utils.pyparseTransform(self._macroGrammar, aString)

	def _getMacroGrammar(self, debug=False):
		with utils.pyparsingWhitechars(" \t"):
			macro = Forward()
			quoteEscape = (Literal("\\{").addParseAction(lambda *args: "{") | 
				Literal("\\}").addParseAction(lambda *args: "}"))
			charRun = Regex(r"[^}\\]+")
			argElement = macro | quoteEscape | charRun
			argument = Suppress("{") + ZeroOrMore(argElement) + Suppress("}")
			argument.addParseAction(lambda s, pos, toks: "".join(toks))
			arguments = ZeroOrMore(argument)
			arguments.setWhitespaceChars("")
			macroName = Regex("[A-Za-z_][A-Za-z_0-9]+")
			macroName.setWhitespaceChars("")
			macro << Suppress( "\\" ) + macroName + arguments
			macro.addParseAction(self._execMacro)
			literalBackslash = Literal("\\\\")
			literalBackslash.addParseAction(lambda *args: "\\")
			suppressedLF = Literal("\\\n")
			suppressedLF.addParseAction(lambda *args: " ")
			glue = Literal("\\+")
			glue.addParseAction(lambda *args: "")
			return literalBackslash | suppressedLF | glue | macro


class ExpansionDelegator(object):
	"""A mixin to make a class expand macros by delegating everything to
	its parent.

	This is intended for base.Structures that have a parent attribute;
	by mixing this in, they use their parents to expand macros for them.
	"""
	def expand(self, aString):
		return self.parent.expand(aString)


class MacroPackage(object):
	r"""is a function dispatcher for MacroExpander.

	Basically, you inherit from this class and define macro_xxx functions.
	MacroExpander can then call \xxx, possibly with arguments.
	"""
	def __findMacro(self, macName):
		fun = getattr(self, "macro_"+macName, None)
		if fun is not None:
			return fun
		if hasattr(self, "rd"):
			fun = getattr(self.rd, "macro_"+macName, None)
		if fun is not None:
			return fun
		raise MacroError(
			"No macro \\%s available in a %s context"%(
				macName, self.__class__.__name__),
			macName, hint="%s objects have the following macros: %s."%(
				self.__class__.__name__, ", ".join(self.listMacros())))

	def listMacros(self):
		return [n[6:] for n in dir(self) if n.startswith("macro_")]

	def execMacro(self, macName, args):
		fun = self.__findMacro(macName)
		try:
			return fun(*args)
		except TypeError:
			raise utils.logOldExc(MacroError(
				"Invalid macro arguments to \\%s: %s"%(macName, args), macName,
				hint="You supplied too few or too many arguments"))

	def getExpander(self):
		try:
			return self.__macroExpander
		except AttributeError:
			self.__macroExpander = MacroExpander(self)
			return self.getExpander()

	def expand(self, stuff):
		return self.getExpander().expand(stuff)

	def macro_quote(self, arg):
		"""returns the argument in quotes (with internal quotes backslash-escaped 
		if necessary).
		"""
		return '"%s"'%(arg.replace('"', '\\"'))


class StandardMacroMixin(MacroPackage):
	"""is  a mixin providing some macros for scripting's MacroExpander.

	The class mixing in needs to provide its resource descriptor in the
	rd attribute.
	"""
	def macro_rdId(self):
		"""the identifier of the current resource descriptor.
		"""
		return self.rd.sourceId

	def macro_rdIdDotted(self):
		"""the identifier for the current resource descriptor with slashes replaced
		with dots (so they work as the "host part" in URIs.
		"""
		return self.rd.sourceId.replace("/", ".")

	def macro_schema(self):
		"""the schema of the current resource descriptor.
		"""
		return self.rd.schema

	def macro_RSTservicelink(self, serviceId, title=None):
		"""a link to an internal service; id is <rdId>/<serviceId>/<renderer>,
		title, if given, is the anchor text.

		The result is a link in the short form for restructured test.
		"""
		if title is None:
			title = serviceId
		return "`%s <%s>`_"%(title, osinter.makeSitePath(serviceId))

	def macro_RSTtable(self, tableName):
		"""adds an reStructured test link to a tableName pointing to its table
		info.
		"""
		return "`%s <%s>`_"%(tableName, 
			osinter.makeSitePath("tableinfo/%s"%tableName))

	def macro_internallink(self, relPath):
		"""an absolute URL from a path relative to the DC root.
		"""
		return osinter.makeAbsoluteURL(relPath)

	def macro_urlquote(self, string):
		"""wraps urllib.quote.
		"""
		return urllib.quote(string)

	def macro_today(self):
		"""today's date in ISO representation.
		"""
		return str(datetime.date.today())

	def macro_getConfig(self, section, name=None):
		"""the current value of configuration item {section}{name}.

		You can also only give one argument to access settings from the
		general section.
		"""
		if name is None:
			section, name = "general", section
		return str(config.get(section, name))

	def macro_metaString(self, metaKey, default=None):
		"""the value of metaKey on the macro expander.

		This will raise an error when the meta Key is not available unless
		you give a default.
		"""
		try:
			val = self.getMeta(metaKey, raiseOnFail=True)
		except meta.NoMetaKey:
			if default is not None:
				return default
			raise
		return val.getContent(macroPackage=self
			).replace("\n", " ") # undo default line breaking

	def macro_upper(self, aString):
		"""returns aString uppercased.

		There's no guarantees for characters outside ASCII.
		"""
		return aString.upper()

	def macro_decapitalize(self, aString):
		"""returns aString with the first character lowercased.
		"""
		if aString:
			return aString[0].lower()+aString[1:]

	def macro_test(self, *args):
		"""always "test macro expansion".
		"""
		return "test macro expansion"


class MacDef(structure.Structure):
	"""A macro definition within an RD.

	The macro defined is available on the parent.
	"""
	name_ = "macDef"

	_name = attrdef.UnicodeAttribute("name", description="Name the macro"
		" will be available as", copyable=True, default=utils.Undefined)
	_content = structure.DataContent(description="Replacement text of the"
		" macro")

	def validate(self):
		self._validateNext(MacDef)
		if len(self.name)<2:
			raise common.LiteralParseError("name", self.name, hint=
				"Macro names must have at least two characters.")

	def onElementComplete(self):
		self._onElementCompleteNext(MacDef)
		def mac():
			return self.content_
		setattr(self.parent, "macro_"+self.name, mac)


def MacDefAttribute(**kwargs):
	return complexattrs.StructListAttribute("macDefs", childFactory=MacDef,
		**kwargs)
