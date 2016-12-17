
import numpy as np
from stars_processing.filters_tools.base_filter import BaseFilter, Learnable
from utils.helpers import checkDepth


class ComparingFilter(BaseFilter, Learnable):
    '''
    This class is responsible for comparing light curves of stars according
    to implementations of particular sub-filters

    Attributes
    -----------
    compar_filters : iterable
        List of comparative filter classes

    compar_stars : iterable
        List of Star objects which represent searched group of star objects

    decider : Decider object
        This object learns to recognize and then find searched star objects

    plot_save_path : str, NoneType
        Path to the folder where plots are saved if not None, else
        plots are showed immediately

    plot_save_name : str, NoneType
        Name of plotted file
    '''

    def __init__(self, compar_filters, compar_stars, decider,
                 plot_save_path=None, plot_save_name="ComparingPlot.png",
                 **filters_params):
        """
        Parameters
        -----------
        compar_filters : iterable
            List of comparative filter classes

        compar_stars : iterable
            List of Star objects which represent searched group of star objects

        decider : Decider object
            This object learns to recognize and then find searched star objects

        plot_save_path : str, NoneType
            Path to the folder where plots are saved if not None, else
            plots are showed immediately

        plot_save_name : str, NoneType
            Name of plotted file
        """
        self.compar_filters = [cls(**filters_params) for cls in compar_filters]
        self.comp_stars = compar_stars
        self.decider = decider
        self.plot_save_path = plot_save_path
        self.plot_save_name = plot_save_name

        self.labels = [
            filt.__class__.__name__ + " distance" for filt in self.compar_filters]

        self.learned = False

        # TODO: Get mean probability value
        # if search_opt.startswith("average"):
        #     search_opt, self.avg_num = search_opt[ : len("average") ], search_opt[len("average") : ]

    def applyFilter(self, stars, meth="average"):
        """
        Parameters
        -----------
        stars: iterable
            List of Star objects to filter

        Returns
        --------
        list
            List of Star objects which passed thru filtering
        """

        if not self.learned:
            raise Exception("First you have to learn this compare filter")

        stars_coords = self.getSpaceCoords(stars, meth)
        passed = self.decider.filter(stars_coords)

        return [star for this_passed, star in zip(passed, stars) if this_passed]

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
            probable    : take coordinate with highest probability
                          of membership. Can be performed just
                          on learned decider
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

            elif meth == "probab":
                if not self.learned:
                    raise Exception(
                        "First you have to learn this compare filter")
                space_coordinates.append(self.decider.getBestCoord(coords))

            else:
                raise Exception("Unresolved coordinates calculation method")

        return space_coordinates

    def _filtOneStar(self, star, search_opt="all"):
        '''
        Calculate distances of inspected star and template stars

        Parameters
        -----------
        star: Star object
            Star to filter

        Returns
        --------
        list
            List of all distances (coordinates) of inspected star to all
            template stars
        '''

        coordinates = []
        # Try every template star
        for comp_star in self.comp_stars:
            this_coo_list = []

            # Apply all comparative filters
            for filt in self.compar_filters:
                this_coo_list.append(filt.compareTwoStars(star, comp_star))

            # Return best match if match is sufficient (there is no need to
            # find best match)
            if (search_opt == "passing" and self.decider.filter([this_coo_list])):
                return [this_coo_list]

            coordinates.append(this_coo_list)

        if search_opt == "passing":
            return False

        elif search_opt == "closest":
            return self.decider.getBestCoord(coordinates)

        return coordinates

    def _findClosestCoord(self, coords):
        """Get closest coordinates"""
        checkDepth(coords, 2)

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
        checkDepth(coords, 2)
        x = np.array(coords)
        mean_coord = []
        for dim in range(x.shape[1]):
            mean_coord.append(x[:, dim].mean())

        return mean_coord
