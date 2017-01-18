
import numpy as np
from utils.helpers import checkDepth


class ComparativeBase():
    '''
    This class is responsible for comparing light curves of stars according
    to implementations of particular sub-filters

    Attributes
    -----------
    compar_filters : iterable
        List of comparative filter classes

    compar_stars : iterable
        List of Star objects which represent searched group of star objects

    plot_save_path : str, NoneType
        Path to the folder where plots are saved if not None, else
        plots are showed immediately

    plot_save_name : str, NoneType
        Name of plotted file
    '''

    def loadCompStars(self, comp_stars):
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
                space_coordinates.append(self._findClosestCoord(coords))

            elif meth == "average":
                space_coordinates.append(self._findAverageCoord(coords))

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

    def _findClosestCoord(self, coords):
        """Get closest coordinates"""
        checkDepth(coords, 1)

        best_dist = 1e99
        best_coord = None
        for coord in coords:
            dist = np.sqrt(sum([x**2 for x in coord]))

            if dist < best_dist:
                best_dist = dist
                best_coord = coord

        return best_coord

    def _findAverageCoord(self, coords):
        """Get average coordinate"""
        checkDepth(coords, 1)
        x = np.array(coords)
        mean_coord = []
        for dim in range(x.shape[1]):
            mean_coord.append(x[:, dim].mean())

        return mean_coord
