from sklearn import svm
from sklearn import tree
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis as LDA
from sklearn.discriminant_analysis import QuadraticDiscriminantAnalysis as QDA
from sklearn.naive_bayes import GaussianNB
from sklearn.ensemble import (RandomForestClassifier, ExtraTreesClassifier,
                              AdaBoostClassifier, GradientBoostingClassifier)

from lcc.stars_processing.utilities.superv_base_decider import SupervisedBase


class LDADec(SupervisedBase):
    """
    Sklearn implementation of Linear Discriminant Analysis

    http://scikit-learn.org/stable/modules/lda_qda.html
    """

    def __init__(self, treshold=0.5, solver="svd", shrinkage=None, priors=None,
                 n_components=None, store_covariance=False, tol=0.0001):
        classi_params = {"solver": solver, "shrinkage": shrinkage, "priors": priors, "n_components": n_components,
                         "store_covariance": store_covariance, "tol": tol}
        SupervisedBase.__init__(self, clf=LDA(**classi_params), treshold=treshold)


class GaussianNBDec(SupervisedBase):
    """
    Sklearn implementation of Gaussian Naive Bayes

    http://scikit-learn.org/stable/modules/naive_bayes.html#gaussian-naive-bayes
    """

    def __init__(self, treshold=0.5, priors=None):
        SupervisedBase.__init__(self, clf=GaussianNB(priors), treshold=treshold)



class QDADec(SupervisedBase):
    """
    Sklearn implementation of Quadratic Discriminant Analysis

    http://scikit-learn.org/stable/modules/lda_qda.html
    """

    def __init__(self, treshold=0.5, priors=None, reg_param=0.0, store_covariances=False, tol=0.0001):

        classi_params = {"priors": priors, "reg_param": reg_param,
                         "store_covariances": store_covariances, "tol": tol}
        SupervisedBase.__init__(self, clf=QDA(**classi_params), treshold=treshold)


class SVCDec(SupervisedBase):
    """
    Sklearn implementation of Support Vector Machines

    http://scikit-learn.org/stable/modules/svm.html
    """

    def __init__(self, treshold=0.5, C=1.0, kernel="rbf", degree=3, gamma="auto", coef0=0.0, shrinking=True,
                 tol=0.001, cache_size=200, class_weight=None, verbose=False,
                 max_iter=-1, decision_function_shape=None, random_state=None):
        """
        Parameters
        -----------
        treshold: float
            Border probability value (objects with probability higher then this
            value is considered as searched object)
        """
        classi_params = {"C": C, "kernel": kernel, "degree": degree, "gamma": gamma, "coef0": coef0,
                         "shrinking": shrinking, "probability": True, "tol": tol, "cache_size": cache_size,
                         "class_weight": class_weight, "verbose": verbose, "max_iter": max_iter,
                         "decision_function_shape": decision_function_shape, "random_state": random_state}

        self.treshold = treshold
        self.learner = svm.SVC(**classi_params)


class TreeDec(SupervisedBase):
    """
    Sklearn implementation of Decision Trees

    http://scikit-learn.org/stable/modules/tree.html
    """

    def __init__(self, treshold=0.5, criterion="gini", splitter="best", max_depth=None, min_samples_split=2,
                 min_samples_leaf=1, min_weight_fraction_leaf=0.0, max_features=None, random_state=None,
                 max_leaf_nodes=None, min_impurity_split=1e-07, class_weight=None, presort=False):
        """
        Parameters
        -----------
            treshold: float
                Border probability value (objects with probability higher then this
                value is considered as searched object)
        """
        classi_params = {"criterion": criterion, "splitter": splitter, "max_depth": max_depth,
                         "min_samples_split": min_samples_split, "min_samples_leaf": min_samples_leaf,
                         "min_weight_fraction_leaf": min_weight_fraction_leaf, "max_features": max_features,
                         "random_state": random_state, "max_leaf_nodes": max_leaf_nodes,
                         "min_impurity_split": min_impurity_split, "class_weight": class_weight, "presort": presort}
        self.treshold = treshold
        self.learner = tree.DecisionTreeClassifier(**classi_params)

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
    
    
class GradBoostDec(SupervisedBase):
    """
    Sklearn implementation of GradientBoosting

    http://scikit-learn.org/stable/modules/generated/sklearn.ensemble.GradientBoostingClassifier.html
    """

    def __init__(self, treshold=0.5, loss="deviance", learning_rate=0.1, n_estimators=100, subsample=1.0,
                 criterion="friedman_mse", min_samples_split=2, min_samples_leaf=1, min_weight_fraction_leaf=0.0,
                 max_depth=3, min_impurity_split=1e-07, init=None, random_state=None, max_features=None,
                 max_leaf_nodes=None, presort="auto"):
        """
        Parameters
        -----------
            treshold: float
                Border probability value (objects with probability higher then this
                value is considered as searched object)
        """
        classi_params = {"loss": loss, "learning_rate": learning_rate, "n_estimators": n_estimators,
                         "subsample": subsample, "criterion": criterion, "min_samples_split": min_samples_split,
                         "min_samples_leaf": min_samples_leaf, "min_weight_fraction_leaf": min_weight_fraction_leaf,
                         "max_depth": max_depth, "min_impurity_split": min_impurity_split, "init": init,
                         "random_state": random_state, "max_features": max_features,"max_leaf_nodes": max_leaf_nodes,
                         "presort": presort}
        SupervisedBase.__init__(self, clf=GradientBoostingClassifier(**classi_params), treshold=treshold)
        
        
        
        
class RandomForestDec(SupervisedBase):
    """
    Sklearn implementation of RandomForestClassifier

    http://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestClassifier.html
    """

    def __init__(self, treshold=0.5, n_estimators=10, criterion="gini", max_depth=None, min_samples_split=2,
                 min_samples_leaf=1, min_weight_fraction_leaf=0.0, max_features="auto", max_leaf_nodes=None,
                 min_impurity_split=1e-07, bootstrap=True, oob_score=False, n_jobs=1, random_state=None,
                 class_weight=None):
        """
        Parameters
        -----------
            treshold: float
                Border probability value (objects with probability higher then this
                value is considered as searched object)
        """
        classi_params = {"n_estimators": n_estimators, "criterion": criterion, "max_depth": max_depth,
                        "min_samples_split": min_samples_split, "min_samples_leaf": min_samples_leaf,
                        "min_weight_fraction_leaf": min_weight_fraction_leaf, "max_features": max_features,
                        "max_leaf_nodes": max_leaf_nodes, "min_impurity_split": min_impurity_split,
                         "bootstrap": bootstrap, "oob_score": oob_score, "n_jobs": n_jobs,
                         "random_state": random_state, "class_weight": class_weight}
        SupervisedBase.__init__(self, clf=RandomForestClassifier(**classi_params), treshold=treshold)
        
        
        
        
        
        
class AdaBoostDec(SupervisedBase):
    """
    Sklearn implementation of RandomForestClassifier

    http://scikit-learn.org/stable/modules/generated/sklearn.ensemble.AdaBoostClassifier.html
    """

    def __init__(self, treshold=0.5, base_estimator=None, n_estimators=50, learning_rate=1.0,
                 algorithm="SAMME.R",random_state=None):
        """
        Parameters
        -----------
            treshold: float
                Border probability value (objects with probability higher then this
                value is considered as searched object)
        """
        classi_params = {"base_estimator": base_estimator, "n_estimators": n_estimators,
                         "learning_rate": learning_rate,"algorithm": algorithm, "random_state": random_state}
        SupervisedBase.__init__(self, clf=AdaBoostClassifier(**classi_params), treshold=treshold)
        



class ExtraTreesDec(SupervisedBase):
    """
    Sklearn implementation of RandomForestClassifier

    http://scikit-learn.org/stable/modules/generated/sklearn.ensemble.ExtraTreesClassifier.html
    """

    def __init__(self, treshold=0.5, n_estimators=10, criterion="gini", max_depth=None, min_samples_split=2,
                 min_samples_leaf=1, min_weight_fraction_leaf=0.0, max_features="auto", max_leaf_nodes=None,
                 min_impurity_split=1e-07, bootstrap=False, oob_score=False, n_jobs=1, random_state=None,
                 class_weight=None):
        """
        Parameters
        -----------
            treshold: float
                Border probability value (objects with probability higher then this
                value is considered as searched object)
        """
        classi_params = {"n_estimators": n_estimators, "criterion": criterion, "max_depth": max_depth,
                         "min_samples_split": min_samples_split, "min_samples_leaf": min_samples_leaf,
                         "min_weight_fraction_leaf": min_weight_fraction_leaf, "max_features": max_features,
                         "max_leaf_nodes": max_leaf_nodes, "min_impurity_split": min_impurity_split,
                         "bootstrap": bootstrap, "oob_score": oob_score, "n_jobs": n_jobs,
                         "random_state": random_state, "class_weight": class_weight}

        SupervisedBase.__init__(self, clf=ExtraTreesClassifier(**classi_params), treshold=treshold)
        
        
