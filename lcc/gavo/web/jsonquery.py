"""
Fast Web->DB->JSON machinery, for now only for the portal page.  It's
not quite clear to me yet what to do with this kind of thing.

It would seem we could do with more of these very lightweight
things; on the other hand, these bypass all metadata mangement...
ah, let's see.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import json

from nevow import rend
from nevow import inevow

from gavo import base


# these are the fields necessary for formatting resource headers
RESMETA_FIELDS = ("title, accessurl, referenceurl,"
	" sourcerd, resid, owner, browseable")


class JSONQuery(rend.Page):
	"""A resource returning Json for the database query given in the
	query class attribute (and potentially some arguments).

	TODO: we should do some more sensible error handling.
	"""
	def renderHTTP(self, ctx):
		queryArgs = dict((key, value[0])
			for key, value in inevow.IRequest(ctx).args.iteritems())

		with base.getTableConn() as conn:
			res = list(conn.queryToDicts(
				self.query, queryArgs))

		request = inevow.IRequest(ctx)
		request.setHeader("content-type", "text/json")
		return json.dumps(res)


class Titles(JSONQuery):
	query = (
		"SELECT "+RESMETA_FIELDS+
		" FROM dc.resources"
		"   NATURAL JOIN dc.interfaces"
		"   NATURAL JOIN dc.sets"
		" WHERE setname='local'"
		" AND NOT deleted"
		" ORDER BY title")


class Subjects(JSONQuery):
	query = (
		"SELECT subject, count(*) as numMatch"
		" FROM dc.subjects"
		"   NATURAL JOIN dc.sets"
		" WHERE setname='local'"
		" AND NOT deleted"
		" GROUP BY subject"
		" ORDER BY subject")


class Authors(JSONQuery):
	query = (
		"SELECT author, count(*) as numMatch"
		" FROM dc.authors"
		"   NATURAL JOIN dc.sets"
		" WHERE setname='local'"
		" AND NOT deleted"
		" GROUP BY author"
		" ORDER BY author")


class ByFulltext(JSONQuery):
	query = (
		"SELECT DISTINCT "+RESMETA_FIELDS+
		" FROM dc.resources"
		"   NATURAL JOIN dc.interfaces"
		"   NATURAL JOIN dc.subjects"
		"   NATURAL JOIN dc.sets"
		" WHERE setname='local'"
		" AND NOT deleted"
		" AND (to_tsvector('english', description) || to_tsvector(subject) "
		"   || to_tsvector('english', title) || to_tsvector(authors))"
		"  @@ plainto_tsquery(%(q)s)"
		" ORDER BY title")


class BySubject(JSONQuery):
	query = (
		"SELECT "+RESMETA_FIELDS+
		" FROM dc.resources"
		"   NATURAL JOIN dc.interfaces"
		"   NATURAL JOIN dc.subjects"
		"   NATURAL JOIN dc.sets"
		" WHERE setname='local'"
		" AND subject=%(subject)s"
		" AND NOT deleted"
		" ORDER BY title")


class ByAuthor(JSONQuery):
	query = (
		"SELECT "+RESMETA_FIELDS+
		"  FROM dc.resources"
		"    NATURAL JOIN dc.interfaces"
		"    NATURAL JOIN dc.authors"
		"    NATURAL JOIN dc.sets"
		" WHERE setname='local'"
		" AND author=%(author)s"
		" AND NOT deleted"
		" ORDER BY title")


class ServiceInfo(JSONQuery):
	query = (
		"SELECT title, description, authors,"
		"    to_char(dateUpdated, 'YYYY-MM-DD') as lastupdate,"
		"    referenceURL, accessURL"
		"  FROM dc.interfaces"
		"    NATURAL JOIN dc.sets"
		"    RIGHT OUTER JOIN dc.resources USING (sourcerd, resid)"
		"  WHERE setname='local'"
		"  AND resId=%(resId)s and sourceRd=%(sourceRD)s")


class PortalPage(rend.Page):
	child_titles = Titles()
	child_subjects = Subjects()
	child_authors = Authors()
	child_bySubject = BySubject()
	child_byAuthor = ByAuthor()
	child_byFulltext = ByFulltext()
	child_serviceInfo = ServiceInfo()
