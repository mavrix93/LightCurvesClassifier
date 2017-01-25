from __future__ import division
import warnings

import numpy as np
from entities.exceptions import QueryInputError
from utils.commons import check_attribute
from utils.helpers import getMeanDict


class StarsFilter(object):
    """
    This class is responsible for filtering stars according to given filters
    (their own implementation of filtering)

    Attributes
    ----------
    descriptors : list
        Descriptor objects

    decider : list
        Decider object

    learned : bool
        It is True after executing the learning

    searched_coords : list
        Parameters space coordinates (got from descriptors) of searched
        objects

    others_coords : list
        Parameters space coordinates (got from descriptors) of contamination
        objects
    """

    def __init__(self, descriptors, deciders):
        """
        Parameters
        ----------
        descriptors : list
            Descriptor objects

        decider :list
            Decider objects
        """

        self.descriptors = descriptors

        if not isinstance(deciders, (list, tuple)):
            deciders = [deciders]
        self.deciders = deciders

        self.learned = False
        self.searched_coords = []
        self.others_coords = []

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
        stars_coords = self.getSpaceCoordinates(stars)

        if pass_method == "all":
            probabilities = self.evaluateCoordinates(stars_coords, "lowest")

        elif pass_method == "mean":
            probabilities = self.evaluateCoordinates(stars_coords, "mean")

        elif pass_method == "one":
            probabilities = self.evaluateCoordinates(stars_coords, "highest")

        else:
            raise QueryInputError("Invalid filtering method")

        return [probab >= treshold for probab in probabilities]

    def learnOnCoords(self, searched_coords, others_coords):
        """
        Train deciders on given sample of coordinates

        Parameters
        ----------
        searched_coords : list, tuple
            Sample of searched coordinates

        others_coords : list, tuple
            Contamination sample of coordinates

        Returns
        -------
            None
        """
        self.coords = searched_coords + others_coords

        for decider in self.deciders:
            decider.learn(searched_coords, others_coords)

        self.learned = True
        self.searched_coords = searched_coords
        self.others_coords = others_coords

    def learn(self, searched, others):
        """
        Train deciders on given sample of `Star` objects

        Parameters
        ----------
        searched : list, tuple
            Sample of searched group of stars

        others : list, tuple
            Contamination sample of stars


        Returns
        -------
            None
        """
        self.learnOnCoords(
            self.getSpaceCoordinates(searched), self.getSpaceCoordinates(others))

    def getSpaceCoordinates(self, stars, get_labels=False):
        """
        Get params space coordinates according to descriptors

        Parameters
        ----------
        stars : list, tuple
            List of `Star` objects

        get_labels : bool
            If True labels are returned with coordinates

        Returns
        -------
        list
            Coordinates of the stars

        list
            Names of the stars
        """
        space_coordinates = []
        labels = []
        for star in stars:
            coords = self._getSpaceCoordinates(star)
            if coords:
                space_coordinates.append(coords)
                labels.append(star.name)
            else:
                warnings.warn("Not all space coordinates have been obtained")

        if get_labels:
            return space_coordinates, labels
        return space_coordinates

    def evaluateStars(self, stars, meth="mean"):
        """
        Get probabilities of membership of inspected stars

        Parameters
        ----------
        stars : list
            Star objects

        meth : str
            Method for filtering:
                mean - mean probability

                highest - highest probability

                lowest - lowest probability

        Returns
        -------
        list
            Probabilities of membership according to selected the method
        """
        stars_coords = self.getSpaceCoordinates(stars)
        return self.evaluateCoordinates(stars_coords, meth)

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

    @check_attribute("learned", True, "raise")
    def getStatistic(self, s_stars, c_stars, treshold=None):
        """
        Parameters
        ----------
        s_stars : list of `Star` objects
            Searched stars

        c_stars : list of `Star` objects
            Contamination stars

        treshold : float
            Treshold value for filtering (number from 0 to 1)

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
        searched_stars_coords = self.getSpaceCoordinates(s_stars)
        contamination_stars_coords = self.getSpaceCoordinates(c_stars)

        return getMeanDict([decider.getStatistic(searched_stars_coords,
                                                 contamination_stars_coords, treshold) for decider in self.deciders])

    def _getSpaceCoordinates(self, star):
        space_coordinate = []
        for descriptor in self.descriptors:
            coo = descriptor.getSpaceCoords([star])
            if coo:
                space_coordinate += coo
            else:
                return False
        return space_coordinate
