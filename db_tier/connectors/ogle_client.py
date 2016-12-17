'''
Created on Jan 6, 2016

@author: Martin Vo
'''

from astropy.coordinates.sky_coordinate import SkyCoord
import re
import socket
import urllib
from urllib2 import URLError
import urllib2
from warnings import warn

from conf import settings
from db_tier.base_query import LightCurvesDb
from entities.exceptions import NoInternetConnection, QueryInputError
from entities.star import Star
import numpy as np
from utils.helpers import verbose


# Throws:
# NOTE: This is kind of messy version of db connector. Lots of changes in order
# to get clean connector need to be done. Anyway it is working...
# TODO: Area search returns just one star
class OgleII(LightCurvesDb):
    '''
    OgleII class is responsible for searching stars in OGLE db according
    to query. Then it can download light curves and saved them or retrieve
    stars object (with lc, coordinates, name...)
    '''

    ROOT = "http://ogledb.astrouw.edu.pl/~ogle/photdb"
    TARGETS = ["lmc", "smc", "bul", "sco"]

    # QUERY_TYPE = "phot"
    QUERY_TYPE = "bvi"
    MAX_REPETITIONS = 3
    MAX_TIMEOUT = 60

    LC_META = {"xlabel": "hjd",
               "xlabel_unit": "days",
               "ylabel": "magnitude",
               "ylabel_unit": "mag",
               "color": "V",
               "origin": "OgleII"}

    def __init__(self, queries):
        '''
        @param query:    Query is dictionary of query parameters. 
                         In case of containing "starcat" and "target"searching
                         via starcat will be executed.
                         Other case searching via coordinates will be done. Moreover
                         there is possibility to search in magnitude ranges if
                         "minMag" and "maxMag" is in dictionary
        @param ra:     Right Ascension value in degrees
        @param dec:    Declination value in degrees

        EXAMPLE:
        print OgleII({"field":"LMC_SC1","starid":"152248","target":"lmc"}).getStarsWithCurves()
        '''
        self.queries = queries

    def oneQuery(self, query):
        # Query parameters
        self.tmpdir = None
        self.field = ""
        self.starid = ""
        self.use_field = "off"
        self.use_starid = "off"
        self.use_ra = "off"
        self.use_decl = "off"
        self.use_imean = "off"
        self.valmin_imean = ""
        self.valmax_imean = ""
        self.valmin_ra = ""
        self.valmax_ra = ""
        self.valmin_decl = ""
        self.valmax_decl = ""
        self.use_starcat = "off"
        self.starcat = ""
        self.phot = "off"
        self.bvi = "off"

        self.query_err_repetitions = 0

        if (query.get("target") in self.TARGETS):
            self.db_target = query["target"]
        else:
            raise QueryInputError(
                "Unknown given target field %s" % query.get("target"))

        if "starid" in query:
            self.starid = query["starid"]
            self.use_field = "on"
            self.use_starid = "on"

            if ("field" in query):
                self.field = query["field"]

            elif ("field_num" in query):
                target = query["target"]
                if target == "lmc":
                    field_pat = "LMC_SC"
                elif target == "smc":
                    field_pat = "SMC_SC"
                elif target == "bul":
                    field_pat = "BUL_SC"
                else:
                    raise QueryInputError("Unresolved target")

                self.field = field_pat + str(query["field_num"])

        # In case "ra","dec","delta","target" in dict, searching thru
        # coordinates will be done
        elif ("ra" in query and "dec" in query and
              "delta" in query and "target" in query):
            ra = query["ra"]
            dec = query["dec"]
            # If it is not already coordination object
            self.coo = SkyCoord(ra, dec, unit="deg")
            self.delta = query["delta"] / 3600.0
            self.use_ra = "on"
            self.use_decl = "on"

            # Get range of coordinate values
            self._parse_coords_ranges()

        elif "coo" in query and "target" in query:
            self.coo = query["coo"]
            self.use_ra = "on"
            self.use_decl = "on"

            # Get range of coordinate values
            self._parse_coords_ranges()

        else:
            raise QueryInputError("Query option was not resolved")

    def getStars(self):
        '''Get Star objects'''
        res_stars = []
        for query in self.queries:
            self.oneQuery(query)
            try:
                stars = self._post_query()
                if self.use_ra == "on":
                    checked_stars = []
                    for star in stars:
                        if self.coneSearch(star.coo, self.coo, self.delta):
                            checked_stars.append(star)
                    res_stars += checked_stars
                else:
                    res_stars += stars
            except URLError:
                if self.query_err_repetitions < self.MAX_REPETITIONS:
                    self.getStars()
                else:
                    return []
                self.query_err_repetitions += 1

        return res_stars

    def getStarsWithCurves(self):
        '''Get Star objects with light curves'''

        res_stars = []
        for query in self.queries:
            self.oneQuery(query)
            try:
                stars = self._post_query()
            except URLError:
                raise NoInternetConnection(
                    "Connection to OGLEII database failed")

            ready_stars = self._parse_light_curves(stars)

            verbose("Light curves have been saved", 3, settings.VERBOSITY)

            if self.use_ra == "on":
                checked_stars = []
                for star in ready_stars:
                    if self.coneSearch(star.coo, self.coo, self.delta):
                        checked_stars.append(star)
                res_stars += checked_stars
            else:
                res_stars += ready_stars
        return res_stars

    def _post_query(self):
        '''
        This method execute query in OGLE db

        Returns:
        --------
            List of stars meeting query parameters
        '''
        # Number of pages in html file
        PAGE_LEN = 1e10

        # Query parameters
        params = {
            "db_target": self.db_target,
            "dbtyp": "dia2",
            "sort": "field",
            "use_field": self.use_field,
            "val_field": self.field,
            "use_starid": self.use_starid,
            "val_starid": self.starid,
            "disp_starcat": "on",
            "use_starcat": self.use_starcat,
            "disp_ra": "on",
            "use_ra": self.use_ra,
            "valmin_ra": self.valmin_ra,
            "valmax_ra": self.valmax_ra,
            "disp_decl": "on",
            "use_decl": self.use_decl,
            "valmin_decl": self.valmin_decl,
            "valmax_decl": self.valmax_decl,
            "disp_imean": "on",
            "use_imean": self.use_imean,
            "valmin_imean": self.valmin_imean,
            "valmax_imean": self.valmax_imean,
            "disp_pgood": "off",
            "disp_bmean": "on",
            "disp_vmean": "on",
            "disp_imean": "on",
            "disp_imed": "off",
            "disp_bsig": "off",
            "disp_vsig": "off",
            "disp_isig": "off",
            "disp_imederr": "off",
            "disp_ndetect": "off",
            "disp_v_i": "off",
            "disp_b_v": "off",
            "sorting": "ASC",
            "pagelen": PAGE_LEN,
        }

        # Delete unneeded parameters
        for key in params.keys():
            if (params[key] == "off") or (params[key] == ""):
                params.pop(key)
        # Url for query
        url = "%s/query.php?qtype=%s&first=1" % (self.ROOT, self.QUERY_TYPE)

        # Post query
        verbose("OGLEII query is about to start", 3, settings.VERBOSITY)
        try:
            result = urllib2.urlopen(
                url, urllib.urlencode(params), timeout=self.MAX_TIMEOUT)

        # TODO: Catch timeout (repeat?)
        except socket.timeout:
            if self.query_err_repetitions < self.MAX_REPETITIONS:
                self._post_query()
            else:
                raise

            self.query_err_repetitions += 1

        verbose(
            "OGLEII query is done. Parsing result...", 3, settings.VERBOSITY)
        return self._parse_result(result)

    def _parse_result(self, result):
        '''Parsing result from retrieved web page'''
        # NOTE: Order of particular values is hardcoded, it is possible
        # to read input line with order of displayed values

        stars = []
        values = {}
        more = {}
        # Index of line
        idx = None

        # Patterns for searching star values into query result (html file)
        field_starid_pattern = re.compile(
            "^.*jsgetobj.php\?field=(?P<field>[^&]+)\&starid=(?P<starid>\d+).*$")
        tmpdir_pattern = re.compile(
            "<input type='hidden' name='tmpdir' value='(.*)'>")
        value_pattern = re.compile("^.*<td align='right'>(.*)</td>.*$")
        # If query post is successful
        if (result.code == 200):
            for line in result.readlines():
                if line.strip().startswith("<td align="):
                    # Try to match star id (first line of star line, length is
                    # controlled by idx value)
                    field_starid = field_starid_pattern.match(line)
                    # Load star parameters
                    if (idx is not None):
                        # If all star parameters were loaded
                        end_text = '<td align="right"><a href="bvi_query.html">New Query</a></td></tr></table>'
                        if (idx >= 8 or line.strip() == end_text):
                            idx = None
                            # Append star into the stars list and empty star
                            # list
                            values["more"] = more
                            values["coo"] = SkyCoord(values.pop("ra"),
                                                     values.pop("dec"),
                                                     unit="deg")
                            star = Star(**values)

                            stars.append(star)
                            values = {}
                            more = {}

                        else:
                            idx += 1
                            value = value_pattern.match(line).group(1)

                            try:
                                value = float(value)
                            except:
                                idx += 1

                            # Ra
                            if (idx == 1):
                                values["ra"] = value * 15
                            # Decl
                            elif (idx == 2):
                                values["dec"] = value
                            # V mag
                            elif (idx == 3):
                                more["v_mag"] = value
                            # I mag
                            elif (idx == 4):
                                more["i_mag"] = value
                                values["more"] = more
                            # B mag
                            elif (idx == 5):
                                more["b_mag"] = value

                    # If first line of star info
                    if (field_starid):
                        field = field_starid.group("field")
                        starid = field_starid.group("starid")

                        idx = 0
                        og = {}
                        og["field"] = field
                        og["starid"] = starid
                        og["target"] = self.db_target
                        values["ident"] = {
                            self.__class__.__name__: {"db_ident": og, "name": field + "_" + starid}}

                    # Try to match tmpdir (once in result) where query data is
                    # saved
                    tmpdir = tmpdir_pattern.match(line)
                    if (tmpdir):
                        self.tmpdir = tmpdir.group(1)

        verbose("OGLE II query is done. Amount of the stars meeting the parameters: %i" % len(
            stars), 3, settings.VERBOSITY)
        return stars

    def _parse_light_curves(self, stars):
        '''This help method makes query in order to get page with light curve and download them'''

        ready_stars = []
        numStars = len(stars)
        for i, star in enumerate(stars):
            verbose("Parsing query result " + str(i) + "/" +
                    str(numStars), 3, settings.VERBOSITY)

            # Make post request in order to obtain light curves
            self._make_tmpdir(star.ident[self.__class__.__name__]["db_ident"][
                              "field"].lower(), star.ident[self.__class__.__name__]["db_ident"]["starid"])

            # Specific url path to lc into server
            url = "%s/data/%s/%s_i_%s.dat" % (self.ROOT, self.tmpdir, star.ident[self.__class__.__name__][
                                              "db_ident"]["field"].lower(), star.ident[self.__class__.__name__]["db_ident"]["starid"])

            # Parse result and download  (if post is successful)
            result = urllib2.urlopen(url)
            if (result.code == 200):
                star_curve = []
                for line in result.readlines():
                    parts = line.strip().split(" ")
                    star_curve.append(
                        [float(parts[0]), float(parts[1]), float(parts[2])])
                if (star_curve and len(star_curve) != 0):
                    star.putLightCurve(np.array(star_curve), meta=self.LC_META)
            ready_stars.append(star)
        return ready_stars

    def _make_tmpdir(self, field, starid):
        '''Make post request to get temp directory in db for obtaining light curves'''

        params = {
            "field": field,
            "starid": starid,
            "tmpdir": self.tmpdir,
            "db": "DIA",
            "points": "good",
        }

        url = "%s/getobj.php" % self.ROOT
        result = urllib2.urlopen(url, urllib.urlencode(params))
        if (result.code != 200):
            raise Exception("%s %s" % (result.code, result.msg))

    def _parse_coords_ranges(self):
        '''Get coordinates in right format and get coordinates ranges'''
        ra = self.coo.ra.hour
        dec = self.coo.dec.degree
        self.valmin_ra = ra - self.delta / 15.0
        self.valmax_ra = ra + self.delta / 15.0
        self.valmin_decl = dec - self.delta
        self.valmax_decl = dec + self.delta
