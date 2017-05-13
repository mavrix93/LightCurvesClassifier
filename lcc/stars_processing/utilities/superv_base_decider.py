import numpy as np


from lcc.entities.exceptions import LearningError, QueryInputError
from lcc.stars_processing.utilities.base_decider import BaseDecider
from lcc.utils.helpers import check_depth


class SupervisedBase(BaseDecider):
    """
    Base class for `sklearn` library supervised classes transformed
    to the package content. It is not intended to use this directly,
    but thru certain method subclasses.

    Attributes
    ----------
    treshold : float
        Border probability value (objects with probability higher then this
        value is considered as searched object)

    learner : sklearn object
        Learner object for desired method of supervised learning
    """

    def __init__(self, clf, treshold=0.5):
        """
        Parameters
        -----------
        treshold: float
            Border probability value (objects with probability higher then this
            value is considered as searched object)

        learner: sklearn object
            Learner object for desired method of supervised learning
        """

        self.treshold = treshold
        self.learner = clf()

    def learn(self, right_coords, wrong_coords):
        """
        Learn to recognize objects

        Parameters
        -----------
        right_coords: iterable
            List of coordinates (list of numbers) of searched objects

        wrong_coords: iterable
            List of coordinates (list of numbers) of contamination objects

        Returns
        --------
        NoneType
            None
        """
        right_coords = list(right_coords)
        wrong_coords = list(wrong_coords)

        if not len(right_coords) or not len(wrong_coords):
            raise QueryInputError(
                "Decider can't be learned on an empty sample\nGot\tsearched:%s\tothers%s" % (right_coords, wrong_coords))

        y = [1 for i in range(len(right_coords))]
        y += [0 for i in range(len(wrong_coords))]
        self.X = np.array(right_coords + wrong_coords)
        self.y = np.array(y)

        if not self.X.any() or not self.y.any():
            raise QueryInputError(
                "No stars have an attribute which are needed by filter")

        try:
            self.learner.fit(self.X, self.y)
        except Exception as e:
            raise LearningError(str(e) +
                                "\nCould not learn decider on the dataset:\nX = %s\n\nlabels = %s" % (self.X, self.y))

    def evaluate(self, coords):
        """
        Get probability of membership

        Parameters
        ----------
        coords : list of lists
            List of prameter space coordinates

        Returns
        -------
        list of floats
            List of probabilities
        """
        # TODO:
        # if coords != np.ndarray: coords = np.array( coords )
        # checkDepth(coords, 2)
        prediction = self.learner.predict_proba(coords)[:, 1]
        check_depth(prediction, 1)
        where_are_NaNs = np.isnan(prediction)
        prediction[where_are_NaNs] = 0
        return prediction
