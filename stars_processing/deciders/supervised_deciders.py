'''
Created on Oct 4, 2016

@author: Martin Vo
'''

import numpy as np

from sklearn.lda import LDA
from sklearn.naive_bayes import GaussianNB
from astroML.classification.gmm_bayes import GMMBayes
from sklearn.qda import QDA

from stars_processing.deciders.base_decider import BaseDecider
from utils.helpers import checkDepth
from conf import deciders_settings
from entities.exceptions import QueryInputError, LearningError
from sklearn import svm
from sklearn import tree

class SupervisedBase(BaseDecider):
    """
    Base class for sklearn library supervised classes transformed to the package
    content. It is not intended to use this directly, but thru certain method
    subclasses.  
    
    Attributes:
    -----------
        treshold: float
            Border probability value (objects with probability higher then this
            value is considered as searched object)
            
        learner: sklearn object
            Learner object for desired method of supervised learning
    """
    def __init__(self, clf, treshold = 0.5):
        """
        Parameters:
        -----------
            treshold: float
                Border probability value (objects with probability higher then this
                value is considered as searched object)
                
            learner: sklearn object
                Learner object for desired method of supervised learning
        """
        
        self.treshold = treshold
        self.learner = clf()
    
    def learn( self, right_coords , wrong_coords ):
        """
        Learn to recognize objects
        
        Parameters:
        -----------
            right_coords: iterable
                List of coordinates (list of numbers) of searched objects
                
            wrong_coords: iterable
                List of coordinates (list of numbers) of contamination objects
                
        Returns:
        --------
            None
        """
        
        y = [1 for i in range(len(right_coords))]
        y += [0 for i in range(len(wrong_coords))]
        self.X = np.array(right_coords + wrong_coords)
        self.y = np.array(y)
        
        if not self.X.any() or not self.y.any():
            raise QueryInputError("No stars have attributes which are needed by filter")
        
        try:
            self.learner.fit( self.X, self.y)
        except:
            raise LearningError("Could not learn decider on dataset:\nX = %s\n\nlabels = %s" %(self.X, self.y))
        
    def evaluate( self, coords ): 
        # TODO:
        # if coords != np.ndarray: coords = np.array( coords )
        # checkDepth(coords, 2)
        prediction =  self.learner.predict_proba(coords)
        a = prediction[:,1]
        checkDepth(a, 1)        
        return a
    
class LDADec(SupervisedBase):
    def __init__(self, treshold = None):
        if not treshold:
            treshold = deciders_settings.TRESHOLD
        SupervisedBase.__init__( self, clf = LDA, treshold = treshold)

class GaussianNBDec(SupervisedBase):
    def __init__(self, treshold = None):
        if not treshold:
            treshold = deciders_settings.TRESHOLD
        SupervisedBase.__init__( self, clf = GaussianNB, treshold = treshold)        
        
        
class GMMBayesDec(SupervisedBase):
    def __init__(self, treshold = None):
        if not treshold:
            treshold = deciders_settings.TRESHOLD
        SupervisedBase.__init__( self, clf = GMMBayes, treshold = treshold)
        
class QDADec(SupervisedBase):
    def __init__(self, treshold = None):
        if not treshold:
            treshold = deciders_settings.TRESHOLD
        SupervisedBase.__init__( self, clf = QDA, treshold = treshold)
        
class SVCDec( SupervisedBase ):      
    def __init__(self, treshold = 0.5):
        """
        Parameters:
        -----------
            treshold: float
                Border probability value (objects with probability higher then this
                value is considered as searched object)
        """
        
        self.treshold = treshold
        self.learner = svm.SVC()
        
    def evaluate( self, coords ): 
        return self.learner.predict(coords)


class TreeDec( SupervisedBase ):      
    def __init__(self, treshold = 0.5):
        """
        Parameters:
        -----------
            treshold: float
                Border probability value (objects with probability higher then this
                value is considered as searched object)
        """
        
        self.treshold = treshold
        self.learner = tree.DecisionTreeClassifier()
        
    def evaluate( self, coords ): 
        return self.learner.predict(coords)