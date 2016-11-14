'''
Created on May 18, 2016

@author: Martin Vo
'''
from utils.helpers import progressbar
import numpy as np
from stars_processing.filters_tools.base_filter import BaseFilter, Learnable
from utils.commons import returns,accepts
from entities.star import Star


# TODO: Need to upgraded
class VariogramSlope(BaseFilter, Learnable):
    '''
    This filter sorting stars according slopes of their variograms
    '''


    def __init__(self,  variogram_days_bin, decider, 
                 plot_save_path = None, plot_save_name = "",*args, **kwargs):
        '''
        @param slopes_range: Tuple/list.. of border values for permitted range of slopes 
        '''
        self.decider = decider
        self.variogram_days_bin = variogram_days_bin
        self.plot_save_path = plot_save_path
        self.plot_save_name = plot_save_name
        
    @accepts(list)
    @returns(list)    
    def applyFilter(self,stars):
        '''
        Filter stars according to slopes of their variograms
        
        @param stars: List of star objects (containing light curves)        
        @return: List of star-like objects passed thru filtering
        '''
        
        stars_coords = self.getSpaceCoords( stars )
        
        return [star_coo for star_coo, passed in zip(stars_coords, self.decider.filter(stars_coords)) if passed]
    
   
    def getSpaceCoords(self, stars): 
        """
        Get list of desired colors
        
        Parameters:
        -----------
            stars : list of Star objects
                Stars with color magnitudes in their 'more' attribute
 
        Returns:
        -------
            List of list of floats
        """
        
        coords = []
        for star in stars:
            if star.lightCurve:
                x,y =  star.getVariogram( self.variogram_days_bin )
                coords.append( [np.polyfit(x, y, 1)[0]] )
            else:
                coords.append( [None] )
        return coords
                
        