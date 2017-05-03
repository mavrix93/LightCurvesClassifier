"""
Common functionality for the DC user interface.

This module contains, in partiular, the interface for having "easy subcommands"
using argparse.  The idea is to use the exposedFunction decorator on functions
that should be callable from the command line as subcommands; the functions
must all have the same signature. For example, if they all took the stuff
returned by argparse, you could say in the module containing them::

  args = _makeParser(globals()).parse_args()
  args.subAction(args)

To specify the command line arguments to the function, use Args.  See
admin.py for an example.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import sys

from gavo import base
from gavo.imp import argparse


class Arg(object):
	"""an argument/option to a subcommand.

	These are constructed with positional and keyword parameters to
	the argparse's add_argument.
	"""
	def __init__(self, *args, **kwargs):
		self.args, self.kwargs = args, kwargs
	
	def add(self, parser):
		parser.add_argument(*self.args, **self.kwargs)


def exposedFunction(argSpecs=(), help=None):
	"""a decorator exposing a function to parseArgs.

	argSpecs is a sequence of Arg objects.  This defines the command line
	interface to the function.

	The decorated function itself must accept a single argument,
	the args object returned by argparse's parse_args.
	"""
	def deco(func):
		func.subparseArgs = argSpecs
		func.subparseHelp = help
		return func
	return deco


def makeParser(functions):
	"""returns a command line parser parsing subcommands from functions.

	functions is a dictionary (as returned from globals()).  Subcommands
	will be generated from all objects that have a subparseArgs attribute;
	furnish them using the commandWithArgs decorator.

	This attribute must contain a sequence of Arg items (see above).
	"""
	parser = argparse.ArgumentParser()
	subparsers = parser.add_subparsers()
	for name, val in functions.iteritems():
		args = getattr(val, "subparseArgs", None)
		if args is not None:
			subForName = subparsers.add_parser(name, help=val.subparseHelp)
			for arg in args:
				arg.add(subForName)
			subForName.set_defaults(subAction=val)
	return parser


def getMatchingFunction(funcSelector, functions, parser):
	"""returns the module name and a funciton name within the module for
	the function selector funcSelector.

	The function will exit if funcSelector is not a unique prefix within
	functions.
	"""
	matches = []
	for key, res in functions:
		if key.startswith(funcSelector):
			matches.append(res)
	if len(matches)==1:
		return matches[0]
	if matches:
		sys.stderr.write("Multiple matches for function %s.\n\n"%funcSelector)
	else:
		sys.stderr.write("No match for function %s.\n\n"%funcSelector)
	parser.print_help(file=sys.stderr)
	sys.exit(1)


def _getAutoDDIds(rd):
	"""helps getPertainingDDs
	"""
	res = []
	for dd in rd.dds:
		if dd.auto:
			res.append(dd)
	return res


def _getSelectedDDIds(rd, selectedIds):
	"""helps getPertainingDDs
	"""
	res = []
	ddDict = dict((dd.id, dd) for dd in rd.dds)
	for ddId in selectedIds:
		if ddId not in ddDict:
			raise base.ReportableError(
				"The DD '%s' you are trying to import is not defined within"
				" the RD '%s'."%(ddId, rd.sourceId),
				hint="Data elements available in %s include %s"%(rd.sourceId,
					", ".join(ddDict) or '(None)'))
		res.append(ddDict[ddId])
	return res


def getPertainingDDs(rd, selectedIds):
	"""returns a list of dds on which imp or drop should operate.

	By default, that's the "auto" dds of rd.  If ddIds is not empty,
	it is validated that all ids mentioned actually exist.

	Finally, if no DDs are selected but DDs are available, an error is raised.
	"""
	if selectedIds:
		dds = _getSelectedDDIds(rd, selectedIds)
	else:
		dds = _getAutoDDIds(rd)
	if not dds:
		if not rd.dds:
			base.ui.notifyWarning("There is no data element"
				" in the RD %s; is that all right?"%rd.sourceId)
		else:
			raise base.ReportableError(
				"Neither automatic not manual data selected from RD %s "%rd.sourceId,
				hint="All data elements have auto=False.  You have to"
					" explicitely name one or more data to import (names"
					" available: %s)"%(", ".join(dd.id or "(anon)" for dd in rd.dds)))
	return dds

