from matplotlib import pyplot
import unittest

from lcc.db_tier.stars_provider import StarsProvider
from lcc.stars_processing.deciders.supervised_deciders import SVCDec
from lcc.stars_processing.descriptors.curve_shape_descr import CurvesShapeDescr
from lcc.stars_processing.descriptors.hist_shape_descr import HistShapeDescr
from lcc.stars_processing.stars_filter import StarsFilter
import numpy as np


class Test(unittest.TestCase):

    def setUp(self):
        days_per_bin = 10
        alphabet_size = 15

        s_queries = [{"path": "quasars"}]
        client = StarsProvider().getProvider(
            obtain_method="FileManager", obtain_params=s_queries)
        self.s_stars = client.getStars()

        c_queries = [{"path": "some_stars"}]
        client = StarsProvider().getProvider(
            obtain_method="FileManager", obtain_params=c_queries)
        self.c_stars = client.getStars()

        self.N = int(np.mean([len(self.s_stars), len(self.c_stars)]))

        self.lc_shape_descriptor = CurvesShapeDescr(self.s_stars[:self.N / 3],
                                                    days_per_bin, alphabet_size)

        self.hist_shape_descriptor = HistShapeDescr(
            self.s_stars[:self.N / 3], 10, alphabet_size)
        self.qda_decider = SVCDec()

    def tearDown(self):
        pass

    def testROC(self):
        star_filter = StarsFilter(
            [self.lc_shape_descriptor, self.hist_shape_descriptor], [self.qda_decider])

        star_filter.learn(
            self.s_stars[self.N / 3:2 * self.N / 3], self.c_stars[2 * self.N / 3:])
        roc = star_filter.getROCs(
            self.s_stars, self.c_stars, 10)
        print roc
        pyplot.plot(roc[0], roc[1], "b-")
        pyplot.show()
        # self.c_stars[self.N / 2:], 5)


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
