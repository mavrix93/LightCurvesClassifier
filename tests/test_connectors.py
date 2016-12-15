'''
Created on Dec 15, 2016

@author: Martin Vo
'''
import unittest

from db_tier.stars_provider import StarsProvider
from entities.star import Star


class Test(unittest.TestCase):

    def testMacho(self):
        queries = [{"ra": 0.4797, "dec": -67.1290, "delta": 10},
                   {"Field": 1, "Tile": 3441, "Seqn": 25}]
        client = StarsProvider().getProvider(obtain_method="MachoDb",
                                             obtain_params=queries)
        stars = client.getStarsWithCurves()
        print ", ".join([st.name for st in stars])

    """def testOgle(self):
        queries = [{"starid": 2, "field_num": 1, "target": "lmc"},
                   {"ra": 83.2372, "dec": -70.5579, "delta": 20, "target": "lmc"}]
        client = StarsProvider().getProvider(obtain_method="OgleII",
                                             obtain_params=queries)
        stars = client.getStarsWithCurves()

        self.failUnless(len(stars) == 2)
        self.failUnless(isinstance(stars[0], Star))

    def testAsas(self):
        queries = [{"ASAS": "000030-3937.5"},
                   {"ra": 10.08, "dec": -39.625, "delta": 20},
                   {"ra": 0.1251, "dec": -39.6250, "delta": 10}]
        client = StarsProvider().getProvider(obtain_method="AsasArchive",
                                             obtain_params=queries)
        stars = client.getStarsWithCurves()

        self.failIf(len(stars) == 0)
        self.failUnless(isinstance(stars[0], Star))
        print " ,".join([st.coo.to_string() for st in stars])"""

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
