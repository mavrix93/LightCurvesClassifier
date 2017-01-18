from stars_processing.utils.compare import ComparativeBase
from stars_processing.utils.symbolic_representation import SymbolicRepresentation
from stars_processing.utils.base_descriptor import BaseDescriptor


class HistShape(SymbolicRepresentation, ComparativeBase, BaseDescriptor):
    '''
    This descriptor compares histograms of light curves of inspected star
    with the template

    Attributes
    -----------
    bins : int
        Length of result histogram

    alphabet_size : int
        Range of of used letters

    slide : bool
        If True, words with different lengths are dynamically compared
        by sliding shorter word thru longer
    '''

    def __init__(self, bins, alphabet_size, slide=False, **kwargs):
        '''
        Parameters
        -----------
        hist_bins : int
            Length of result histogram

        hist_alphabet_size : int
            Range of of used letters

        slide : bool
            If True, words with different lengths are dynamically compared
            by sliding shorter word thru longer
        '''
        self.bins = bins
        self.alphabet_size = alphabet_size
        self.slide = slide

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
        return self._getWord(star.lightCurve.getHistogram(bins=self.bins)[0], self.bins, self.alphabet_size)
