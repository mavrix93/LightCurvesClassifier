'''
Created on Feb 18, 2016

@author: Martin Vo
'''

from entities.abstract_coordinate import AbstractCoordinate


class Declination(AbstractCoordinate):
    '''
    Declination class is child of coordinates abstract class and it differ
    from parent classes just by its attributes.  
    '''


    def __init__(self, dec,dec_format="degrees"):
        '''
        @param dec:    Declination value in degrees or as tuple (d,m,s)
        @param dec_format: Unit of the coordinate value (e.g. "degrees", "radians"...)
        '''
        
        AbstractCoordinate.__init__(self,degrees=dec,coo_format=dec_format,MIN_VALUE=-90,MAX_VALUE=90,HOUR_TO_DEGREE_VALUE=1)
