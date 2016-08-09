'''
Created on Feb 18, 2016

@author: Martin Vo
'''

from entities.abstract_coordinate import AbstractCoordinate
import numpy as np
#from utils.commons import mandatory_args, default_values, args_type

class RightAscension(AbstractCoordinate):
    '''
    Right Ascension class is child of coordinates abstract class and it differ
    from parent classes by its attributes and one new method.   
    '''

    def __init__(self, ra,ra_format="degrees"):
        '''
        @param ra:    Right Ascension value in degrees or as tuple (h,m,s)
        @param ra_format: Unit of the coordinate value (e.g. "hours", "degrees", "radians")
        '''
        AbstractCoordinate.__init__(self,degrees=ra, coo_format=ra_format, MIN_VALUE=0,MAX_VALUE=360,HOUR_TO_DEGREE_VALUE=15)
      
    def __str__(self):
        if self.degrees: return "%.4f hours"%(self.getHours()) 
        return "" 
        
    def getHours(self):
        if not self.degrees:
            return None
        return self.degrees/float(self.HOUR_TO_DEGREE_VALUE)
    

        
