from stars_processing.utilities.compare import ComparativeBase
from stars_processing.utilities.symbolic_representation import SymbolicRepresentation
from stars_processing.utilities.base_descriptor import BaseDescriptor


class VariogramShape(SymbolicRepresentation, ComparativeBase, BaseDescriptor):
    '''
    This descriptor compares variograms of light curves of inspected star
    with the template in symbolic representation.

    Attributes
    -----------
    comp_stars : list
        Template stars

    days_per_bin : float
        Ratio which decides about length of the word

    alphabet_size : int
        Range of of used letters

    slide : bool
        If True, words with different lengths are dynamically compared
        by sliding shorter word thru longer
    '''

    def __init__(self, comp_stars, bins, alphabet_size, slide=False, **kwargs):
        '''
        Parameters
        -----------
        comp_stars : list
            Template stars

        bins : int
            Number of bins

        alphabet_size : int
            Range of of used letters

        slide : bool
            If True, words with different lengths are dynamically compared
            by sliding shorter word thru longer
        '''
        self.comp_stars = comp_stars
        self.bins = bins
        self.alphabet_size = alphabet_size
        self.slide = slide

    def getWord(self, star):
        '''
        Parameters
        -----------
        Star object with a light curve

        Returns
        --------
        str
            String representation of light curve's variogram
        '''
        return self._getWord(star.lightCurve.getVariogram(bins=self.bins)[1],
                             self.bins, self.alphabet_size)
