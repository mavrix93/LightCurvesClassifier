'''
Created on Feb 22, 2016

@author: Martin Vo
'''


from stars_processing.filters_impl.symbolic_representation import SAX
import unittest

class TestSax(unittest.TestCase):
    '''Testing of symbolic representation'''
    
    def setUp(self):
        # All tests will be run with 6 letter words
        # and 5 letter alphabet
        self.sax = SAX(6, 5, 1e-6)
    def test_to_letter_rep(self):
        arr = [7,1,4,4,4,4]
        letters = self.sax.to_letter_rep(arr)[0]
        assert letters == 'eacccc'

    def test_long_to_letter_rep(self):
        long_arr = [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,6,6,6,6,10,100]
        letters= self.sax.to_letter_rep(long_arr)[0]
        assert letters == 'bbbbce'

    def test_compare_strings(self):
        base_string = 'aaabbc'
        similar_string = 'aabbbc'
        dissimilar_string = 'ccddbc'
        similar_score = self.sax.compare_strings(base_string, similar_string)
        dissimilar_score = self.sax.compare_strings(base_string, dissimilar_string)
        assert similar_score < dissimilar_score
