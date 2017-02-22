import abc

from lcc.stars_processing.utilities.sax import SAX
import numpy as np


class SymbolicRepresentation(object):
    '''
    This common class for all descriptors based on symbolic representation
    of data.
    '''
    __metaclass__ = abc.ABCMeta

    def compareTwoStars(self, star, comp_star):
        """
        Compare two stars according to a filter implementation

        Parameters
        ----------
        star : `Star` instance
            Star to compare

        comp_star : `Star` instance
            Star to compare

        Returns
        -------
        float
            Dissimilarity of two stars
        """
        curve_len = np.max(
            [len(star.lightCurve.mag), len(comp_star.lightCurve.mag)])

        if not self.slide or not hasattr(self, "getWords"):
            inspected_word = self.getWord(star)
            comp_word = self.getWord(comp_star)
            score = self._getDissmilarity(inspected_word, comp_word, curve_len)
            return score

        else:
            one_word, words = self.getWords(comp_star, star)
            return self._getDissmilaritySlide(one_word, words)

    def _getWord(self, x, word_size, alphabet_size):
        self.sax = SAX(word_size, alphabet_size)
        return self.sax.to_letter_rep(x)[0]

    def _getDissmilaritySlide(self, sliding_word, words):
        '''
        This method go through string curve of a star and trying to match filter
        sentence pattern.
        '''
        best_score = 1e9
        for word in words:
            score = self.sax.compare_strings(word, sliding_word)
            if score < best_score:
                best_score = score
        return best_score

    def _getDissmilarity(self, inspected_word, filter_word, curve_len):
        '''
        This method go through string curve of a star and trying to match filter
        sentence pattern.
        '''
        if not inspected_word or not filter_word:
            raise Exception("There are no words for comparing")

        shift = 0
        # Case of shorter filter word then star word
        if (len(filter_word) < len(inspected_word)):
            word_a = filter_word
            word_b = inspected_word
        else:
            word_b = filter_word
            word_a = inspected_word

        a_word_size = len(word_a)
        b_word_size = len(word_b)
        # Shift shorter word thru longer word and look for match
        best_score = 99
        while (a_word_size + shift <= b_word_size):
            word = word_b[shift:shift + a_word_size]
            score = self.sax.compare_strings(word, word_a)

            if (score < best_score):
                best_score = score
            shift += 1

            if not self.slide:
                break

        return best_score
