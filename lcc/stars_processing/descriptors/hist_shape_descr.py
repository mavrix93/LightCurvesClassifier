from lcc.stars_processing.utilities.base_descriptor import BaseDescriptor
from lcc.stars_processing.utilities.compare import ComparativeBase
from lcc.stars_processing.utilities.symbolic_representation import SymbolicRepresentation


class HistShapeDescr(SymbolicRepresentation, ComparativeBase, BaseDescriptor):
    """
    This descriptor compares histograms of light curves of inspected star
    with the template

    Attributes
    -----------
    comp_stars : list
        Template stars

    bins : int
        Length of result histogram

    alphabet_size : int
        Range of of used letters

    slide : bool
        If True, words with different lengths are dynamically compared
        by sliding shorter word thru longer

    slide : bool
        If True, words with different lengths are dynamically compared
        by sliding shorter word thru longer

    meth : str
        Method key for calculating distance from comparative objects

        average     : take mean distance in each coordinate as
                      object coordinate
        closest     : take coordinate with closest distance as
                      object coordinate
        best'n'   : take best n scores of match, it can be integer or percentage float (0-1).
                    for example best10 takes 10 best matches, best0.5 takes 50 % best matches of the total
    """

    LABEL = "Dissimilarity of the light curves histogram from the template"

    def __init__(self, comp_stars, bins, alphabet_size, slide=False, meth="average"):
        """
        Parameters
        -----------
        comp_stars : list
            Template stars

        hist_bins : int
            Length of result histogram

        hist_alphabet_size : int
            Range of of used letters

        slide : bool
            If True, words with different lengths are dynamically compared
            by sliding shorter word thru longer

        meth : str
            Method key for calculating distance from comparative objects

            average     : take mean distance in each coordinate as
                          object coordinate
            closest     : take coordinate with closest distance as
                          object coordinate
            best'n'   : take best n scores of match, it can be integer or percentage float (0-1).
                        for example best10 takes 10 best matches, best0.5 takes 50 % best matches of the total
        """
        self.comp_stars = comp_stars
        self.bins = bins
        self.alphabet_size = alphabet_size
        self.slide = slide
        self.meth = meth

    def getWord(self, star):
        """
        Parameters
        -----------
        Star object with light curve

        Returns
        -------
        str
            String representation of light curve's histogram
        """
        return self._getWord(star.lightCurve.getHistogram(bins=self.bins)[0], self.bins, self.alphabet_size)
