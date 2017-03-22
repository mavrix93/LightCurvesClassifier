import abc
import numpy as np

from lcc.entities.exceptions import QueryInputError
from lcc.utils.helpers import convert_input_value


class ComparativeBase():
    '''
    This class is responsible for comparing light curves of inspected stars
    with the template stars

    Attributes
    -----------
    compar_stars : list, iterable
        List of Star objects which represent searched group of star objects
    '''
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

    def getSpaceCoords(self, stars):
        '''
        Apply all filters and get their space coordinates

        Parameters
        -----------
        stars : Star objects
            Stars to filtering

        Returns
        --------
        list
            List of coordinates
        '''
        try:
            meth = self.method
        except AttributeError:
            meth = "average"

        space_coordinates = []
        # PB for star in progressbar(stars,"Obtaining space coordinates: "):
        for star in stars:
            coords = [x for x in self._filtOneStar(star, search_opt="all") if x]
            if meth == "closest":
                space_coordinates.append(np.min(coords))

            elif meth == "average":
                space_coordinates.append(np.mean(coords))

            elif meth.startswith("best"):
                n = convert_input_value(meth[4:])

                if isinstance(n, float):
                    n = int(len(coords)*n)

                if not meth:
                    raise QueryInputError("""Unresolved coordinates calculation method. String 'best' has to
                    be followed by integer or float number""")

                space_coordinates.append(np.mean(np.argsort(coords)[:n]))

            else:
                raise QueryInputError("Unresolved coordinates calculation method")

        return space_coordinates

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
