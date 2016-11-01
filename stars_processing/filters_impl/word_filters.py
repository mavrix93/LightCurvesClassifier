'''
Created on Mar 20, 2016

@author: Martin Vo

Classes responsible for filtering stars (comparing template stars
with tested stars) via their words (data transformed into the symbolic representation)
'''

from stars_processing.filters_tools.symbolic_representation import SymbolicRepresentation
from stars_processing.filters_tools.sax import SAX
from utils.data_analysis import compute_bins
from stars_processing.filters_tools.base_filter import ComparativeSubFilter

class CurvesShapeFilter(ComparativeSubFilter, SymbolicRepresentation):
    '''
    This filter implementation sort stars according to their string (symbolic) 
    representation of light curve. Template for filtering is build up as a list 
    of reference stars which light curves will be taken for comparing
    '''
    
    KEY_NAME = "curve_word"
    
    def __init__(self, lc_days_per_bin, lc_alphabet_size, **kwargs):
        '''
        @param days_per_bin: Ratio which decides about length of the word (symbolic representation of light curve)
        @param alphabet_size: Range of of used letters          
        '''
        
        SymbolicRepresentation.__init__(self, filter_attribute = self.KEY_NAME, days_per_bin=days_per_bin,alphabet_size=alphabet_size)
        
        
    def prepareStar(self, star):
        '''
        Parameters:
        -----------
            Star object with light curve

        Returns:
        --------
            Star enchanted by light curve world
        ''' 
        
        word_size = compute_bins(star.lightCurve.time,self.days_per_bin)
        sax = SAX(word_size,self.alphabet_size)
        star[self.KEY_NAME] =  sax.to_letter_rep(star.lightCurve.mag)[0]
        return star
    
    
class HistShapeFilter(ComparativeSubFilter, SymbolicRepresentation):
    '''
    This filter implementation sort stars according to their string (symbolic) 
    representation of histogram. Template for filtering is build up as a list 
    of reference stars which histograms will be taken for comparing
    '''
    
    KEY_NAME = "histogram_word"
    
    def __init__(self,hist_days_per_bin,hist_alphabet_size, **kwargs):
        '''
        @param wordSize: Length of symbol representation of histogram
        @param alphabet_size: Range of of used letters     
        '''
        SymbolicRepresentation.__init__(self, filter_attribute= self.KEY_NAME, days_per_bin = hist_days_per_bin,alphabet_size= hist_alphabet_size)
        
        
    def prepareStar(self,star):
        '''
        Returns:
        --------
            Star enchanted by histogram world
        ''' 
   
        hist = star.getHistogram(days_per_bin=self.days_per_bin)[0]
        sax = SAX(len(hist),self.alphabet_size)
        star.more[ self.KEY_NAME ] = sax.to_letter_rep(hist)[0]
        return star   
    
class VariogramShapeFilter(ComparativeSubFilter, SymbolicRepresentation):
    '''
    This filter implementation sort stars according to their string (symbolic) 
    representation of light curve. Template for filtering is build up as a list 
    of reference stars which light curves will be taken for comparing
    '''
    
    KEY_NAME = "variogram_word"
    
    def __init__(self, vario_days_per_bin, vario_alphabet_size, **kwargs):
        '''
        @param letterPerDayRatio: Ratio which decides about length of word (symbolic representation of light curve)
        @param alphabet_ize: Range of of used letters         
        '''
        
        SymbolicRepresentation.__init__(self, filter_attribute= self.KEY_NAME,days_per_bin= vario_days_per_bin,alphabet_size= vario_alphabet_size)
        
    
    def prepareStar(self,star):
        '''
        Returns:
        --------
            Star enchanted by variogram world
        ''' 
        
        vario = star.getVariogram(days_per_bin=self.days_per_bin)[1]
        sax = SAX(len(vario),self.alphabet_size)
        star.more[self.KEY_NAME] = sax.to_letter_rep(vario)[0]
        return star