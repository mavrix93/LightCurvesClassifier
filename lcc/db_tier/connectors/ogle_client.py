from astropy.coordinates.sky_coordinate import SkyCoord
from bs4 import BeautifulSoup
import re
import urllib
import urllib2
import warnings

from lcc.db_tier.base_query import LightCurvesDb
from lcc.entities.exceptions import QueryInputError
from lcc.entities.star import Star
import numpy as np


class OgleII(LightCurvesDb):
    '''
    Connector to OGLEII. It is divided into two subdatabases - "phot" and "bvi".
    The first one contains light curves and metadata about coordinates, identifiers
    and V magnitude. The second one also contains information about V and I. 

    Identifier of the stars in OgleII db are: field, starid and target.

    In case of cone search (if coordinates are provided), "nearest" key can
    be used. If it is True just nearest star to the target point is returned.

    Example:
    --------
    que1 = {"ra": 5.549147 * 15,
       "dec": -70.55792, "delta": 5, "nearest": True}
    que2 = {"field":"LMC_SC1","starid":"152248","target":"lmc"}

    client = StarsProvider().getProvider(
        obtain_method="OgleII", obtain_params=[que1, que2])
    stars = client.getStarsWithCurves()
    '''

    ROOT = "http://ogledb.astrouw.edu.pl/~ogle/photdb"

    BVI_TARGETS = ["lmc", "smc", "bul"]
    PHOT_TARGETS = ["lmc", "smc", "bul", "car"]

    QUERY_TYPES = ["bvi", "phot"]

    MAX_TIMEOUT = 60

    LC_META = {"xlabel": "hjd",
               "xlabel_unit": "days",
               "ylabel": "magnitude",
               "ylabel_unit": "mag",
               "color": "V",
               "origin": "OgleII"}

    COL_MAP = {"Field": "field",
               "StarID": "starid",
               "RA": "ra",
               "Decl": "dec",
               "V": "v_mag",
               "I": "i_mag",
               "B": "b_mag"}

    def __init__(self, queries):
        '''
        Parameters
        ----------
        queries : list, dict, iterable
            Query is list of dictionaries of query parameters or single
            dictionary.
        '''
        if isinstance(queries, dict):
            queries = [queries]
        self.queries = self._parseQueries(queries)

    def getStarsWithCurves(self):
        return self.getStars(lc=True)

    def getStars(self, lc=False):
        stars = []
        for query in self.queries:
            stars += self.postQuery(query, lc)
            if "ra" in query and "dec" in query and "delta" in query:
                stars = self.coneSearch(SkyCoord(float(query["ra"]), float(query["dec"]), unit="deg"),
                                        stars, float(query["delta"] / 3600.),
                                        nearest=query.get("nearest", False))
        return stars

    def postQuery(self, query, lc):
        PAGE_LEN = 1e10
        valmin_ra, valmax_ra, valmin_dec, valmax_dec = self._getRanges(query.get("ra"),
                                                                       query.get(
                                                                           "dec"),
                                                                       query.get("delta"))
        if valmax_ra and valmax_ra:
            valmax_ra = valmax_ra / 15.
            valmin_ra = valmin_ra / 15.

        params = {
            "db_target": query.get("target"),
            "dbtyp": "dia2",
            "sort": "field",
            "use_field": "field" in query,
            "val_field": query.get("field"),
            "use_starid": "starid" in query,
            "val_starid": query.get("starid"),
            "disp_starcat": "off",
            "use_starcat": "off",
            "disp_ra": "on",
            "use_ra": valmin_ra != "",
            "valmin_ra": valmin_ra,
            "valmax_ra": valmax_ra,
            "disp_decl": "on",
            "use_decl": valmin_dec != "",
            "valmin_decl": valmin_dec,
            "valmax_decl": valmax_dec,
            "disp_imean": "on",
            "use_imean": "mag_i_min" in query,
            "valmin_imean": query.get("mag_i_min"),
            "valmax_imean": query.get("mag_i_max"),
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
        to_del = []
        for key, value in params.iteritems():
            if not value or value == "off":
                to_del.append(key)
        # Url for query
        url = "%s/query.php?qtype=%s&first=1" % (self.ROOT, query.get("db"))
        [params.pop(x, None) for x in to_del]
        result = urllib2.urlopen(
            url, urllib.urlencode(params), timeout=100)
        return self._parseResult(result, lc=lc)

    def _parseQueries(self, queries):
        todel_queries = []
        new_queries = []
        for i, query in enumerate(queries):
            if "db" not in query:
                query["db"] = self.QUERY_TYPES[0]

            if "coo" in query and isinstance(query["coo"], SkyCoord) and "delta" in query:
                todel_queries.append(i)
                coo = query["coo"]
                query["ra"] = coo.ra.degree
                query["dec"] = coo.dec.degree

            if "ra" in query and "dec" in query and "target" not in query:
                todel_queries.append(i)

                if query["db"] == "phot":
                    targets = self.PHOT_TARGETS
                else:
                    targets = self.BVI_TARGETS

                for target in targets:
                    z = query.copy()
                    z["target"] = target
                    new_queries.append(z)

            elif "starid" in query:
                if "field" in query:
                    query["target"] = query["field"][:3].lower()
                elif "field_num" in query and "target" in query:
                    query["field"] = query[
                        "target"].upper() + "_SC" + str(query["field_num"])
                else:
                    raise QueryInputError("Unresolved target")

            if query["db"] not in self.QUERY_TYPES:
                raise QueryInputError(
                    "Invalid db. Available OgleII databases: %s" % self.QUERY_TYPES)

        return [item for i, item in enumerate(
            queries) if i not in todel_queries] + new_queries

    def _parseResult(self, result, lc=False):
        START_TABLE = "<p><table"
        END_TABLE = "</table>"

        if result.code != 200:
            warnings.warn("Website has not returned 200 status")
            return []

        lc_tmp = None
        raw_table = ""
        skip = True
        for line in result.readlines():
            if skip:
                if line.strip().startswith(START_TABLE):
                    raw_table += line[len("<p>"):]
                    skip = False
                if lc and line.strip().startswith("<input type='hidden'"):
                    tmpdir_pattern = re.compile(
                        "<input type='hidden' name='tmpdir' value='(.*)'>")
                    tmpdir = tmpdir_pattern.match(line)
                    if tmpdir:
                        lc_tmp = tmpdir.group(1)

            else:
                if line.strip().startswith(END_TABLE):
                    break
                raw_table += line

        if not raw_table:
            return []

        soup = BeautifulSoup(raw_table, "lxml")
        table = soup.find('table')
        rows = table.findAll('tr')

        res_rows = []
        for tr in rows[1:]:
            cols = tr.findAll('td')
            res_cols = []
            for td in cols:
                res_cols.append(td.find(text=True))
            res_rows.append(res_cols)

        header = [th.find(text=True) for th in table.findAll("th")]
        return self._createStars(header, res_rows, lc_tmp)

    def _createStars(self, header, rows, lc_tmp):
        # [u'No', u'Field', u'StarID', u'RA', u'Decl', u'V', u'I', u'B']
        # [u'No', u'Field', u'StarID', u'RA', u'Decl', u'I']

        cols_map = self._parseHeader(header)
        stars = []
        for row in rows:
            field = str(row[cols_map.get("field")])
            starid = int(row[cols_map.get("starid")])
            ra = float(row[cols_map.get("ra")])
            dec = float(row[cols_map.get("dec")])

            colors = ["i_mag", "b_mag", "v_mag"]
            more = {}
            for col in colors:
                if cols_map.get(col) and cols_map.get(col):
                    try:
                        more[col] = float(row[cols_map.get(col)])
                    except:
                        pass

            name = field + "_" + str(starid)
            coo = (ra * 15, dec, "deg")

            ident = {"OgleII": {"name": name,
                                "db_ident": {"field": field,
                                             "starid": starid}}}

            st = Star(ident, name, coo, more)

            if lc_tmp:
                lc = self._getLc(field, starid, lc_tmp)
                if lc and len(lc) != 0:
                    st.putLightCurve(np.array(lc), meta=self.LC_META)

            stars.append(st)
        return stars

    def _parseHeader(self, header):
        cols_map = {}
        for i, col in enumerate(header):
            if col in self.COL_MAP.keys():
                cols_map[self.COL_MAP[col]] = i
        return cols_map

    def _getLc(self, field, starid, lc_tmp):
        params = {
            "field": field,
            "starid": starid,
            "tmpdir": lc_tmp,
            "db": "DIA",
            "points": "good",
        }

        _url = "%s/getobj.php" % self.ROOT
        _result = urllib2.urlopen(_url, urllib.urlencode(params))

        url = "%s/data/%s/%s_i_%s.dat" % (self.ROOT,
                                          lc_tmp, field.lower(), starid)
        result = urllib2.urlopen(url)

        if (result.code == 200):
            star_curve = []
            for line in result.readlines():
                parts = line.strip().split(" ")
                star_curve.append(
                    [round(float(parts[0]), 4), round(float(parts[1]), 3), round(float(parts[2]), 3)])
            return star_curve
