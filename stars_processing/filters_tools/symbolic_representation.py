'''
Created on Mar 19, 2016

@author: Martin Vo
'''

import abc
from stars_processing.filters_tools.sax import SAX
import warnings
import numpy as np


class SymbolicRepresentation(object):
    __metaclass__ = abc.ABCMeta
    '''
    This common class for all filters based on symbolic representation of data.
    Filtering is based on comparing two star objects (their certain attributes)
    '''
    
    def __init__(self,filter_attribute,days_per_bin=100,alphabet_size=10):
        '''
        @param letterPerDayRatio: This ration is deciding about length of the star word
        @param alphabet_size: Size of alphabet
        @param treshold: Criterion for deciding whether if matching filter and star
                         is sufficient to consider the star as certain phenomena
                         (such as: qso, gravitational lensing etc.)
                         
        '''
        
        self.filter_attribute = filter_attribute
        self.alphabet_size = alphabet_size
        self.days_per_bin = days_per_bin
        
       
                
    def compareStars(self,star,comp_stars):
        '''
        This method return best similarity of the star and list of stars
        by given attribute (curve,histogram, variogram etc)
        '''
        
        best_score = 99        
        best_match = (None,None)
        for comp_star in comp_stars:
            score = self.compareTwoStars(star, comp_star)
            
            if score < best_score:
                best_score = score
                best_match = (star,comp_star)
                
        return best_match[0],best_match[1],best_score   
    
    def compareTwoStars(self,star,comp_star):
        if (star != comp_star):
            curve_len = np.max([len(star.lightCurve.mag),len(comp_star.lightCurve.mag)])
            score = self._seekInStarAttribute( star.more.get(self.filter_attribute), comp_star.more.get(self.filter_attribute),curve_len)
            return score
        warnings.warn("Comparing the same stars")
        return 0
    
    def _seekInStarAttribute(self,starWord,filterWord,curve_len):
        '''
        This method is going through string curve of a star and trying to math filter sentence pattern  
        In the case of the same length of star word and filter word, there would be 
        no need to do sliding window.
        '''
        if not(len(starWord) or len(filterWord)):
            raise Exception("There are no words for comparing")
        
        #TODO check whether word is not empty 
        shift = 0
        #Case of shorter filter word then star word
        if (len(filterWord)  <len(starWord) ):
            aWord = filterWord
            bWord = starWord
        else:
            bWord = filterWord
            aWord = starWord
        
        aWordSize = len(aWord)
        bWordSize = len(bWord)
        #Shift shorter word thru longer word and look for match
        best_score = 99
        while (aWordSize +shift <= bWordSize ):            
            word = bWord[shift:shift+aWordSize]
            sax = SAX(aWordSize,self.alphabet_size)
            sax.scalingFactor = np.sqrt(curve_len/len(word))
            score= sax.compare_strings(word, aWord)
            if (score < best_score):
                    best_score = score
            shift +=1
        return best_score
    

   

        
        
   
        
        







    
    



        