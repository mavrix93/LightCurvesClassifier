"""
CLI function to show various things.

Maybe gavo config and gavo info should be folded in here if this grows.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from gavo import rscdesc  # (register getRD)
from gavo.user.common import Arg, exposedFunction, makeParser


@exposedFunction([
	Arg("rdId", help="an RD id (or a path to RD xml)"),],
	help="show what data items are avalailable")
def dds(args):
	rd = rscdesc.openRD(args.rdId)
	for dd in rd.dds:
		outLine = dd.id
		if dd.auto:
			outLine += "*"
		print outLine

def main():
	args = makeParser(globals()).parse_args()
	args.subAction(args)
