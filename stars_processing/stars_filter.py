from __future__ import division
import warnings

import numpy as np
from entities.exceptions import QueryInputError
from utils.commons import check_attribute


class StarsFilter(object):
    """
    This class is responsible for filtering stars according to given filters
    (their own implementation of filtering)
    """

    def __init__(self, descriptors, deciders):

        self.descriptors = descriptors

        if not isinstance(deciders, (list, tuple)):
            deciders = [deciders]
        self.deciders = deciders
        self.learned = False

    @check_attribute("learned", True, "raise")
    def filterStars(self, stars, pass_method="all", treshold=0.5):
        '''
        Apply all deciders

        Parameters
        ----------
        stars : list, iterable
            Star objects to be filtered

        pass_method : str
            Inspected star pass if it fulfill the selected condition.
            Methods for filtering:
                all - all probabilities have to be greater then the treshold

                mean - mean probability has to be greater then the treshold

                one - at least one has to be greater then the treshold

        Returns
        -------
        list of `Star`s
            Stars which passed thru filtering
        '''
        stars_coords = self.assignSpaceCoordinates(stars)

        if pass_method == "all":
            probabilities = self.evaluateCoordinates(stars_coords, "lowest")

        elif pass_method == "mean":
            probabilities = self.evaluateCoordinates(stars_coords, "mean")

        elif pass_method == "one":
            probabilities = self.evaluateCoordinates(stars_coords, "highest")

        else:
            raise QueryInputError("Invalid filtering method")

        return [probab >= treshold for probab in probabilities]

    def learn(self, searched, others):
        searched_coords = self.assignSpaceCoordinates(searched)
        others_coords = self.assignSpaceCoordinates(others)

        self.coords = searched_coords + others_coords

        for decider in self.deciders:
            decider.learn(searched_coords, others_coords)

        self.learned = True

    @check_attribute("learned", True, "raise")
    def assignSpaceCoordinates(self, stars):
        space_coordinates = []
        for star in stars:
            coords = self._assignSpaceCoordinates(star)
            if coords:
                space_coordinates.append(coords)
            else:
                warnings.warn("Not all space coordinates have been obtained")
        return space_coordinates

    @check_attribute("learned", True, "raise")
    def evaluateCoordinates(self, stars_coords, meth="mean"):
        '''
        Get probability of membership calculated from all deciders

        Parameters
        ----------
        stars_coords : list, iterable
            List of coordinates (lists)

        meth : str
            Method for filtering:
                mean - mean probability

                highest - highest probability

                lowest - lowest probability

        Returns
        -------
        list
            Probabilities of membership according to selected the method
        '''
        decisions = []
        for decider in self.deciders:
            decisions.append(decider.evaluate(stars_coords))

        if meth == "mean":
            return [np.mean(coo) for coo in np.array(decisions).T]

        elif meth == "highest":
            return [np.max(coo) for coo in np.array(decisions).T]

        elif meth == "lowest":
            return [np.min(coo) for coo in np.array(decisions).T]

        else:
            raise QueryInputError(
                "Invalid method for calculating membership probability")

    def _assignSpaceCoordinates(self, star):
        space_coordinate = []
        for descriptor in self.descriptors:
            coo = descriptor.getSpaceCoords([star])
            if coo:
                space_coordinate += coo[0]
            else:
                return False
        return space_coordinate

    @check_attribute("learned", True, "raise")
    def getStatistic(self, s_stars, c_stars):
        """
        Parameters
        ----------
        s_stars : list of `Star` objects
            Searched stars

        c_stars : list of `Star` objects
            Contamination stars

        Returns
        -------
        statistic information : dict

            precision (float)
                True positive / (true positive + false positive)

            true_positive_rate (float)
                Proportion of positives that are correctly identified as such

            true_negative_rate :(float)
                Proportion of negatives that are correctly identified as such

            false_positive_rate (float)
                Proportion of positives that are incorrectly identified
                as negatives

            false_negative_rate (float)
                Proportion of negatives that are incorrectly identified
                as positives
        """
        searched_stars_coords = self.assignSpaceCoordinates(s_stars)
        contamination_stars_coords = self.assignSpaceCoordinates(c_stars)

        return [decider.getStatistic(searched_stars_coords, contamination_stars_coords) for decider in self.deciders]
