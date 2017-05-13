from lcc.stars_processing.utilities.base_descriptor import BaseDescriptor
from lcc.stars_processing.utilities.compare import ComparativeBase
from lcc.stars_processing.utilities.symbolic_representation import SymbolicRepresentation
from lcc.utils.data_analysis import compute_bins
from lcc.entities.exceptions import QueryInputError
import numpy as np


class CurvesShapeDescr(SymbolicRepresentation, ComparativeBase, BaseDescriptor):
    """
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
        best'n'   : take best n scores of match, it can be integer or percentage float (0-1).
                    for example best10 takes 10 best matches, best0.5 takes 50 % best matches of the total
    """

    LABEL = "Dissimilarity of the curve from the template"

    def __init__(self, comp_stars, days_per_bin, alphabet_size,
                 slide=0.25, meth="average"):
        """
        Parameters
        -----------
        comp_stars : list
            Template stars

        days_per_bin : float
            Ratio which decides about length of the word

        alphabet_size : int
            Range of of used letters

        slide : NoneType, float
            If a float, words with different lengths are dynamically compared
            by sliding shorter word thru longer and overlayed by this ratio.
            If it is None, no sliding is executed.

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

    def getWords(self, star1, star2):
        '''
        Parameters
        -----------
        star1 : object
            Star object with light curve

        star2 : object
            Star object with light curve

        Returns
        --------
        list
            String representations of light curve
        '''
        MAX_ITER = 500

        word_size1 = compute_bins(star1.lightCurve.time, self.days_per_bin)
        word_size2 = compute_bins(star2.lightCurve.time, self.days_per_bin)
        stars = [star1, star2]
        _words = [word_size1, word_size2]
        min_arg = np.argmin(_words)
        max_arg = np.argmax(_words)

        longer_star = stars[max_arg]
        shorter_star = stars[min_arg]
        longer_word = _words[max_arg]
        shorter_word = _words[min_arg]

        window_size = len(longer_star.lightCurve.time) * \
            shorter_word / float(longer_word)
        overlay_len = self.slide * window_size

        words = []
        from_i = 0
        to_i = 0
        i = 0
        while i < MAX_ITER:

            to_i = int(from_i + window_size)

            if to_i > len(longer_star.lightCurve.mag):
                break

            lc_slice = longer_star.lightCurve.mag[from_i: to_i]
            words.append(
                self._getWord(lc_slice, shorter_word, self.alphabet_size))

            from_i += int(window_size - overlay_len)

            i += 1

        return self._getWord(shorter_star.lightCurve.mag, shorter_word, self.alphabet_size), words
