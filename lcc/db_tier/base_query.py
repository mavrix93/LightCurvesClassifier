import abc

import astropy.units as u
from lcc.entities.exceptions import QueryInputError
import numpy as np


class StarsCatalogue(object):
    __metaclass__ = abc.ABCMeta
    '''Common class for all catalogs containing informations about stars'''

    def getStars(self):
        """
        Query `Star` objects

        Returns
        -------
        list
            List of `Star` objects
        """
        raise NotImplementedError

    def coneSearch(self, coo, stars, delta_deg, nearest=False):
        """
        Filter results from cone search

        Parameters
        ----------
        coo : astropy.coordinates.sky_coordinate.SkyCoord
            Center of searching

        stars : list of `Star` objects
            Stars returned by query

        delta_deg: float, astropy.units.quantity.Quantity
            Radius from center of searching

        nearest : bool
            Nearest star to the center of searching is returned if it is True

        Returns
        --------
        list
            List of `Star` objects
        """
        try:
            if not isinstance(delta_deg, u.quantity.Quantity):
                delta_deg = float(delta_deg) * u.deg

            distances = []
            passed_stars = []
            for star in stars:
                dist = coo.separation(star.coo)
                if dist < delta_deg:
                    passed_stars.append(star)
                    distances.append(dist.degree)

        except AttributeError:
            raise QueryInputError("Invalid query coordinates")

        if distances and (nearest or str(nearest).capitalize() == "True"):
            return [passed_stars[np.argmin(distances)]]

        return passed_stars

    def _getRanges(self, ra, dec, arcsec_delta):

        if not ra or not dec or not arcsec_delta:
            return "", "", "", ""
        else:
            delta = float(arcsec_delta) / 3600.
            return float(ra) - float(delta), float(ra) + float(delta), float(dec) - float(delta), float(dec) + float(delta)


class LightCurvesDb(StarsCatalogue):
    __metaclass__ = abc.ABCMeta
    '''This is common class for every database containing light curves'''

    def getStarsWithCurves(self):
        """
        Query `Star` objects

        Returns
        -------
        list
            List of `Star` objects appended by `LightCurve` instances
        """
        raise NotImplementedError
