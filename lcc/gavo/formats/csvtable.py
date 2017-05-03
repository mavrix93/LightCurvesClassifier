"""
Wrinting data in CSV.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import csv
import re

from gavo import base
from gavo import rsc
from gavo.formats import common


def _encodeRow(row):
	"""return row with everything that's a unicode object turned into a
	utf-8 encoded string.

	This will also normalise whitespace to blanks.
	"""
	res = []
	for val in row:
		if isinstance(val, str):
			res.append(re.sub("\s+", " ", val))
		if isinstance(val, unicode):
			res.append(re.sub("\s+", " ", val.encode("utf-8")))
		else:
			res.append(val)
	return res


def writeDataAsCSV(table, target, acquireSamples=True,
		dialect=base.getConfig("async", "csvDialect"), headered=False):
	"""writes table to the file target in CSV.

	The CSV format chosen is controlled through the async/csvDialect
	config item.

	If headered is True, we also include table params (if present)
	in comments.
	"""
	if isinstance(table, rsc.Data):
		table = table.getPrimaryTable()
	sm = base.SerManager(table, acquireSamples=acquireSamples)
	writer = csv.writer(target, dialect)

	if headered:
		for param in table.iterParams():
			if param.value is not None:
				target.write(("# %s = %s // %s\r\n"%(
					param.name,
					param.getStringValue(),
					param.description)).encode("utf-8"))

		writer.writerow([c["name"] for c in sm])

	for row in sm.getMappedTuples():
		try:
			writer.writerow(_encodeRow(row))
		except UnicodeEncodeError:
			writer.writerow(row)
	

def writeDataAsHeaderedCSV(table, target, acquireSamples=True):
	return writeDataAsCSV(table, target, headered=True,
		acquireSamples=acquireSamples)

# NOTE: This will only serialize the primary table
common.registerDataWriter("csv", writeDataAsCSV, "text/csv", 
	"CSV without column labels")
common.registerDataWriter("csv_header", 
	lambda table, target, **kwargs: 
		writeDataAsCSV(table, target, headered=True, **kwargs),
	"text/csv;header=present",
	"CSV with column labels")
