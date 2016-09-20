'''
Created on May 18, 2016

@author: Martin Vo
'''
from utils.helpers import progressbar
import numpy as np
from stars_processing.filters_tools.base_filter import BaseFilter
from utils.commons import returns,accepts
from entities.star import Star

class VariogramSlope(BaseFilter):
    '''
    This filter sorting stars according slopes of their variograms
    '''


    def __init__(self, slopes_range, variogram_days_bin):
        '''
        @param slopes_range: Tuple/list.. of border values for permitted range of slopes 
        '''
        self.slopes_range = slopes_range
        self.variogram_days_bin = variogram_days_bin
        
    @accepts(list)
    @returns(list)    
    def applyFilter(self,stars):
        '''
        Filter stars according to slopes of their variograms
        
        @param stars: List of star objects (containing light curves)        
        @return: List of star-like objects passed thru filtering
        '''
        
        result_stars = []
        for star in progressbar(stars,"Filtering by variogram slopes: "):
            if self._filterStar(star):
                result_stars.append(star)
                
        return result_stars
    
    @accepts(Star)
    def _filterStar(self,star):
        x,y =  star.getVariogram(self.variogram_days_bin)
        vario_slope = np.polyfit(x, y, 1)[0]
        
        if vario_slope > self.slopes_range[0] and vario_slope < self.slopes_range[1]:
            return True
        return False
                
        