'''
Created on Sep 28, 2016

@author: Martin Vo
'''

from __future__ import division
import abc
import warnings
import numpy as np
from matplotlib import pyplot as plt
from utils.helpers import checkDepth



class BaseDesider(object):
    """
    A desider class works with "coordinates" (specification) of objects. It can
    learn identify inspected group of objects according to "coordinates" of 
    searched objects and other objects.
    
    All desider classes have to inherit this abstract class. That means that they
    need to implement several methods: "learn" and "evaluate". Also all of them
    have to have "treshold" attribute. To be explained read comments below.
    
    Attributes:
    -----------
        treshold : float
            Probability (1.0  means 100 %) level. All objects with probability of
            membership to the group higher then the treshold are considered
            as members.
    """
    
    __metaclass__ = abc.ABCMeta
    
    def __init__(self, treshold = 0.5):
        """
        Parameters:
        -----------
            treshold : float
                Probability (1.0  means 100 %) level. All objects with probability of
                membership to the group higher then the treshold are considered
                as members.
        """
        
        self.treshold = treshold
    
    def learn( self, right_coords, wrong_coords ):
        """
        After executing this method the decider object is capable to recognize
        objects according their "coordinates" via "filter" method.  
        
        Parameters:
        -----------
            right_coords : list
                "Coordinates" of searched objects
                
            wrong_coords : list
                "Coordinates" of other objects 
        """
        raise NotImplementedError
        
    def evaluate( self, star_coords ):
        """
        Parameters:
        -----------
            star_coords : list
                Coordinates of inspected star got from subfilters
                
        Returns:
        --------
            Probability that inspected star belongs to the searched group of objects
        """
        raise NotImplementedError
    
    def evaluateList(self, stars_coords):
        """
        Parameters:
        -----------
            stasr_coords : list
                Coordinates of inspected stars (e.g. obtained from subfilters)
                
        Returns:
        --------
            Probabilities that inspected stars belongs to the searched group of objects
        """        
        return np.array([ self.evaluate( coords ) for coords in stars_coords ])
    
    def getBestCoord(self, stars_coords):
        """
        Parameters:
        -----------
            stars_coords : list
                Coordinates of inspected stars got from subfilters
                
        Returns:
        --------
            Coordinates with highest probability of membership to the searched group
            (one list of coordinates)
        """
        checkDepth(stars_coords, 2)        
        if not len(stars_coords):
            warnings.warn(" There are no stars coordinates to inspect")
            return None
        
        best_coo = None
        best_prob = 0
        for coords in stars_coords:
            prob = self.evaluate( [coords] )[0]
            if prob >= best_prob:
                best_coo = coords
                best_prob = prob
        
        # TODO: 
        assert best_coo != None
                
        return best_coo
        
    def filter( self, stars_coords ):
        """
        Parameters:
        -----------
            stars_coords : list
                Coordinates of inspected stars
                
        Returns:
        --------
            List of True/False whether coordinates belong to the searched group of objects
        """
        checkDepth(stars_coords, 2)
        return [ self.evaluate( [coo]) >= self.treshold for coo in stars_coords ]
    
    
    def getStatistic( self, right_coords, wrong_coords ):
        """
        Parameters:
        -----------
            right_coords : list
                "Coordinates" of searched objects
                
            wrong_coords : list
                "Coordinates" of other objects 
        
        Returns:
        --------
            statistic information : dict
                
                precision : float
                    True positive / (true positive + false positive)
                    
                true_positive_rate : float
                    Proportion of positives that are correctly identified as such
                    
                true_negative_rate : float
                    Proportion of negatives that are correctly identified as such
                    
                false_positive_rate : float
                    Proportion of positives that are incorrectly identified as negatives
                    
                false_negative_rate : float
                    Proportion of negatives that are incorrectly identified as positives
                
        """
        checkDepth(right_coords, 2)
        checkDepth(wrong_coords, 2)
        
        right_num = len( right_coords )
        wrong_num = len( wrong_coords )
        
        true_pos = sum([1  for guess in self.filter( right_coords ) if guess == True])
        false_neg = right_num - true_pos
        
        true_neg = sum([1  for guess in self.filter( wrong_coords ) if guess == False])
        false_pos = wrong_num - true_neg
        
        if true_pos + false_pos > 0:
            precision = true_pos / (true_pos + false_pos)
        else:
            precision = None
        
        print true_pos, true_neg, false_pos, false_neg  
        return {"precision" : precision,
                "true_positive_rate" : true_pos / right_num ,
                "true_negative_rate" : true_neg / wrong_num,
                "false_positive_rate" : false_pos / right_num,
                "false_negative_rate" : false_neg / wrong_num}
        
        """return {"precision" : precision,
                "true_positive_rate" : true_pos / (false_neg + true_pos) ,
                "true_negative_rate" : true_neg / (false_pos + true_neg),
                "false_positive_rate" : false_pos / (false_pos + true_neg),
                "false_negative_rate" : false_neg / (false_neg + true_pos)}"""
        
        
    def plotProbabSpace(self, xlim = None, ylim = None, OFFSET = 0.4):
        plt.clf()
        try:
            if xlim == None or ylim == None:
                x_min, x_max = np.min(self.X[:,0]), np.max(self.X[:,0]) 
                y_min, y_max = np.min(self.X[:,1]), np.max(self.X[:,1])
                
                x_offset = (x_max-x_min) * OFFSET    
                y_offset = (y_max-y_min) * OFFSET  
                          
                xlim = ( x_min - x_offset, x_max + x_offset)
                ylim = ( y_min - y_offset, y_max + y_offset)
            
            searched = self.X[self.y==1]
            others = self.X[self.y==0]    
            plt.plot( searched[:,0], searched[:,1], "ro", label = "Searched objects")
            plt.plot( others[:,0], others[:,1], "bo", label = "Others")            
        except:
            xlim = (0, 50)
            ylim = (0, 50)
            print "Can't plot coordinates of training objects. Decider has to have X and y attribute."
        

        xx, yy = np.meshgrid(np.linspace(xlim[0], xlim[1], 100),
                             np.linspace(ylim[0], ylim[1], 100))
        
        try:
            Z = self.evaluate(np.c_[xx.ravel(), yy.ravel()])
            print "a"
        except ValueError:
            Z = self.evaluateList(np.c_[xx.ravel(), yy.ravel()])
            print "b"
        print "Z", Z         
        Z = Z.reshape(xx.shape)  
        
        plt.pcolor(xx,yy,Z)    
        plt.legend()
        plt.colorbar()  
        plt.xlim(*xlim)
        plt.ylim(*ylim)  
        plt.show()
        
    