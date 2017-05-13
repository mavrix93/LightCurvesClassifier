from __future__ import division

import warnings

from lcc.entities.exceptions import QueryInputError
from lcc.utils.commons import check_attribute
from lcc.utils.helpers import getMeanDict
import numpy as np
import pandas as pd


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

        if not deciders:
            warnings.warn("There are no deciders!")
        if not descriptors:
            warnings.warn("There are no descriptors!")

        self.learned = False
        self.searched_coords = []
        self.others_coords = []

    def __str__(self, *args, **kwargs):
        txt = "Descriptors: " + \
            ", ".join([desc.__class__.__name__ for desc in self.descriptors])
        txt += "\nDeciders: " + \
            ", ".join([dec.__class__.__name__ for dec in self.deciders])
        if self.learned:
            txt += "\nStar filter is learned\n"
            txt += "It was trained on the sample of %i searched and %i contamination objects" % (
                len(self.searched_coords), len(self.others_coords))
        else:
            txt += "\nStar filter is not learned"
        return txt

    @check_attribute("learned", True, "raise")
    def filterStars(self, stars, pass_method="all"):
        """
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
        """
        stars_coords = self.getSpaceCoordinates(stars)

        treshold = np.mean([dec.treshold for dec in self.deciders])

        if pass_method == "all":
            probabilities = self.evaluateCoordinates(stars_coords, "lowest")

        elif pass_method == "mean":
            probabilities = self.evaluateCoordinates(stars_coords, "mean")

        elif pass_method == "one":
            probabilities = self.evaluateCoordinates(stars_coords, "highest")

        else:
            raise QueryInputError("Invalid filtering method")

        return [stars[i] for i, probab in enumerate(probabilities) if probab >= treshold]

    def learnOnCoords(self, searched_coords, others_coords):
        """
        Train deciders on given sample of coordinates

        Parameters
        ----------
        searched_coords : pandas.DataFram, list, tuple
            Sample of searched coordinates

        others_coords : pandas.DataFram, list, tuple
            Contamination sample of coordinates

        Returns
        -------
            None
        """
        if (isinstance(searched_coords, pd.DataFrame) and
                isinstance(others_coords, pd.DataFrame)):
            searched_coords_data = searched_coords.values.tolist()
            others_coords_data = others_coords.values.tolist()
        else:
            searched_coords_data = list(searched_coords)
            others_coords_data = list(others_coords)

        for decider in self.deciders:
            decider.learn(searched_coords_data, others_coords_data)

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
        coords = self.getSpaceCoordinates(searched+others)
        self.learnOnCoords(coords[:len(searched)], coords[len(searched):])

    def getSpaceCoordinates(self, stars):
        """
        Get params space coordinates according to descriptors

        Parameters
        ----------
        stars : list, tuple
            List of `Star` objects

        Returns
        -------
        pandas.DataFrame
            Coordinates of the stars as pandas DataFrame
        """
        space_coordinates = self._getSpaceCoordinates(stars)
        if isinstance(space_coordinates, np.ndarray):
            space_coordinates = space_coordinates.tolist()
        labels = [st.name for st in stars]

        assert len(space_coordinates) == len(labels)

        desc_labels = []
        for desc in self.descriptors:
            if hasattr(desc.LABEL, "__iter__"):
                desc_labels += desc.LABEL
            else:
                desc_labels.append(desc.LABEL)

        df_coords = pd.DataFrame(
            space_coordinates, columns=desc_labels, index=labels)
        df_coords.fillna(np.NaN)
        df_coords.dropna(inplace=True)

        return df_coords

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
        """
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
        """
        decisions = []
        for decider in self.deciders:
            decisions.append(decider.evaluate(stars_coords))
        if meth == "mean":
            return [round(np.mean(coo), 2) for coo in np.array(decisions).T]

        elif meth == "highest":
            return [round(np.max(coo), 2) for coo in np.array(decisions).T]

        elif meth == "lowest":
            return [round(np.min(coo), 2) for coo in np.array(decisions).T]

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
        searched_stars_coords = self.getSpaceCoordinates(s_stars).values
        contamination_stars_coords = self.getSpaceCoordinates(c_stars).values

        return getMeanDict([decider.getStatistic(searched_stars_coords,
                                                 contamination_stars_coords, treshold) for decider in self.deciders])

    def _getSpaceCoordinates(self, stars):
        space_coordinate = []
        for descriptor in self.descriptors:
            coo = descriptor.getSpaceCoords(stars)
            if not hasattr(coo[0], "__iter__"):
                coo = [[c] for c in coo]

            if not space_coordinate:
                space_coordinate = coo
            else:
                space_coordinate = [list(a)+list(b) for a,b in zip(space_coordinate, coo)]
        return space_coordinate
