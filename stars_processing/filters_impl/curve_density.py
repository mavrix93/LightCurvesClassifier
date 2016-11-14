'''
Created on May 12, 2016

@author: Martin Vo
'''
from utils.data_analysis import to_ekvi_PAA
from utils.commons import returns,accepts
from entities.star import Star
from utils.helpers import progressbar
from stars_processing.filters_tools.base_filter import BaseFilter, Learnable

class CurveDensityFilter(BaseFilter, Learnable):
    '''
    This filter throw out stars with low density light curves. It means light
    curves with huge non observing gaps or light curves with low amount of observations 
    '''


    def __init__(self, decider, plot_save_path = None, plot_save_name = "",*args, **kwargs):
        '''
        @param dens_limit: Minimal value of light curve density
        '''
        
        self.decider = decider
        self.plot_save_path = plot_save_path
        self.plot_save_name = plot_save_name
    
    @returns(list)
    @accepts(list)    
    def applyFilter(self,stars):
        '''
        Filter stars according to light curve densities 
        
        @param stars: List of star objects (containing light curves)        
        @return: List of star-like objects passed thru filtering
        '''
        stars_coords = self.getSpaceCoords( stars )  
        
        return [star_coo for star_coo, passed in zip(stars_coords, self.decider.filter(stars_coords)) if passed]
    
    def getSpaceCoords(self, stars):  
        coo = []
        
        for star in stars:
            if star.lightCurve:
                x,y = to_ekvi_PAA(star.lightCurve.time, star.lightCurve.mag)
                ren = x.max() - x.min()
                coo.append( [float(len(x))/ren] )
            else:
                coo.append( [None] )
        return coo
            
