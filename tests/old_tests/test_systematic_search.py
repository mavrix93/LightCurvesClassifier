'''
Created on Jul 19, 2016

@author: Martin Vo
'''
import unittest
from stars_processing.systematic_search.stars_searcher import StarsSearcher
from stars_processing.systematic_search.ogle_systematic_search import OgleSystematicSearch
from stars_processing.filters_impl.abbe_value import AbbeValueFilter


class Test(unittest.TestCase):



    def test_og(self):
        abbe_filt = AbbeValueFilter(0.7)
        search = OgleSystematicSearch([abbe_filt], SAVE_PATH = "test_light_curves/", SAVE_LIM = 1)
        #searcher = StarsSearcher([], SAVE_PATH = "test_light_curves/", SAVE_LIM = 1, OBTH_METHOD="ogle")
        
        queries = []
        for i in range(1001,1003):
            queries.append({"starid":i, "field_num":1,"target":"bul"})
            
        search.queryStars(queries)

