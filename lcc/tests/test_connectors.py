import unittest

from lcc.db_tier.stars_provider import StarsProvider
from lcc.entities.star import Star
import numpy as np
from lcc.utils.stars import plotStarsPicture


class Test(unittest.TestCase):

    def testKepler(self):
        # NOTE: Ok

        RESULTS_NUM = 4
        EQUAL = (1, 2)

        queries = [{"ra": 297.8399, "dec": 46.57427, "delta": 10, "nearest": True},
                   {"kic_num": 9787239},
                   {"kic_jkcolor": (0.3, 0.4), "max_records": 2}]

        client = StarsProvider().getProvider(obtain_method="Kepler",
                                             obtain_params=queries)
        stars = client.getStars()
        self.failIf(np.NaN in stars[1].lightCurve.getHistogram()[1])
        self.failUnless(stars and len(stars) == RESULTS_NUM)

    def testCorotFaint(self):
        queries = [{"Corot": "102706554"},
                   {"ra": 100.94235, "dec": -00.89651, "delta": 10}]
        client = StarsProvider().getProvider(
            obtain_method="CorotFaint", obtain_params=queries)
        stars = client.getStars(max_bins=10000)
        # plotStarsPicture(stars)

    def testCorotBright(self):
        RESULTS_NUM = 2

        queries = [{"ra": 102.707, "dec": -0.54089, "delta": 10},
                   {"CoRot": 116}]
        client = StarsProvider().getProvider(
            obtain_method="CorotBright", obtain_params=queries)

        stars = client.getStars(max_bins=100)
        self.failUnless(len(stars) == RESULTS_NUM)
        self.failIf(None in [st.lightCurve for st in stars])

    def testMacho(self):
        #
        RESULTS_NUM = 1
        queries = [{"Field": 1, "Tile": 3441, "Seqn": 25}]
        client = StarsProvider().getProvider(obtain_method="Macho",
                                             obtain_params=queries)
        stars = client.getStars()
        self.failUnless(len(stars) == RESULTS_NUM)
        self.failUnless(isinstance(stars[0], Star))

    def testOgle(self):
        queries = [{"starid": 2, "field_num": 1, "target": "lmc"},
                   {"ra": 5.545575 * 15, "dec": -70.55272, "delta": 30}]
        client = StarsProvider().getProvider(obtain_method="OgleII",
                                             obtain_params=queries)
        stars = client.getStars()
        print len(stars)
        plotStarsPicture(stars[1:])
        self.failUnless(len(stars) == 2)
        self.failUnless(isinstance(stars[0], Star))

    def testAsas(self):
        queries = [{"ASAS": "000030-3937.5"},
                   {"ra": 10.08, "dec": -39.625, "delta": 20},
                   {"ra": 0.1251, "dec": -39.6250, "delta": 10}]
        client = StarsProvider().getProvider(obtain_method="Asas",
                                             obtain_params=queries)
        stars = client.getStars()

        self.failIf(len(stars) == 0)
        self.failUnless(isinstance(stars[0], Star))
        print " ,".join([st.coo.to_string() for st in stars])

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
