'''
Created on Mar 18, 2016

@author: Martin Vo

IDEA OF ORGANIZATION OF FILTERING:

- this class perform all filtering
- every filter class is inherited from parent "BaseFilter" class
    -> every filter will contain method for filtering stars (with same name), so
     it is possible to perform applying filters at once in this class
'''

#Throws:
from entities.exceptions import NotFilterTypeClass

from utils.helpers import verbose

from conf.settings import *
from entities.star import Star


class FilteringManager(object):
    '''
    This class is responsible for filtering stars according to given filters
    (their own implementation of filtering)
    Class is initialized with inspected stars as argument. Additionally stars
    can be added thru add method. Each filter has its own implementation 
    of preparing 
    '''


    def __init__(self, stars=[]):
        '''
        @param stars: Stars which will be filtered
        '''
        
        self.stars = stars
        self.filters = []
        
        
    def loadFilter(self,stars_filter):
        '''
        This method load reference stars which will be used as template for filtering
        
        @param stars_filter: This is stars filter object responsible for filtering
                             stars according to its own criterion 
        '''        

        self._check_filter_validity(stars_filter)        
        self.filters.append(stars_filter)

       
    def performFiltering(self):
        '''
        Apply all filters to stars and return stars which passed thru all filters
                
        @return: Stars which passed thru filtering
        '''

        stars = self.stars  
        for st_filter in self.filters:
            stars=st_filter.applyFilter(stars)
        verbose("Filtering is done\nNumber of stars passed filtering: %i / %i"%(len(stars), len(self.stars)),3,VERBOSITY)
        return stars
         
    
    def addStars(self,stars):
        '''Add list of stars or one star to the list of stars for filtering'''
         
        ty_stars = type(stars)
        if (ty_stars == list):
            self.stars += stars
        elif (ty_stars == Star):
            self.stars.append(stars)
            
    def _check_filter_validity(self,stars_filter):
        '''Check whether filter class inherit BaseFilter'''
        
        if not isinstance(stars_filter, BaseFilter):
            raise NotFilterTypeClass(stars_filter.__class__.__name__)
    


