from lcc.stars_processing.utilities.base_descriptor import BaseDescriptor
from lcc.stars_processing.utilities.compare import ComparativeBase
from lcc.stars_processing.utilities.symbolic_representation import SymbolicRepresentation
from lcc.utils.data_analysis import compute_bins
from lcc.entities.exceptions import QueryInputError


class CurvesShapeDescr(SymbolicRepresentation, ComparativeBase, BaseDescriptor):
    '''
    This descriptor which compares light curves of inspected star
    with the template in symbolic representation

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

    meth : str
        Method key for calculating distance from comparative objects

        average     : take mean distance in each coordinate as
                      object coordinate
        closest     : take coordinate with closest distance as
                      object coordinate
    '''

    AVAIL_METHODS = ["average", "closest"]
    LABEL = "Dissimilarity of the curve from the template"

    def __init__(self, comp_stars, days_per_bin, alphabet_size,
                 slide=True, meth="average"):
        '''
        Parameters
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

        meth : str
            Method key for calculating distance from comparative objects

            average     : take mean distance in each coordinate as
                          object coordinate
            closest     : take coordinate with closest distance as
                          object coordinate
        '''
        if not meth in self.AVAIL_METHODS:
            raise QueryInputError(
                "Unrecognized method %s\nAvailable: %s" % (meth, self.AVAIL_METHODS))

        self.comp_stars = comp_stars
        self.days_per_bin = days_per_bin
        self.alphabet_size = alphabet_size
        self.slide = slide
        self.meth = meth

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
