from astroML.classification.gmm_bayes import GMMBayes
from sklearn import svm
from sklearn import tree
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis as LDA
from sklearn.discriminant_analysis import QuadraticDiscriminantAnalysis as QDA
from sklearn.naive_bayes import GaussianNB

from lcc.stars_processing.utilities.superv_base_decider import SupervisedBase


class LDADec(SupervisedBase):
    """
    Sklearn implementation of Linear Discriminant Analysis

    http://scikit-learn.org/stable/modules/lda_qda.html
    """

    def __init__(self, treshold=0.5):
        SupervisedBase.__init__(self, clf=LDA, treshold=treshold)


class GaussianNBDec(SupervisedBase):
    """
    Sklearn implementation of Gaussian Naive Bayes

    http://scikit-learn.org/stable/modules/naive_bayes.html#gaussian-naive-bayes
    """

    def __init__(self, treshold=0.5):
        SupervisedBase.__init__(self, clf=GaussianNB, treshold=treshold)


class GMMBayesDec(SupervisedBase):
    """
    Sklearn implementation of Bayesian Regression

    http://scikit-learn.org/stable/modules/linear_model.html#bayesian-regression
    """

    def __init__(self, treshold=0.5):
        SupervisedBase.__init__(self, clf=GMMBayes, treshold=treshold)


class QDADec(SupervisedBase):
    """
    Sklearn implementation of Quadratic Discriminant Analysis

    http://scikit-learn.org/stable/modules/lda_qda.html
    """

    def __init__(self, treshold=0.5):
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
        self.learner = svm.SVC(probability=True)


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
