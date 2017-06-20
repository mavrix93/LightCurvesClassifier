import abc

import logging
import numpy as np

from lcc.entities.exceptions import QueryInputError
from lcc.utils.helpers import convert_input_value


class ComparativeBase():
    """
    This class is responsible for comparing light curves of inspected stars
    with the template stars

    Attributes
    -----------
    compar_stars : list, iterable
        List of Star objects which represent searched group of star objects
    """
    __metaclass__ = abc.ABCMeta

    def compareTwoStars(self, *args, **kwargs):
        raise NotImplemented()

    def loadCompStars(self, comp_stars):
        """
        Load comparative stars for the template sample

        Parameters
        ----------
        comp_stars : list
            Stars for the template

        Returns
        -------
            None
        """
        self.comp_stars = comp_stars

    def getFeatures(self, star):
        """
        Get difference in symbolic space of the investigated star from the template

        Parameters
        -----------
        star : lcc.entities.star.Star object
            Star to process

        Returns
        -------
        list
            Difference in symbolic space of the investigated star from the template
        """
        try:
            meth = self.method
        except AttributeError:
            meth = "average"


        coords = [x for x in self._filtOneStar(star, search_opt="all") if x is not None]
        logging.debug("Coords: %s" % coords)

        if meth == "closest":
            return np.min(coords)

        elif meth == "average":
            return np.mean(coords)

        elif meth.startswith("best"):
            n = convert_input_value(meth[4:])

            if isinstance(n, float):
                n = int(len(coords)*n)

            if not meth:
                raise QueryInputError("""Unresolved coordinates calculation method. String 'best' has to
                be followed by integer or float number""")

            return np.mean(np.argsort(coords)[:n])

        else:
            raise QueryInputError("Unresolved coordinates calculation method")



    def _filtOneStar(self, star, *args, **kwargs):
        """
        Calculate distances of inspected star and template stars

        Parameters
        -----------
        star: Star object
            Star to filter

        Returns
        --------
        list
            List of all dissimilarities of inspected star to template stars
        """

        coordinates = []
        # Try every template star
        for comp_star in self.comp_stars:
            if comp_star.lightCurve and star.lightCurve:
                coordinates.append(self.compareTwoStars(star, comp_star))
            else:
                coordinates.append(None)
        return coordinates
