"""
The main entry point to CLI usage of GAVO code.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from __future__ import with_statement

# The idea here is that you expose a CLI functionality by giving, as
# strings, the module and function to call.
#
# We also give a little startup note if we're running on a tty.
# While we do this, we import api; that should take care of most
# of the real startup time.

import os
import sys
import textwrap
import traceback

from gavo.user import common


functions = [
	("admin", ("user.admin", "main")),
	("adql", ("protocols.adqlglue", "localquery")),
	("config", ("base.config", "main")),
	("drop", ("user.dropping", "dropRD")),
	("dlrun", ("protocols.dlasync", "main")),
	("purge", ("user.dropping", "dropTable")),
	("gendoc", ("user.docgen", "main")),
	("import", ("user.importing", "main")),
	("info", ("user.info", "main")),
	("mkboost", ("grammars.directgrammar", "main")),
	("mkrd", ("user.mkrd", "main")),
	("publish", ("registry.publication", "main")),
	("raise", ("user.errhandle", "bailOut")),
	("serve", ("user.serve", "main")),
	("stc", ("stc.cli", "main")),
	("show", ("user.show", "main")),
	("test", ("rscdef.regtest", "main")),
	("taprun", ("protocols.taprunner", "main")),
	("totesturl", ("rscdef.regtest", "urlToURL")),
	("validate", ("user.validation", "main")),
	("upgrade", ("user.upgrade", "main")),
# init is special cased, but we want it in here for help generation
	("init", ("initdachs.info", "main")),
]


def _enablePDB():
# This can't be a callback to the --enable-pdb option since it needs
# errhandle, and we only want to import this after the command line
# is parsed
	import pdb
	def enterPdb(type, value, tb):
		traceback.print_exception(type, value, tb)
		pdb.pm()
	sys.excepthook = enterPdb


def _enableDebug(*args):
	from gavo import base
	base.DEBUG = True


def _printVersion(*args):
	from gavo import base
	from gavo.user import upgrade
	print "Software (%s) Schema (%s/%s)"%(
		base.getVersion(),
		upgrade.CURRENT_SCHEMAVERSION,
		upgrade.getDBSchemaVersion())
	sys.exit(0)


def _parseCLArgs():
	"""parses the command line and returns instructions on how to go on.

	As a side effect, sys.argv is manipulated such that the program
	called thinks it was execd in the first place.
	"""
	from optparse import OptionParser
	sels = [n for n,x in functions]
	sels.sort()
	parser = OptionParser(usage="%prog {<global option>} <func>"
		" {<func option>} {<func argument>}\n"+
		textwrap.fill("<func> is a unique prefix into {%s}"%(", ".join(sels)),
		initial_indent='', subsequent_indent='  '),
		description="Try %prog <func> --help for function-specific help")
	parser.disable_interspersed_args()
	parser.add_option("--traceback", help="print a traceback on all errors.",
		action="store_true", dest="alwaysTracebacks")
	parser.add_option("--hints", help="if there are hints on an error, display"
		" them", action="store_true", dest="showHints")
	parser.add_option("--enable-pdb", help="run pdb on all errors.",
		action="store_true", dest="enablePDB")
	parser.add_option("--disable-spew", help='Ignored.',
		action="store_true", dest="disableSpew")
	parser.add_option("--profile-to", metavar="PROFILEPATH",
		help="enable profiling and write a profile to PROFILEPATH",
		action="store", dest="profilePath", default=None)
	parser.add_option("--suppress-log", help="Do not log exceptions and such"
		" to the gavo-specific log files", action="store_true",
		dest="suppressLog")
	parser.add_option("--debug", help="Produce debug info as appropirate.",
		action="callback", callback=_enableDebug)
	parser.add_option("--version", help="Write software version to stdout"
		" and exit", action="callback", callback=_printVersion)

	opts, args = parser.parse_args()
	if len(args)<1:
		parser.print_help(file=sys.stderr)
		sys.exit(2)

	module, funcName = common.getMatchingFunction(args[0], functions, parser)
	parser.destroy()
	args[0] = "gavo "+args[0]
	sys.argv = args
	return opts, module, funcName


def main():

	# we want to preserve group-writability in all our operations;  hence
	# this prominent place for overriding a user decision...
	os.umask(002)

	if len(sys.argv)>1 and sys.argv[1]=="init":  
		# Special case: initial setup, no api working yet
		del sys.argv[1]
		from gavo.user import initdachs
		sys.exit(initdachs.main())

	opts, module, funcName = _parseCLArgs()
	from gavo import base
	from gavo import utils
	from gavo.user import errhandle

	if not (opts.suppressLog or os.environ.get("GAVO_LOG")=="no"):
		from gavo.user import logui
		logui.LoggingUI(base.ui)

	if opts.enablePDB:
		_enablePDB()
	funcToRun = utils.loadInternalObject(module, funcName)

	if opts.profilePath:
		import cProfile
		cProfile.runctx("funcToRun()", globals(), locals(), opts.profilePath)
		return

	try:
		funcToRun()
	except Exception:
		if opts.alwaysTracebacks:
			traceback.print_exc()
		sys.exit(errhandle.raiseAndCatch(opts))


if __name__=="__main__":
	main()
