from astroML.classification.gmm_bayes import GMMBayes
from sklearn import svm
from sklearn import tree
from sklearn.naive_bayes import GaussianNB
from sklearn.discriminant_analysis import QuadraticDiscriminantAnalysis as QDA
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis as LDA

from conf import deciders_settings
from entities.exceptions import QueryInputError, LearningError
import numpy as np
from stars_processing.deciders.base_decider import BaseDecider
from utils.helpers import checkDepth


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
        if not right_coords or not wrong_coords:
            raise QueryInputError(
                "Decider can't be learned on an empty sample")

        y = [1 for i in range(len(right_coords))]
        y += [0 for i in range(len(wrong_coords))]
        self.X = np.array(right_coords + wrong_coords)
        self.y = np.array(y)

        if not self.X.any() or not self.y.any():
            raise QueryInputError(
                "No stars have attributes which are needed by filter")

        try:
            self.learner.fit(self.X, self.y)
        except:
            raise LearningError(
                "Could not learn decider on dataset:\nX = %s\n\nlabels = %s" % (self.X, self.y))

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
        checkDepth(prediction, 1)
        where_are_NaNs = np.isnan(prediction)
        prediction[where_are_NaNs] = 0
        return prediction


class LDADec(SupervisedBase):
    """
    Sklearn implementation of Linear Discriminant Analysis

    http://scikit-learn.org/stable/modules/lda_qda.html
    """

    def __init__(self, treshold=None):
        if not treshold:
            treshold = deciders_settings.TRESHOLD
        SupervisedBase.__init__(self, clf=LDA, treshold=treshold)


class GaussianNBDec(SupervisedBase):
    """
    Sklearn implementation of Gaussian Naive Bayes

    http://scikit-learn.org/stable/modules/naive_bayes.html#gaussian-naive-bayes
    """

    def __init__(self, treshold=None):
        if not treshold:
            treshold = deciders_settings.TRESHOLD
        SupervisedBase.__init__(self, clf=GaussianNB, treshold=treshold)


class GMMBayesDec(SupervisedBase):
    """
    Sklearn implementation of Bayesian Regression

    http://scikit-learn.org/stable/modules/linear_model.html#bayesian-regression
    """

    def __init__(self, treshold=None):
        if not treshold:
            treshold = deciders_settings.TRESHOLD
        SupervisedBase.__init__(self, clf=GMMBayes, treshold=treshold)


class QDADec(SupervisedBase):
    """
    Sklearn implementation of Quadratic Discriminant Analysis

    http://scikit-learn.org/stable/modules/lda_qda.html
    """

    def __init__(self, treshold=None):
        if not treshold:
            treshold = deciders_settings.TRESHOLD
        SupervisedBase.__init__(self, clf=QDA, treshold=treshold)


class SVCDec(SupervisedBase):
    """
    Sklearn implementation of Support Vector Machines

    http://scikit-learn.org/stable/modules/svm.html
    """

    def __init__(self, treshold=0.5):
        """
        Parameters
        -----------
        treshold: float
            Border probability value (objects with probability higher then this
            value is considered as searched object)
        """
        self.treshold = treshold
        self.learner = svm.SVC()

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
        return self.learner.predict(coords)


class TreeDec(SupervisedBase):
    """
    Sklearn implementation of Decision Trees

    http://scikit-learn.org/stable/modules/tree.html
    """

    def __init__(self, treshold=0.5):
        """
        Parameters
        -----------
            treshold: float
                Border probability value (objects with probability higher then this
                value is considered as searched object)
        """

        self.treshold = treshold
        self.learner = tree.DecisionTreeClassifier()

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
        return self.learner.predict(coords)
