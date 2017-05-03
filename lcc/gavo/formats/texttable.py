"""
Writing data as plain text.

Currently, we only do TSV.  It would probably be nice to support "formatted
ASCII as well, though that may be a bit tricky given that we do not
really store sane formatting hints for most columns.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import cStringIO

from gavo import base
from gavo import rsc
from gavo.formats import common


def _makeString(val):
# this is a cheap trick to ensure everything non-ascii is escaped.
	if isinstance(val, basestring):
		return repr(unicode(val))[2:-1]
	return str(val)


def renderAsText(table, target, acquireSamples=True):
	"""writes a text (TSV) rendering of table to the file target.
	"""
	if isinstance(table, rsc.Data):
		table = table.getPrimaryTable()
	sm = base.SerManager(table, acquireSamples=acquireSamples)
	for row in sm.getMappedTuples():
		target.write("\t".join([_makeString(s) for s in row])+"\n")


def getAsText(data):
	target = cStringIO.StringIO()
	renderAsText(data, target)
	return target.getvalue()


def readTSV(inFile):
	"""returns a list of tuples for a tab-separated-values file.

	Lines starting with # and lines containing only whitespace are ignored.  
	Whitespace at front and back is stripped.

	No checks are done at this point, i.e., the tuples could be of varying 
	lengths.
	"""
	data = []
	for ln in inFile:
		ln = ln.strip()
		if not ln or ln.startswith("#"):
			continue
		data.append(tuple(ln.split("\t")))
	return data


# NOTE: This will only serialize the primary table.
common.registerDataWriter("tsv", renderAsText, "text/tab-separated-values",
	"Tab separated values", "text/plain")
