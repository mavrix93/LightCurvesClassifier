'''
Created on Mar 20, 2016

@author: Martin Vo
'''

from utils.commons import returns,accepts
from stars_processing.filters_tools.base_filter import BaseFilter
from entities.star import Star
from utils.helpers import progressbar

class AbbeValueFilter(BaseFilter):
    '''
    Filter implementation which sorts stars according to their Abbe value
    '''


    def __init__(self, abbe_lim, *args, **kwargs):
        '''
        @param abbe_lim: Maximum abbe value for passing thru filter
        '''
        self.abbe_lim = abbe_lim
    
    @accepts(list)
    @returns(list)
    def applyFilter(self,stars):
        '''
        Filter stars according to Abbe values
        
        @param stars: List of star objects (containing light curves)
        
        @return: List of star-like objects passed thru filtering
        '''
        passed_stars = []
        for star in stars:
            res = self._filterStar(star)
            if res[0]: passed_stars.append(res[0])
        return passed_stars
    
    @accepts(Star)    
    def _filterStar(self,star):
        abbe_value = star.getAbbe()
        if (abbe_value < self.abbe_lim):
            return star,abbe_value
        return False, False
 