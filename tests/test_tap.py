'''
Created on Mar 6, 2016

@author: Martin Vo
'''
import unittest
from db_tier.TAP_query import TapClient
from db_tier.macho_client import MachoDb

class TestTap(unittest.TestCase):
    '''
    Testing TAP protocol
    '''

    def test_sql_parse(self):
        print MachoDb([75981007]).getStarsWithCurves()
        
        
        