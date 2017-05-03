"""
A small user interface for testing STC.
"""

#c Copyright 2008-2016, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import sys
import textwrap

from gavo import base
from gavo import stc


def cmd_resprof(opts, srcSTCS):
	"""<srcSTCS> -- make a resource profile for srcSTCS.
	"""
	ast0 = stc.parseSTCS(srcSTCS)
	print stc.getSTCXProfile(ast0)


def cmd_parseX(opts, srcFile):
	"""<srcFile> -- read STC-X from srcFile and output it as STC-S, - for stdin
	"""
	if srcFile=="-":
		src = sys.stdin
	else:
		src = open(srcFile)
	asf = stc.parseSTCX(src.read())
	src.close()
	print "\n\n====================\n\n".join(stc.getSTCS(ast)
		for _, ast in asf)
		

def cmd_conform(opts, srcSTCS, dstSTCS):
	"""<srcSTCS>. <dstSTCS>  -- prints srcSTCS in the system of dstSTCS.
	"""
	ast0, ast1 = stc.parseSTCS(srcSTCS), stc.parseSTCS(dstSTCS)
	res = stc.conformTo(ast0, ast1)
	print stc.getSTCS(res)


def cmd_utypes(opts, srcSTCS):
	"""<QSTCS> -- prints the utypes for the quoted STC string <QSTCS>.
	"""
	utypes = stc.getUtypes(stc.parseQSTCS(srcSTCS))
	for utype, val in sorted(utypes, key=lambda a:a[0]):
		if isinstance(val, stc.ColRef):
			print "%-60s -> %s"%(utype, val.dest)
		else:
			print "%-60s = %s"%(utype, val)


def cmd_parseUtypes(opts):
	"""--- reads the output of utypes and prints quoted STC for it.
	"""
	types = []
	for ln in sys.stdin:
		try:
			utype, val = ln.split("=", 1)
			types.append((utype.strip(), val.strip()))
		except ValueError:
			pass
		else:
			continue
		try:
			utype, val = ln.split("->", 1)
			types.append((utype.strip(), stc.ColRef(val.strip())))
		except ValueError:
			pass
		else:
			continue
		raise base.ReportableError("Not a proper input line for STC-S: %r"%ln)
	print stc.getSTCS(stc.parseFromUtypes(types))


def makeParser():
	from optparse import OptionParser
	parser = OptionParser(usage="%prog [options] <command> {<command-args}\n"
		"  Use command 'help' to see commands available.")
	parser.add_option("-e", "--dump-exception", help="Dump exceptions.",
		dest="dumpExc", default=False, action="store_true")
	return parser

_cmdArgParser = makeParser()


def cmd_help(opts):
	""" -- outputs help to stdout.
	"""
	_cmdArgParser.print_help(file=sys.stdout)
	sys.stdout.write("\nCommands include:\n")
	for name in sorted(n for n in globals() if n.startswith("cmd_")):
		sys.stdout.write("%s %s\n"%(name[4:], 
			globals()[name].__doc__.strip()))
	

def parseArgs():
	opts, args = _cmdArgParser.parse_args()
	if not args:
		_cmdArgParser.print_help(file=sys.stderr)
		sys.exit(1)
	return opts, args[0], args[1:]


def bailOnExc(opts, msg):
	import traceback
	if opts.dumpExc:
		traceback.print_exc()
	sys.stderr.write(textwrap.fill(msg, replace_whitespace=True,
		initial_indent='', subsequent_indent="  ")+"\n")
	sys.exit(1)


def main():
	opts, cmd, args = parseArgs()
	try:
		handler = globals()["cmd_"+cmd]
	except KeyError:
		bailOnExc(opts, "Unknown command: %s."%cmd)
	try:
		handler(opts, *args)
	except TypeError:
		bailOnExc(opts, "Invalid arguments for %s: %s."%(cmd, args))
	except stc.STCSParseError, ex:
		bailOnExc(opts, "STCS expression '%s' bad somewhere after %s (%s)"%(
			ex.expr, ex.pos, ex.message))
	except stc.STCNotImplementedError, ex:
		bailOnExc(opts, "Feature not yet supported: %s."%ex)
	except stc.STCValueError, ex:
		bailOnExc(opts, "Bad value in STC input: %s."%ex)
