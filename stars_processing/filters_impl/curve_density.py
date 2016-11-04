'''
Created on May 12, 2016

@author: Martin Vo
'''
from utils.data_analysis import to_ekvi_PAA
from utils.commons import returns,accepts
from entities.star import Star
from utils.helpers import progressbar
from stars_processing.filters_tools.base_filter import BaseFilter

class CurveDensityFilter(BaseFilter):
    '''
    This filter throw out stars with low density light curves. It means light
    curves with huge non observing gaps or light curves with low amount of observations 
    '''


    def __init__(self, dens_limit = 0.23, *args, **kwargs):
        '''
        @param dens_limit: Minimal value of light curve density
        '''
        
        self.dens_limit = dens_limit
    
    @returns(list)
    @accepts(list)    
    def applyFilter(self,stars):
        '''
        Filter stars according to light curve densities 
        
        @param stars: List of star objects (containing light curves)        
        @return: List of star-like objects passed thru filtering
        '''
        res_stars = []
        for st in stars:   
            if self._filterStar(st):
                res_stars.append(st)
                
        return res_stars
    
    @accepts(Star)
    def _filterStar(self,st):
        x,y = to_ekvi_PAA(st.lightCurve.time, st.lightCurve.mag)
        ren = x.max() - x.min()
        if  float(len(x))/ren > self.dens_limit:
            return True
        return False