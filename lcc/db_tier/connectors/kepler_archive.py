from __future__ import division


from astropy.coordinates.sky_coordinate import SkyCoord
import kplr

from lcc.db_tier.base_query import LightCurvesDb
from lcc.entities.light_curve import LightCurve
from lcc.entities.star import Star
import numpy as np
from lcc.entities.exceptions import QueryInputError

# TODO: Delete fits files downloaded to .kplr/data


class KeplerArchive(LightCurvesDb):
    '''
    This is connector to Kepler archive of light curves using kplr package

    EXAMPLE
    -------
    queries = [{"ra": 297.8399, "dec": 46.57427, "delta": 10},
               {"kic_num": 9787239},
               {"kic_jkcolor": (0.3, 0.4), "max_records": 5}]
    client = StarsProvider().getProvider(obtain_method="KeplerArchive",
                                         obtain_params=queries)
    stars = client.getStarsWithCurves()
    '''

    RA_IDENT = "kic_degree_ra"
    DEC_IDENT = "kic_dec"

    NAME = "_name"

    IDENTIFIER = {"kic_2mass_id": "2mass",
                  "_name": "kepler"}

    STAR_MORE_MAP = {"kic_zmag": "z_mag",
                     "kic_umag": "u_mag",
                     "kic_kmag": "k_mag",
                     "kic_jmag": "j_mag",
                     "kic_hmag": "h_mag",
                     "kic_imag": "i_mag",
                     "kic_gmag": "g_mag",
                     "kic_teff": "teff"}

    LC_META = {"xlabel": "TIME",
               "xlabel_unit": "BJD - 2454833",
               "ylabel": "Flux",
               "ylabel_unit": "electrons per second",
               "color": "N/A",
               "origin": "Kepler",
               "invert_yaxis": False}

    def __init__(self, obtain_params):
        '''
        Parameters
        ----------
            obtain_params : list, iterable
                Array of dictionaries of queries. There have to be one of these
                set of keys in the dictionary:

                1) "kic_num" - for query by the kepler unique identifier

                2) "ra" (degrees), "dec" (degrees), "delta" (arcseconds) - for query in certain are 
        '''
        if type(obtain_params) == dict:
            obtain_params = [obtain_params]
        self.query = obtain_params
        self.client = kplr.API()

        # Default value to resolve if not area search
        self.delta = None

    def getStarsWithCurves(self):
        """
        Returns
        --------
        list of `Star` objects
            List of Star objects with light curves according to queries
        """
        return self.getStars(lc=True)

    def getStars(self, lc=False):
        """
        Returns
        --------
        list of `Star` objects
            List of Star objects according to queries
        """
        stars = []
        for que in self.query:
            _stars = self._getStars(que, lc)
            if self.delta:
                nearest = que.get("nearest", False)

                checked_stars = self.coneSearch(SkyCoord(self.ra,
                                                         self.dec, unit="deg"),
                                                _stars, self.delta,
                                                nearest=nearest)
                stars += checked_stars
            else:
                stars += _stars
        return stars

    def _getStars(self, que, lc=True):
        """Get stars from one query"""

        kic_num = que.get("kic_num", None)
        ra = que.get("ra", None)
        dec = que.get("dec", None)
        delta = que.get("delta", None)
        if kic_num:
            _stars = [self.client.star(kic_num)]
            self.delta = None
        else:
            if ra and dec and delta:
                try:
                    delta = delta / 3600.0
                    self.ra, self.dec, self.delta = ra, dec, delta
                except:
                    raise QueryInputError(
                        "Coordinates parameters conversion to float has failed")

                query = {"kic_degree_ra": "%f..%f" % (ra - delta, ra + delta),
                         "kic_dec": "%f..%f" % (dec - delta, dec + delta)}

            else:
                query = {}
                for key, value in que.iteritems():
                    if hasattr(value, "__iter__"):
                        query[key] = "%s..%s" % (value[0], value[1])
                    else:
                        query[key] = value

            try:
                _stars = self.client.stars(**query)
            except:
                raise QueryInputError("Unresolved query.\n%s" % query)

        return [self._parseStar(_star, lc) for _star in _stars]

    def _parseStar(self, _star, lc):
        """Transform kplr Star object into package Star object"""

        star = Star()
        more = {}
        ident = {}
        data_dict = _star.__dict__
        for key, value in data_dict.iteritems():

            if key in self.STAR_MORE_MAP.keys():
                more[self.STAR_MORE_MAP[key]] = value

            elif key in self.IDENTIFIER.keys():
                ident[self.IDENTIFIER[key]] = {}
                ident[self.IDENTIFIER[key]]["identifier"] = value
                ident[self.IDENTIFIER[key]]["name"] = "kic_" + value

        ra = data_dict.get(self.RA_IDENT)
        dec = data_dict.get(self.DEC_IDENT)
        star.name = "KIC_" + data_dict.get(self.NAME, "")

        if lc:
            star.lightCurve, _ = self._getLightCurve(_star, lim=1)

        star.coo = (ra, dec)
        star.ident = ident
        star.more = more

        return star

    def _getLightCurve(self, star, lim=None):
        """Obtain light curve"""

        raw_lcs = star.get_light_curves(fetch=False)[:lim]

        ready_lcs = []
        obj_name = None

        for lc in raw_lcs:
            with lc.open() as f:
                obj_name = f[0].header.get("OBJECT")
                hdu_data = f[1].data
                time = hdu_data["time"].tolist()
                flux = hdu_data["sap_flux"].tolist()
                ferr = hdu_data["sap_flux_err"].tolist()

            ready_lcs.append(LightCurve(self._cleanLc(time, flux, ferr),
                                        meta=self.LC_META))

        return ready_lcs, obj_name

    def _cleanLc(self, time, flux, err):
        lc = []
        for t, f, e in zip(time, flux, err):
            obs = [t, f, e]
            if np.NaN not in obs:
                lc.append(obs)
        return lc
