'''
Created on Feb 28, 2016

@author: Martin Vo
'''

import abc

class StarsCatalogue(object):
    __metaclass__ = abc.ABCMeta
    '''Common class for all catalogues containing informations about stars'''
    
    def getStars(self):
        raise NotImplementedError

class LightCurvesDb(StarsCatalogue):
    __metaclass__ = abc.ABCMeta
    '''This is common class for every database containing light curves'''
    
    def getStarsWithCurves(self):
        raise NotImplementedError
    

    
        
        
        







        
        
        
