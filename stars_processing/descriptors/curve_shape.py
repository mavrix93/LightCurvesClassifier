from stars_processing.descriptors.compare import ComparativeBase
from stars_processing.filters_tools.symbolic_representation import SymbolicRepresentation
from utils.data_analysis import compute_bins


class CurvesShape(ComparativeBase, SymbolicRepresentation):
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

    def __init__(self, days_per_bin, alphabet_size, **kwargs):
        '''
        Parameters
        -----------
        days_per_bin : float
            Ratio which decides about length of the word

        alphabet_size : int
            Range of of used letters
        '''
        self.days_per_bin = days_per_bin
        self.alphabet_size = alphabet_size
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
        word_size = compute_bins(star.lightCurve.time, self.days_per_bin)
        return self._getWord(star.lightCurve.mag, word_size, self.alphabet_size)
