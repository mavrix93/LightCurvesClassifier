from __future__ import division

import abc
import collections
import warnings

from lcc.utils.data_analysis import computePrecision
from lcc.utils.helpers import check_depth
import numpy as np


class BaseDecider(object):
    """
    A decider class works with "coordinates" (specification) of objects. It can
    learn identify inspected group of objects according to "coordinates" of 
    searched objects and other objects.

    All decider classes have to inherit this abstract class. That means that they
    need to implement several methods: "learn" and "evaluate". Also all of them
    have to have "treshold" attribute. To be explained read comments below.

    Attributes
    -----------
    treshold : float
        Probability (1.0  means 100 %) level. All objects with probability of
        membership to the group higher then the treshold are considered
        as members.

    treshold = 0.8
    """

    __metaclass__ = abc.ABCMeta

    def learn(self, right_coords, wrong_coords):
        """
        After executing this method the decider object is capable to recognize
        objects according their "coordinates" via "filter" method.

        Parameters
        -----------
        right_coords : list
            "Coordinates" of searched objects

        wrong_coords : list
            "Coordinates" of other objects

        Returns
        -------
        NoneType
            None
        """
        raise NotImplementedError

    def evaluate(self, star_coords):
        """
        Parameters
        -----------
        star_coords : list
            Coordinates of inspected star got from sub-filters

        Returns
        --------
        list of lists
            Probability that inspected star belongs to the searched
            group of objects
        """
        raise NotImplementedError

    def evaluateList(self, stars_coords):
        """
        Parameters
        ----------
        stars_coords : list
            Coordinates of inspected stars (e.g. obtained from sub-filters)

        Returns
        -------
        list
            Probabilities that inspected stars belongs to the searched
            group of objects
        """
        return np.array([self.evaluate(coords) for coords in stars_coords])

    def getBestCoord(self, stars_coords):
        """
        Parameters
        ----------
        stars_coords : list
            Coordinates of inspected stars got from sub-filters

        Returns
        -------
        list
            Coordinates with highest probability of membership to the
            searched group (one list of coordinates)
        """
        check_depth(stars_coords, 2)
        if not len(stars_coords):
            warnings.warn(" There are no stars coordinates to inspect")
            return None

        best_coo = None
        best_prob = 0
        for coords in stars_coords:
            prob = self.evaluate([coords])[0]
            if prob >= best_prob:
                best_coo = coords
                best_prob = prob

        # TODO:
        assert best_coo is not None

        return best_coo

    def filter(self, stars_coords, treshold=None):
        """
        Parameters
        ----------
        stars_coords : list
            Coordinates of inspected stars

        treshold : float
            Treshold value for filtering (number from 0 to 1)

        Returns
        -------
        List of True/False whether coordinates belong to the searched group of objects
        """
        if not treshold:
            treshold = self.treshold
        check_depth(stars_coords, 2)
        return [self.evaluate([coo])[0] >= treshold for coo in stars_coords]

    def getStatistic(self, right_coords, wrong_coords, treshold=None):
        """
        Parameters
        ----------
        right_coords : list
            Parameter-space coordinates of searched objects

        wrong_coords : list
            Parameter-space coordinates of other objects

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
        check_depth(right_coords, 2)
        check_depth(wrong_coords, 2)

        right_num = len(right_coords)
        wrong_num = len(wrong_coords)

        true_pos = sum(
            [1 for guess in self.filter(right_coords, treshold) if guess == True])
        false_neg = right_num - true_pos

        true_neg = sum(
            [1 for guess in self.filter(wrong_coords, treshold) if guess == False])
        false_pos = wrong_num - true_neg

        precision = round(computePrecision(true_pos, false_pos), 3)

        stat = (("precision", precision),
                ("true_positive_rate", round(true_pos / right_num, 3)),
                ("true_negative_rate", round(true_neg / wrong_num, 3)),
                ("false_positive_rate", round(1 - (true_pos / right_num), 3)),
                ("false_negative_rate", round(1 - (true_neg / wrong_num), 3)))

        return collections.OrderedDict(stat)

        """return {"precision" : precision,
                "true_positive_rate" : true_pos / (false_neg + true_pos) ,
                "true_negative_rate" : true_neg / (false_pos + true_neg),
                "false_positive_rate" : false_pos / (false_pos + true_neg),
                "false_negative_rate" : false_neg / (false_neg + true_pos)}"""
