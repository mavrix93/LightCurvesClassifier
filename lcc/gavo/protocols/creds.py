"""
Code for checking against our user db.

We don't use nevow.guard here since we know we're queried via http, but we
can't be sure that the other end knows html, and we don't want to fuzz around
with sessions.  twisted.cred is a different issue but probably only complicates
matters unnecessarily.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from __future__ import with_statement

from gavo import base


# this should only be changed for unit tests
adminProfile = "admin"


class AllSet(set):
	def __repr__(self):
		return "<all encompassing set>"

	def __contains__(*args):
		return True


def getGroupsForUser(username, password):
	"""returns a set of all groups user username belongs to.

	If username and password don't match, you'll get an empty set.
	"""
	def parseResponse(dbTable):
		return set([a[0] for a in dbTable])

	if username is None:
			return set()
	if username=='gavoadmin' and (
			password and password==base.getConfig("web", "adminpasswd")):
		return AllSet()
	query = ("SELECT groupname FROM dc.groups NATURAL JOIN dc.users as u"
		" where username=%(username)s AND u.password=%(password)s")
	pars = {"username": username, "password": password}
	with base.AdhocQuerier(base.getAdminConn) as querier:
		return parseResponse(querier.query(query, pars))


def hasCredentials(user, password, reqGroup):
	"""returns true if user and password match the db entry and the user
	is in the reqGroup.

	If reqGroup is None, true will be returned if the user/password pair
	is in the user table.
	"""
	if user=="gavoadmin" and base.getConfig("web", "adminpasswd"
			) and password==base.getConfig("web", "adminpasswd"):
		return True

	with base.AdhocQuerier(base.getAdminConn) as querier:
		dbRes = list(querier.query("select password from dc.users where"
			" username=%(user)s", {"user": user}))

		if not dbRes or not dbRes[0]:
			return False
		dbPw = dbRes[0][0]
		if dbPw!=password:
			return False

		if reqGroup:
			dbRes = list(querier.query("select groupname from dc.groups where"
				" username=%(user)s and groupname=%(group)s", 
				{"user": user, "group": reqGroup,}))
			return not not dbRes
		else:
			return True
