'''
Created on Jul 20, 2016

@author: martin
'''
import unittest
from stars_processing.systematic_search.status_resolver import StatusResolver


class Test(unittest.TestCase):


    def test_resolve_passed(self):
        pa = "test_light_curves/ogle_db.txt"
        pa2 = "test_light_curves/ogle_db_plan.txt"
        
        s = StatusResolver(pa)
        qu =  s.getQueries()

        stat = {"passed":True}
        passed1 = StatusResolver.get_with_status(qu,stat)
        passed2 = s.getWithStatus(stat) 
        
        assert passed1 == passed2
