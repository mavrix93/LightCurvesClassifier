import re

import requests
from astropy.coordinates.sky_coordinate import SkyCoord
from lcc.db_tier.base_query import LightCurvesDb
from lcc.entities.exceptions import QueryInputError
from lcc.entities.light_curve import LightCurve
from lcc.entities.star import Star


class CatalinaArchive(LightCurvesDb):
    """
    
    """

    COO_QUERY_ROOT = "http://nunuku.caltech.edu/cgi-bin/getcssconedb_release_img.cgi"
    ID_QUERY_ROOT = "http://nesssi.cacr.caltech.edu/cgi-bin/getcssconedb_id.cgi"

    COO_BASE_QUERY = {"IMG": "nun", "DB": "photcat", ".submit": "Submit",
                      "OUT": "csv", "SHORT": "short", "PLOT": "plot"}

    ID_BASE_QUERY = {".submit": "Submit", "OUT": "csv", "SHORT": "short", "PLOT": "plot"}

    RENAME_FIELDS = [("ra", "RA"), ("dec", "Dec"), ("delta", "Rad")]

    TO_QUO = ["label", "color", "data"]

    LC_META = {"xlabel": "mjd",
               "xlabel_unit": "days",
               "ylabel": "magnitude",
               "ylabel_unit": "mag",
               "color": "V",
               "origin": "CRTS"}


    def __init__(self, queries):
        if isinstance(queries, dict):
            queries = [queries]
        self.queries = queries

    def getStarsWithCurves(self):
        return self.getStars(lc=True)

    def getStars(self, lc=False):
        stars = []
        for query in self.queries:
            stars += self.postQuery(query, lc)
            if "RA" in query and "Dec" in query and "Rad" in query:
                stars = self.coneSearch(SkyCoord(float(query["RA"]), float(query["Dec"]), unit="deg"),
                                        stars, float(query["Rad"] / 3600.),
                                        nearest=query.get("nearest", False))
        return stars

    def postQuery(self, query, lc=True):
        self.parseQuery(query)
        query_type = self.getQueryType(query)
        if query_type == "coo":
            query.update(self.COO_BASE_QUERY)
            root = self.COO_QUERY_ROOT
        elif query_type == "id":
            query.update(self.ID_BASE_QUERY)
            root = self.ID_QUERY_ROOT

        return self.parseRawStar(requests.post(root, data=query).text, lc)

    def parseRawStar(self, raw_html, lc):
        json_data = re.search('var dataSet0 = {(?P<json_data>.*)}', raw_html)
        if not json_data:
            return []

        json_data = json_data.group("json_data")

        for to_quo in self.TO_QUO:
            json_data = json_data.replace("{0}".format(to_quo), '"{0}"'.format(to_quo))

        star_id = re.search('ID=(?P<name>.*)&PLOT=plot', raw_html).group("name")

        json_data = eval("{%s}" % json_data)

        star = Star(name=json_data.get("label"), ident={"CRST" : {"name" : star_id}})
        if lc:
            lc = LightCurve(json_data["data"])
        star.putLightCurve(lc)
        return [star]

    def parseQuery(self, query):
        for rename_fi in self.RENAME_FIELDS:
            if rename_fi[0] in query:
                query[rename_fi[1]] = query.pop(rename_fi[0])

    def getQueryType(self, query):
        if "RA" in query and "Dec" in query:
            return "coo"
        elif "ID" in query:
            return "id"
        else:
            raise QueryInputError("Unresolved query type")
