'''
Classes responsible for filtering stars (comparing template stars
with tested stars) via their words (data transformed into
symbolic representation)
'''

from stars_processing.filters_tools.base_filter import ComparativeSubFilter
from stars_processing.filters_tools.sax import SAX
from stars_processing.filters_tools.symbolic_representation import SymbolicRepresentation
from utils.data_analysis import compute_bins


class CurvesShapeFilter(ComparativeSubFilter, SymbolicRepresentation):
    '''
    This filter implementation sort stars according to their string (symbolic)
    representation of light curve. Template for filtering is build up as a list
    of reference stars which light curves will be taken for comparing

    Attributes
    -----------
    lc_days_per_bin : float
        Ratio which decides about length of the word

    lc_alphabet_size : int
        Range of of used letters

    slide : bool
        If True, words with different lengths are dynamically compared
        by sliding shorter word thru longer
    '''

    def __init__(self, lc_days_per_bin, lc_alphabet_size, **kwargs):
        '''
        Parameters
        -----------
        lc_days_per_bin : float
            Ratio which decides about length of the word

        lc_alphabet_size : int
            Range of of used letters
        '''
        self.lc_days_per_bin = lc_days_per_bin
        self.lc_alphabet_size = lc_alphabet_size
        self.slide = True

    def getWord(self, star):
        '''
        Parameters
        -----------
        Star object with light curve

        Returns
        --------
        String representation of light curve
        '''
        word_size = compute_bins(star.lightCurve.time, self.lc_days_per_bin)
        self.sax = SAX(word_size, self.lc_alphabet_size)
        return self.sax.to_letter_rep(star.lightCurve.mag)[0]


class HistShapeFilter(ComparativeSubFilter, SymbolicRepresentation):
    '''
    This filter implementation sort stars according to their string (symbolic)
    representation of histogram. Template for filtering is build up as a list
    of reference stars which histograms will be taken for comparing

    Attributes
    -----------
    hist_bins : int
        Length of result histogram

    hist_alphabet_size : int
        Range of of used letters

    slide : bool
        If True, words with different lengths are dynamically compared
        by sliding shorter word thru longer
    '''

    def __init__(self, hist_bins, hist_alphabet_size, **kwargs):
        '''
        Parameters
        -----------
        hist_bins : int
            Length of result histogram

        hist_alphabet_size : int
            Range of of used letters
        '''
        self.hist_bins = hist_bins
        self.hist_alphabet_size = hist_alphabet_size
        self.slide = False

    def getWord(self, star):
        '''
        Parameters
        -----------
        Star object with light curve

        Returns
        -------
        str
            String representation of light curve's histogram
        '''
        hist = star.lightCurve.getHistogram(bins=self.hist_bins)[0]
        self.sax = SAX(len(hist), self.hist_alphabet_size)
        return self.sax.to_letter_rep(hist)[0]


class VariogramShapeFilter(ComparativeSubFilter, SymbolicRepresentation):
    '''
    This filter implementation sort stars according to their string (symbolic)
    representation of light curve. Template for filtering is build up as a list
    of reference stars which light curves will be taken for comparing

    Attributes
    -----------
    vario_days_per_bin : float
        Ratio which decides about length of the word

    vario_alphabet_size : int
        Range of of used letters

    slide : bool
        If True, words with different lengths are dynamically compared
        by sliding shorter word thru longer
    '''

    def __init__(self, vario_days_per_bin, vario_alphabet_size, **kwargs):
        '''
        Parameters
        -----------
        vario_days_per_bin : float
            Ratio which decides about length of the word

        vario_alphabet_size : int
            Range of of used letters
        '''
        self.vario_days_per_bin = vario_days_per_bin
        self.vario_alphabet_size = vario_alphabet_size
        self.slide = False

    def getWord(self, star):
        '''
        Parameters
        -----------
        Star object with light curve

        Returns
        --------
        str
            String representation of light curve's variogram
        '''

        bins = compute_bins(star.lightCurve.time, self.vario_days_per_bin)
        vario = star.lightCurve.getVariogram(bins=bins)[1]

        self.sax = SAX(len(vario), self.vario_alphabet_size)
        return self.sax.to_letter_rep(vario)[0]
