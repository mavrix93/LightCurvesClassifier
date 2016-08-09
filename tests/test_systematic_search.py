'''
Created on Jul 19, 2016

@author: Martin Vo
'''
import unittest
from stars_processing.systematic_search.searcher import DefaultDbSearch
from stars_processing.systematic_search.ogleII import OgleSystematicSearch
from stars_processing.filters_impl.abbe_value import AbbeValueFilter


class Test(unittest.TestCase):

    def test_default_db(self):
        searcher = DefaultDbSearch([], SAVE_PATH = "test_light_curves/", SAVE_LIM = 1, OBTH_METHOD="ogle")
        queries = []
        for i in range(1001,1009):
            queries.append({"starid":i, "field_num":1,"target":"bul"})
            
        searcher.queryStars(queries)
        
        

    """def test_(self):
        abbe_filt = AbbeValueFilter(0.7)
        search = OgleSystematicSearch([abbe_filt], SAVE_PATH = "test_light_curves/", SAVE_LIM = 1)
        
        queries = []
        for i in range(1001,1003):
            queries.append({"starid":i, "field_num":1,"target":"bul"})
            
        search.queryStars(queries)"""

