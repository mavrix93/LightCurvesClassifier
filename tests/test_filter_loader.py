'''
Created on Sep 13, 2016

@author: Martin Vo
'''
import unittest
from conf.filter_loader import FilterLoader
from stars_processing.filters_tools.base_filter import BaseFilter


class TestFilterLoader(unittest.TestCase):
    
    def testLoad(self):
        """
        This test method loads two filters from certain file types. First one
        is loaded from 'conf' file type (see ConfigReader class). Second one
        is loaded from 'pickle' object file.
        
        TEST:
            Test will pass successfully if both filters are instances of BaseFilter
        """
        
        DATA_PATH = "./test_data"
        
        file_name1 = "abbe_filt.conf"
        file_name2 = "filter.pickle"
        
        loader1 = FilterLoader( file_name1 )
        loader2 = FilterLoader( file_name2, pickle_object = True)
        
        loader1.FILTER_PATH = DATA_PATH
        loader2.FILTER_PATH = DATA_PATH
        
        filter1 = loader1.getFilter()
        filter2 = loader2.getFilter()
        
        assert isinstance( filter1, BaseFilter )
        assert isinstance( filter2, BaseFilter ) 

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()