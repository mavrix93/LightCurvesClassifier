'''
Created on Mar 20, 2016

@author: Martin Vo

Classes responsible for filtering stars (comparing template stars
with tested stars) via their words (data transformed into the symbolic representation)
'''

from stars_processing.filters_tools.symbolic_representation import SymbolicRepresentation
from stars_processing.filters_tools.sax import SAX
from entities.exceptions import InvalidFilteringParams
from utils.data_analysis import compute_bins

class CurvesShapeFilter(SymbolicRepresentation):
    '''
    This filter implementation sort stars according to their string (symbolic) 
    representation of light curve. Template for filtering is build up as a list 
    of reference stars which light curves will be taken for comparing
    '''
    def __init__(self,days_per_bin,alphabet_size):
        '''
        @param days_per_bin: Ratio which decides about length of the word (symbolic representation of light curve)
        @param alphabet_size: Range of of used letters          
        '''
        
        SymbolicRepresentation.__init__(self, filter_attribute="curveWord", days_per_bin=days_per_bin,alphabet_size=alphabet_size)
        
        
    def prepareStar(self,star):
        '''
        @param Star object with light curve
        @return Star appended by word (light curve)
        ''' 
          
        if (star.curveWord == "" or star.curveWord == None):
            word_size = compute_bins(star.lightCurve.time,self.days_per_bin)
            sax = SAX(word_size,self.alphabetSize)
            lettersCurve = sax.to_letter_rep(star.lightCurve.mag)[0]
            star.putLettersCurve(lettersCurve)
        return star
    
    
    
class HistShapeFilter(SymbolicRepresentation):
    '''
    This filter implementation sort stars according to their string (symbolic) 
    representation of histogram. Template for filtering is build up as a list 
    of reference stars which histograms will be taken for comparing
    '''
    def __init__(self,days_per_bin,alphabet_size):
        '''
        @param wordSize: Length of symbol representation of histogram
        @param alphabetSize: Range of of used letters     
        '''
        SymbolicRepresentation.__init__(self, filter_attribute="histWord",days_per_bin=days_per_bin,alphabet_size=alphabet_size)
        
        
    def prepareStar(self,star):
        '''
        Prepare stars for filtering (get required attributes)
        
        @param Star object with light curve
        @return Star appended by word (histogram)
        ''' 
   
        if (star.histWord == "" or star.histWord == None):
            hist = star.getHistogram(days_per_bin=self.days_per_bin)[0]
            sax = SAX(len(hist),self.alphabetSize)
            lettersHist = sax.to_letter_rep(hist)[0]
            star.putLettersHist(lettersHist)
        return star
    
    
    
class VariogramShapeFilter(SymbolicRepresentation):
    '''
    This filter implementation sort stars according to their string (symbolic) 
    representation of light curve. Template for filtering is build up as a list 
    of reference stars which light curves will be taken for comparing
    '''
    def __init__(self,days_per_bin,alphabet_size):
        '''
        @param letterPerDayRatio: Ratio which decides about length of word (symbolic representation of light curve)
        @param alphabet_ize: Range of of used letters         
        '''
        
        SymbolicRepresentation.__init__(self, filter_attribute="varioWord",days_per_bin=days_per_bin,alphabet_size=alphabet_size)
        
    
    def prepareStar(self,star):
        '''
        @param Star objects with light curve
        @return Star appended by word (variogram)
        ''' 
        
        if (star.varioWord == "" or star.varioWord == None):  
            vario = star.getVariogram(days_per_bin=self.days_per_bin)[1]
            sax = SAX(len(vario),self.alphabetSize)
            lettersVario = sax.to_letter_rep(vario)[0]
            star.putLettersVario(lettersVario)
        return star