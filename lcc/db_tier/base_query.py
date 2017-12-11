import abc
import warnings

import astropy.units as u
import numpy as np

from lcc.entities.exceptions import QueryInputError


class StarsCatalogue(abc.ABC):
    """Common class for all catalogs containing information about stars"""

    def getStars(self, load_lc=True):
        """
        Query `Star` objects

        Parameters
        ----------
        load_lc : bool
            Append light curves to star objects

        Returns
        -------
        list
            List of `Star` objects
        """
        # with futures.ProcessPoolExecutor() as executor:
        #     stars_gen = executor.map(self.getStar, self.queries)
        #     stars = []
        #     for st in stars_gen:
        #         stars += st
        #     return stars
        stars = []
        for query in self.queries:
            stars += self.getStar(query)
        return stars

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
                if star.coo:
                    dist = coo.separation(star.coo)
                    if dist < delta_deg:
                        passed_stars.append(star)
                        distances.append(dist.degree)
                else:
                    passed_stars.append(star)
                    distances.append(np.inf)

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
    """This is common class for every database containing light curves"""

    def getStarsWithCurves(self, *args, **kwargs):
        warnings.warn("This method will be deprecated in the future version. Please used getStars() instead")
        return self.getStars(*args, **kwargs)
