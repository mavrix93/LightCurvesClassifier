
import numpy as np
import abc


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

    def getSpaceCoords(self, stars, meth="average"):
        '''
        Apply all filters and get their space coordinates

        Parameters
        -----------
        stars : Star objects
            Stars to filtering

        meth : str
            Method key for calculating distance from comparative objects

            average     : take mean distance in each coordinate as
                          object coordinate
            closest     : take coordinate with closest distance as
                          object coordinate
        Returns
        --------
        list
            List of coordinates
        '''
        space_coordinates = []
        # PB for star in progressbar(stars,"Obtaining space coordinates: "):
        for star in stars:
            coords = self._filtOneStar(star, search_opt="all")
            if meth == "closest":
                space_coordinates.append(np.min(coords))

            elif meth == "average":
                space_coordinates.append(np.mean(coords))

            else:
                raise Exception("Unresolved coordinates calculation method")

        return space_coordinates

    def _filtOneStar(self, star, *args, **kwargs):
        '''
        Calculate distances of inspected star and template stars

        Parameters
        -----------
        star: Star object
            Star to filter

        Returns
        --------
        list
            List of all dissimilarities of inspected star to template stars
        '''

        coordinates = []
        # Try every template star
        for comp_star in self.comp_stars:
            coordinates.append(self.compareTwoStars(star, comp_star))

        return coordinates
