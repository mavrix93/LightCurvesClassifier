import re

import requests
from astropy.coordinates.sky_coordinate import SkyCoord

from lcc.db_tier.base_query import LightCurvesDb
from lcc.entities.exceptions import QueryInputError
from lcc.entities.light_curve import LightCurve
from lcc.entities.star import Star


class Catalina(LightCurvesDb):
    """
    Connector to CRTS survey (http://crts.caltech.edu/). So far stars can be queried by 'id' or by coordinates.
    Number of results from cone search is restricted on the first one. It will be upgraded soon.
    
    Example query
    ------------
    queries = [{"ra" :170.8113, "dec": 34.1737, "delta" : 2}, {"id" : 1135051006365}]
    cat = Catalina(queries)
    stars = cat.getStars()  
    """

    COO_QUERY_ROOT = "http://nunuku.caltech.edu/cgi-bin/getcssconedb_release_img.cgi"
    ID_QUERY_ROOT = "http://nesssi.cacr.caltech.edu/cgi-bin/getcssconedb_id.cgi"

    COO_BASE_QUERY = {"IMG": "nun", "DB": "photcat", ".submit": "Submit",
                      "OUT": "csv", "SHORT": "short", "PLOT": "plot"}

    ID_BASE_QUERY = {".submit": "Submit", "OUT": "csv", "SHORT": "short", "PLOT": "plot"}

    RENAME_FIELDS = [("ra", "RA"), ("dec", "Dec"), ("delta", "Rad"), ("id", "ID")]

    TO_QUO = ["label", "color", "data"]

    QUERY_OPTIONS = ["ra", "dec", "delta", "nearest", "id"]

    LC_META = {"xlabel": "mjd",
               "xlabel_unit": "days",
               "ylabel": "magnitude",
               "ylabel_unit": "mag",
               "color": "V",
               "origin": "CRTS"}

    def __init__(self, queries, multiproc=True):
        if isinstance(queries, dict):
            queries = [queries]
        self.queries = queries
        self.multiproc = multiproc

    def getStar(self, query, load_lc=True):
        """
        Query `Star` object

        Parameters
        ----------
        query : dict
            Database query
            
        load_lc : bool
            Append light curves to star objects

        Returns
        -------
        list
            List of `Star` objects
        """
        stars = self.postQuery(query, load_lc)
        if "RA" in query and "Dec" in query and "Rad" in query:
            stars = self.coneSearch(SkyCoord(float(query["RA"]), float(query["Dec"]), unit="deg"),
                                    stars, float(query["Rad"] / 3600.),
                                    nearest=query.get("nearest", False))
        return stars

    def postQuery(self, query, load_lc=True):
        """
        Post query according to resolved query type
        
        Parameters
        ----------
        query : dict
            Db query
        
        load_lc : bool 
            Option for downloading light curve
            
        Returns
        -------
        list
            Star objects retrieved from the query
        """
        self.parseQuery(query)
        query_type = self.getQueryType(query)
        updated_query = query.copy()
        if query_type == "coo":
            updated_query.update(self.COO_BASE_QUERY)
            root = self.COO_QUERY_ROOT

        elif query_type == "id":
            updated_query.update(self.ID_BASE_QUERY)
            root = self.ID_QUERY_ROOT

        multiple_lcs = query_type == "coo" and not updated_query.get("nearest", False)

        return self.parseRawStar(requests.post(root, data=updated_query).text, load_lc, multiple_lcs)

    def parseRawStar(self, raw_html, load_lc, multiple_lcs=False):
        """
        Parse html retrieved from the query into Star objects
        
        Parameters
        ----------
        raw_html : str
            Raw html retrieved from the query
        
        load_lc : bool
            load_lc : Option for downloading light curve
             
        multiple_lcs : bool
            If True search for all stars will be executed
            
        Returns
        -------
        list
            Star objects retrieved from the query
        """
        # TODO: Multiple lcs loading. So far just the first star is retrieved
        # if multiple_lcs:
        #     json_data = re.search('var dataSet0 = {(?P<json_data>.*)}', raw_html)
        # else:
        #     json_data = re.search('var dataSet0 = {(?P<json_data>.*)}', raw_html)

        json_data = re.search('var dataSet0 = {(?P<json_data>.*)}', raw_html)

        if not json_data:
            return []

        json_data = json_data.group("json_data")

        for to_quo in self.TO_QUO:
            json_data = json_data.replace("{0}".format(to_quo), '"{0}"'.format(to_quo))

        star_id = re.search('ID=(?P<name>.*)&PLOT=plot', raw_html).group("name")

        json_data = eval("{%s}" % json_data)

        star = Star(name=json_data.get("label"), ident={"CRST" : {"name" : star_id}})
        if load_lc:
            lc = LightCurve(json_data["data"])
            star.putLightCurve(lc)
        return [star]

    def parseQuery(self, query):
        """
        Parse user query into query which can be understood by the catalog
        
        Parameters
        ----------
        query : dict
            Db query
        
        Returns
        -------
        NoneType
        """
        for rename_fi in self.RENAME_FIELDS:
            if rename_fi[0] in query:
                query[rename_fi[1]] = query.pop(rename_fi[0])

        # Catalina accepts delta in arcminutes, query inputs are in arseconds
        if "delta" in query:
            query["delta"] = query["delta"] / 60.

    def getQueryType(self, query):
        """
        Resolve query type

        Parameters
        ----------
        query : dict
            Db query

        Returns
        -------
        str
            Query type key
        """
        if "RA" in query and "Dec" in query:
            return "coo"
        elif "ID" in query:
            return "id"
        else:
            raise QueryInputError("Unresolved query type")
