import unittest
import numpy as np
from entities.star import Star
from utils.stars import plotStarsPicture
from stars_processing.stars_filter import StarsFilter
from stars_processing.descriptors.curve_shape import CurvesShape
from stars_processing.deciders.supervised_deciders import QDADec
from utils.visualization import plotProbabSpace
from stars_processing.descriptors.hist_shape import HistShape
from db_tier.stars_provider import StarsProvider


class Test(unittest.TestCase):

    def setUp(self):
        days_per_bin = 10
        alphabet_size = 15

        s_queries = [{"path": "quasars"}]
        client = StarsProvider().getProvider(
            obtain_method="FileManager", obtain_params=s_queries)
        self.s_stars = client.getStarsWithCurves()

        c_queries = [{"path": "some_stars"}]
        client = StarsProvider().getProvider(
            obtain_method="FileManager", obtain_params=c_queries)
        self.c_stars = client.getStarsWithCurves()

        self.N = int(np.mean([len(self.s_stars), len(self.c_stars)]))

        self.lc_shape_descriptor = CurvesShape(self.s_stars[:self.N / 3],
                                               days_per_bin, alphabet_size)

        self.hist_shape_descriptor = HistShape(
            self.s_stars[:self.N / 3], 10, alphabet_size)
        self.qda_decider = QDADec()

    def tearDown(self):
        pass

    def testROC(self):
        star_filter = StarsFilter(
            [self.lc_shape_descriptor, self.hist_shape_descriptor], [self.qda_decider])

        star_filter.learn(
            self.s_stars[self.N / 3:2 * self.N / 3], self.c_stars[2 * self.N / 3:])

        plotProbabSpace(
            np.linspace(8, 18, 100), np.linspace(0, 5, 100), star_filter)
        # print star_filter.getROCs(self.s_stars[self.N / 2:],
        # self.c_stars[self.N / 2:], 5)


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
