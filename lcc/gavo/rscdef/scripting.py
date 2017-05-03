"""
Support code for attaching scripts to objects.

Scripts can be either in python or in SQL.  They always live on
make instances.  For details, see Scripting in the reference
documentation.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from __future__ import with_statement

from gavo.imp.pyparsing import (
	OneOrMore, ZeroOrMore, QuotedString, Forward,
	SkipTo, StringEnd, Regex, Suppress,
	Literal)

from gavo import base
from gavo import utils
from gavo.base import sqlsupport
from gavo.rscdef import rmkfuncs


class Error(base.Error):
	pass


def _getSQLScriptGrammar():
	"""returns a pyparsing ParserElement that splits SQL scripts into
	individual commands.

	The rules are: Statements are separated by semicolons, empty statements
	are allowed.
	"""
	with utils.pyparsingWhitechars(" \t"):
		atom = Forward()
		atom.setName("Atom")

		sqlComment = Literal("--")+SkipTo("\n", include=True)
		cStyleComment = Literal("/*")+SkipTo("*/", include=True)
		comment = sqlComment | cStyleComment
		lineEnd = Literal("\n")

		simpleStr = QuotedString(quoteChar="'", escChar="\\", 
			multiline=True, unquoteResults=False)
		quotedId = QuotedString(quoteChar='"', escChar="\\", unquoteResults=False)
		dollarQuoted = Regex(r"(?s)\$(\w*)\$.*?\$\1\$")
		dollarQuoted.setName("dollarQuoted")
		# well, quotedId is not exactly a string literal.  I hate it, and so
		# it's lumped in here.
		strLiteral = simpleStr | dollarQuoted | quotedId
		strLiteral.setName("strLiteral")

		other = Regex("[^;'\"$]+")
		other.setName("other")

		literalDollar = Literal("$") + ~ Literal("$")
		statementEnd = ( Literal(';') + ZeroOrMore(lineEnd) | StringEnd() )

		atom <<  ( Suppress(comment) | other | strLiteral | literalDollar )
		statement = OneOrMore(atom) + Suppress( statementEnd )
		statement.setName("statement")
		statement.setParseAction(lambda s, p, toks: " ".join(toks))

		script = OneOrMore( statement ) + StringEnd()
		script.setName("script")
		script.setParseAction(lambda s, p, toks: [t for t in toks.asList()
			if str(t).strip()])

		if False:
			atom.setDebug(True)
			comment.setDebug(True)
			other.setDebug(True)
			strLiteral.setDebug(True)
			statement.setDebug(True)
			statementEnd.setDebug(True)
			dollarQuoted.setDebug(True)
			literalDollar.setDebug(True)
		return script


getSQLScriptGrammar = utils.CachedGetter(_getSQLScriptGrammar)


class ScriptRunner(object):
	"""An object encapsulating the preparation and execution of
	scripts.

	They are constructed with instances of Script below and have
	a method run(dbTable, **kwargs).

	You probably should not override __init__ but instead override
	_prepare(script) which is called by __init__.
	"""
	def __init__(self, script):
		self.name, self.notify = script.name, script.notify
		self._prepare(script)
	
	def _prepare(self, script):
		raise ValueError("Cannot instantate plain ScriptRunners")


class SQLScriptRunner(ScriptRunner):
	"""A runner for SQL scripts.

	These will always use the table's querier to execute the statements.

	Keyword arguments to run are ignored.
	"""
	def _prepare(self, script):
		self.statements = utils.pyparseString(getSQLScriptGrammar(), 
			script.getSource())
	
	def run(self, dbTable, **kwargs):
		for statement in self.statements:
			dbTable.query(statement.replace("%", "%%"))


class ACSQLScriptRunner(SQLScriptRunner):
	"""A runner for "autocommitted" SQL scripts.

	These are like SQLScriptRunners, except that for every statement,
	a savepoint is created, and for SQL errors, the savepoint is restored
	(in other words ACSQL scripts turn SQL errors into warnings).
	"""
	def run(self, dbTable, **kwargs):
		for statement in self.statements:
			try:
				dbTable.query("SAVEPOINT beforeStatement")
				try:
					dbTable.query(statement.replace("%", "%%"))
				except sqlsupport.DBError, msg:
					dbTable.query("ROLLBACK TO SAVEPOINT beforeStatement")
					base.ui.notifyError("Ignored error during script execution: %s"%
						msg)
			finally:
				dbTable.query("RELEASE SAVEPOINT beforeStatement")


class PythonScriptRunner(ScriptRunner):
	"""A runner for python scripts.

	The scripts can access the current table as table (and thus run
	SQL statements through table.query(query, pars)).

	Additional keyword arguments are available under their names.

	You are in the namespace of usual procApps (like procs, rowgens, and
	the like).
	"""
	def __init__(self, script):
		# I need to memorize the script as I may need to recompile
		# it if there's special arguments (yikes!)
		self.code = ("def scriptFun(table, **kwargs):\n"+
			utils.fixIndentation(script.getSource(), "      ")+"\n")
		ScriptRunner.__init__(self, script)

	def _compile(self, moreNames={}):
		return rmkfuncs.makeProc("scriptFun", self.code, "", self,
			**moreNames)

	def _prepare(self, script, moreNames={}):
		self.scriptFun = self._compile()
	
	def run(self, dbTable, **kwargs):
# I want the names from kwargs to be visible as such in scriptFun -- if
# given.  Since I do not want to manipulate func_globals, the only
# way I can see to do this is to compile the script.  I don't think
# this is going to be a major performance issue.
		if kwargs:
			func = self._compile(kwargs)
		else:
			func = self.scriptFun
		func(dbTable, **kwargs)


RUNNER_CLASSES = {
	"SQL": SQLScriptRunner,
	"python": PythonScriptRunner,
	"AC_SQL": ACSQLScriptRunner,
}

class Script(base.Structure, base.RestrictionMixin):
	"""A script, i.e., some executable item within a resource descriptor.

	The content of scripts is given by their type -- usually, they are
	either python scripts or SQL with special rules for breaking the
	script into individual statements (which are basically like python's).

	The special language AC_SQL is like SQL, but execution errors are
	ignored.  This is not what you want for most data RDs (it's intended
	for housekeeping scripts).

	See `Scripting`_.
	"""
	name_ = "script"
	typeDesc_ = "Embedded executable code with a type definition"

	_lang = base.EnumeratedUnicodeAttribute("lang", default=base.Undefined,
		description="Language of the script.", 
		validValues=["SQL", "python", "AC_SQL"], copyable=True)
	_type = base.EnumeratedUnicodeAttribute("type", default=base.Undefined,
		description="Point of time at which script is to run.", 
		validValues=["preImport", "newSource", "preIndex", "postCreation",
			"beforeDrop", "sourceDone"], copyable=True)
	_name = base.UnicodeAttribute("name", default="anonymous",
		description="A human-consumable designation of the script.",
		copyable=True)
	_notify = base.BooleanAttribute("notify", default=True,
		description="Send out a notification when running this"
			" script.", copyable=True)
	_content = base.DataContent(copyable=True, description="The script body.")
	_original = base.OriginalAttribute()

	def getSource(self):
		"""returns the content with all macros expanded.
		"""
		return self.parent.getExpander().expand(self.content_)



class ScriptingMixin(object):
	"""A mixin that gives objects a getRunner method and a script attribute.

	Within the DC, this is only mixed into make.

	The getRunner() method returns a callable that takes the current table
	(we expect db tables, really), the phase and possibly further keyword
	arguments, as appropriate for the phase.

	Objects mixing this in must also support define a method
	getExpander() returning an object mixin in a MacroPackage.
	"""
	_scripts = base.StructListAttribute("scripts", childFactory=Script,
		description="Code snippets attached to this object.  See Scripting_ .",
		copyable=True)

	def getRunner(self):
		runnersByPhase = {}
		for rawScript in self.scripts:
			runner = RUNNER_CLASSES[rawScript.lang](rawScript)
			runnersByPhase.setdefault(rawScript.type, []).append(runner)
			
		def runScripts(table, phase, **kwargs):
			for runner in runnersByPhase.get(phase, []):
				if runner.notify:
					base.ui.notifyScriptRunning(runner)
				runner.run(table, **kwargs)
		
		return runScripts
