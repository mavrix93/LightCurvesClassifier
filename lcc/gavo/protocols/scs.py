"""
IVOA cone search: Helper functions and misc.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from gavo import base

def findNClosest(alpha, delta, tableDef, n, fields, searchRadius=5):
	"""returns the n objects closest around alpha, delta in table.

	n is the number of items returned, with the closest ones at the
	top, fields is a sequence of desired field names, searchRadius
	is a radius for the initial q3c search and will need to be
	lowered for dense catalogues and possibly raised for sparse ones.

	The last item of each row is the distance of the object from
	the query center in degrees.

	The query depends on postgastro extension (and should be changed to
	use pgsphere).  It also requires the q3c extension.
	"""
	with base.AdhocQuerier(base.getTableConn) as q:
		raField = tableDef.getColumnByUCDs("pos.eq.ra;meta.main", 
			"POS_EQ_RA_MAIN").name
		decField = tableDef.getColumnByUCDs("pos.eq.dec;meta.main", 
			"POS_EQ_RA_MAIN").name
		res = q.query("SELECT %s,"
				" celDistDD(%s, %s, %%(alpha)s, %%(delta)s) as dist_"
				" FROM %s WHERE"
				" q3c_radial_query(%s, %s, %%(alpha)s, %%(delta)s,"
				" %%(searchRadius)s)"
				" ORDER BY dist_ LIMIT %%(n)s"%
					(",".join(fields), raField, decField, tableDef.getQName(),
						raField, decField),
			locals()).fetchall()
		return res
