import requests

from lcc.db_tier.TAP_query import TapClient
from lcc.entities.exceptions import QueryInputError
from lcc.entities.light_curve import LightCurve
from lcc.entities.star import Star


class VizierTapBase(TapClient):
    """
    Base class for all tap connectors using VizieR database. In the most
    situations new connectors will contain just few class attributes and 
    there will not be need to write new or overwrite current methods.

    Attributes
    -----------
    TAP_URL : str
        Url to tap server

    FILES_URL : str
        Path to light curve files storage

    TABLE : str
        Name of queried table

    RA : str
        Name of right ascension column. It should be in degrees, anyway it is
        necessary to convert them

    DEC : str
        Name of declination column. It should be in degrees, anyway it is
        necessary to convert them

    NAME : preformated str
        Preformated string with dictionary keys.

        EXAMPLE
        --------
            "{Field}.{Tile}.{Seqn}"

        Keys represent name of columns

    LC_FILE : str
        Column name which can be used for obtaining light curve files.
        By default it is set to None that means that is not necessary
        to include any other column in order to get light curves

    LC_META : dict
        Meta data for light curve.

        Example
        --------
            {"xlabel" : "Terrestrial time",
           "xlabel_unit" : "days",
           "ylabel" : "Flux",
           "ylabel_unit" : "Electrons per second",
           "color" : "N/A",
           "invert_yaxis" : False}

        Light curve is expected by default (magnitudes and Julian days)

    TIME_COL : int
        Number (starts with 0) of times column in data file

    MAG_COL : int
        Number (starts with 0) of magnitudes column in data file

    ERR_COL : int
        Number (starts with 0) of errors column in data file

    ERR_MAG_RATIO : float:
        Ratio between error and magnitude values

        Note:
            Added because of Corot Archive of Faint Stars.

    IDENT_MAP : ordered dict
        Ordered dictionary of "name of database" : "column name/s
        of identifiers"

        Example
        --------
            IDENT_MAP = {"Macho" :  ("Field", "Tile", "Seqn") }

            This allows NAME attribute to access these keys (see above)
            and construct unique identifier for the star.

        For one item dictionaries can be used simple dictionary, because
        there is no need to keep order of items.

    MORE_MAP : ordered dict
        Ordered dictionary of "column names" : "key in new dictionary which
        is be stored in Star object"

        Example
        --------
            MORE_MAP = collections.OrderedDict((("Per", "period"),
                                                ("Class" , "var_type"),
                                                ("Jmag" , "j_mag"),
                                                ("Kmag" , "k_mag"),
                                                ("Hmag" , "h_mag")))


    Methods
    --------
    This class inherits TapClient which brings methods for creating,
    posting and returning tap queries. Methods of this class manage
    results and create Star objects and light curves.

    There is no need overwrite methods in inherited classes in the most
    cases. Anyway obtaining light curves can be different for many
    databases. In this case it would be sufficient to just implement
    new _getLightCurve method.

    Brief description of methods can be found below at their declaration.
    """

    # Common attribute for all vizier tap connectors
    TAP_URL = "http://tapvizier.u-strasbg.fr/TAPVizieR/tap"

    # Most common attributes - can be overwritten #
    RA = "RAJ2000"
    DEC = "DEJ2000"

    LC_FILE = None

    TIME_COL = 0
    MAG_COL = 1
    ERR_COL = 2

    ERR_MAG_RATIO = 1.

    # Split at any number of white spaces
    DELIM = None

    def __init__(self, queries):
        """
        Parameters
        -----------
        queries : list, dict
            List of queries. Each query is dictionary of query parameters
            and its values
        """
        # Case of just one query
        if isinstance(queries, dict):
            queries = [queries]

        self.queries = queries

    # TODO multiprocessing
    def getStars(self, load_lc=True, **kwargs):
        """
        Get star objects with light curves

        Parameters
        ----------
        load_lc : bool
            Star is appended by light curve if True
            
        kwargs : dict
            Optional parameters which have effect just if certain database
            provides this option.

            For example CoRoT archive contains very large light curves,
            so the dimension of light curve can be reduced by `max_bins`
            keyword.

        Returns
        --------
        list
            List of stars with their light curves
        """

        select = set([self.RA, self.DEC, self.LC_FILE] + self.MORE_MAP.keys())

        for val in self.IDENT_MAP.values():
            if isinstance(val, (tuple, list, set)):
                for it in val:
                    select.add(it)
            else:
                select.add(val)

        select = [s for s in select if s]
        select = list(select)

        raw_stars = []
        for _que in self.queries:
            que = _que.copy()
            if "ra" in que and "dec" in que:
                que[self.RA] = que.pop("ra")
                que[self.DEC] = que.pop("dec")
                if "delta" in que:
                    delta = que.pop("delta")
                    que[self.RA], que[self.DEC] = self._areaSearch(
                        que[self.RA], que[self.DEC], delta)

            conditions = []
            for key, value in que.iteritems():
                if isinstance(value, (list, tuple)):
                    if len(value) == 2:
                        conditions.append((key, value[0], value[1]))
                    else:
                        raise QueryInputError("Invalid query range")
                else:
                    if key != "nearest":
                        conditions.append((key, value))

            query_inp = {"table": self.TABLE,
                         "select": select,
                         "conditions": conditions,
                         "URL": self.TAP_URL}
            res = self.postQuery(query_inp)
            if res:
                raw_stars += res

        return self._createStar(raw_stars, select, load_lc, **kwargs)

    def _createStar(self, data, keys, lc_opt, **kwargs):
        """
        Create Star objects from query result

        Parameters
        ----------
        data : list
            Result from query

        keys : list
            Name of columns of data

        lc_opt : bool
            Obtain light curves if True

        Returns
        --------
        list
            List of Star objects
        """
        stars = []
        for raw_star in data:
            ident = {}
            for key, value in self.IDENT_MAP.iteritems():
                db_ident = {}
                if isinstance(value, (list, tuple)):
                    for ide in value:
                        db_ident[ide] = raw_star[keys.index(ide)]
                    name = self.NAME.format(**db_ident)
                else:
                    name = raw_star[keys.index(value)]

                if not db_ident:
                    db_ident = None

                ident[key] = {"name": name, "db_ident": db_ident}

            more = {}
            for key, value in self.MORE_MAP.iteritems():
                more_item = raw_star[keys.index(key)]
                more[value] = more_item
            raw_star_dict = dict(zip(keys, raw_star))

            star = Star(name=self.NAME.format(**raw_star_dict),
                        coo=(raw_star_dict[self.RA],
                             raw_star_dict[self.DEC]),
                        ident=ident,
                        more=more)

            if lc_opt:
                star.putLightCurve(self._getLightCurve(star=star,
                                                       file_name=raw_star_dict.get(
                                                           self.LC_FILE, None),
                                                       **kwargs))
            stars.append(star)
        return stars

    def _getLightCurve(self, star, do_per=False, period_key="period",
                       **kwargs):
        """
        Obtain the light curve

        Parameters
        -----------
        star : Star instance
             Star boy object constructed from query looking
             for his light curve :)

        do_per : bool
            If True phase curve is returned instead

        period_key : str
            Key in star.more dictionary for value of period length

        Returns
        -------
        tuple
            Tuple of times, mags, errors lists
        """
        if do_per:
            period = star.more.get(period_key, None)
            if period:
                self.LC_META = {"xlabel": "Period",
                                "xlabel_unit": "phase"}
        else:
            period = 0

        url = self.LC_URL.format(macho_name=star.name, period=period)

        response = requests.get(url)
        time = []
        mag = []
        err = []
        lcs = []
        for line in response.iter_lines():
            line = line.strip()

            if not line.startswith((" ", "#")):
                parts = line.split(self.DELIM)
                if len(parts) == 3:
                    time.append(float(parts[self.TIME_COL]))
                    mag.append(float(parts[self.MAG_COL]))
                    err.append(float(parts[self.ERR_COL]) / self.ERR_MAG_RATIO)
            else:
                if line.startswith("# m = -1"):
                    meta = self.LC_META.copy()
                    meta["color"] = "B"
                elif line.startswith("# m = -2"):
                    lcs.append(LightCurve([time, mag, err], meta))
                    time, mag, err = [], [], []

                    meta = self.LC_META.copy()
                    meta["color"] = "R"
        lcs.append(LightCurve([time, mag, err], meta))

        return lcs
