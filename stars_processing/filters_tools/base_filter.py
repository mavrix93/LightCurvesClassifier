'''
Created on May 18, 2016

@author: Martin Vo
'''

import abc
from utils.commons import returns, accepts
import warnings
from utils.helpers import clean_path, verbose
import os

import sys

class BaseFilter(object):
    __metaclass__ = abc.ABCMeta
    '''
    Base class for all filters. It is something like interface (check whether
    subclasses have certain methods
    '''
    
    @accepts(list)
    @returns(list)
    def applyFilter(self,stars):
        raise NotImplementedError

    #TODO: Check whether these lists contains object of Star class type
    
class ComparativeSubFilter(object):
    pass


class Learnable( object ):    
    """
    Common class for all filters which are able to call "learn" by yourself.
    All these classes need to be able obtain their space coordinates via
    getSpaceCoords. Then the learning is the same (see learn method below).
    
    Optionally there can be labels on plots if a class has label attribute,
    which is list of string contains label for data.
    
    Also after learning the 'learned' attribute is set to 'True' if exists.
    
    Moreover plot is saved if class has  plot_save_path attribute is not None or ""
    """
    
    def getSpaceCoords(self, stars):
        """        
        Parameters:
        -----------
            stars : list of Star objects
            
        Returns:
        --------
            List of list of numbers (coordinates)
        """
        raise NotImplementedError("getSpaceCoords need to be implemented in all  Learnable classes")
    
    
    def learn(self, searched_stars, contamination_stars, learn_num = ""):        
        self.decider.learn( self.getSpaceCoords( searched_stars),
                            self.getSpaceCoords( contamination_stars))
        
        title = self.__class__.__name__ + ": "+ self.decider.__class__.__name__+"_%s" % str(learn_num)
        
        try:
            self.labels
        except AttributeError:
            self.labels = ["" for i in self.decider.X ]
            
        try:
            self.plot_save_path
        except AttributeError:
            self.plot_save_path = None    
        
        try:
            img_name = clean_path(self.plot_save_name)+"_%s" % str(learn_num)
            self.decider.plotHist(title, self.labels, file_name = img_name, save_path = self.plot_save_path)
            
            if len(self.labels) == 2:                       
                self.decider.plotProbabSpace( save_path = self.plot_save_path,
                                              file_name = img_name,
                                              x_lab = self.labels[0],
                                              y_lab = self.labels[1],
                                              title = title)
        except Exception as err:
            # TODO: Load from settings file
            #path = settings.TO_THE_DATA_FOLDER
            path = "."
            VERB = 2
            
            err_log = open( os.path.join( path , "plot_err_occured.log"), "w")
            err_log.write( str(err) )
            err_log.close()       
            verbose( "Error during plotting.. Log file has been saved into data folder", 1, VERB) 
            
            
        try:
            self.learned = True
        except AttributeError:
            warnings.warn( "Could not be able to set self.learned = True")
            
        
    def getStatistic(self, s_stars, c_stars):
        
        searched_stars_coords = self.getSpaceCoords( s_stars)            
        contamination_stars_coords = self.getSpaceCoords( c_stars)
        
        return self.decider.getStatistic( searched_stars_coords, contamination_stars_coords )
