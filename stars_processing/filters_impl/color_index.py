'''
Created on May 8, 2016

@author: Martin Vo
'''
from warnings import warn
from utils.commons import returns,accepts
from stars_processing.filters_tools.base_filter import BaseFilter
from entities.star import Star
from utils.helpers import progressbar
from db_tier.connectors.ogle_client import updateStar

class ColorIndexFilter(BaseFilter):
    '''
    Filter star according their color indexes
    
    TODO: Make color of indexes optional (so far there are just B-V and V-I)
    '''


    def __init__(self, dec_func,pass_not_found=False, *args, **kwargs):
        '''
        @param  dec_func: Decision function which takes two arguments - BV and VI
                index and returns True/False
        @param  pass_not_found: If color index will not be download and this
                option is True, stars will be passing thru this filter
        '''
        self.dec_func = dec_func
        self.pass_not_found = pass_not_found
    
    @accepts(list)
    @returns(list)     
    def applyFilter(self,stars):
        passed_stars = []
        for star in progressbar(stars,"Color index filtering: "):
            res = self._filterStar(star)
            if res: passed_stars.append(star)
        return passed_stars
    
    @accepts(Star)   
    def _filterStar(self,star):        
        if not star.more:
            star = updateStar(star)
        
        try:   
            bvi = star.more 
            vi = bvi["v_i"]
            bv = bvi["b_v"]            
        except KeyError:
            warn("Star does not have color indexes")
            if self.pass_not_found: return True
            return False
        return self.dec_func(bv,vi)
            
        
        