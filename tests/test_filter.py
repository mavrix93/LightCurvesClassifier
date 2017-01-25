import unittest
import numpy as np
from entities.star import Star
from utils.stars import plotStarsPicture
from stars_processing.stars_filter import StarsFilter
from stars_processing.descriptors.curve_shape_descr import CurvesShape
from stars_processing.deciders.supervised_deciders import QDADec
from stars_processing.tools.visualization import plotProbabSpace
from stars_processing.descriptors.hist_shape_descr import HistShape
from db_tier.stars_provider import StarsProvider
from stars_processing.tools.visualization import plotParamsSpace
from matplotlib import pyplot
from stars_processing.deciders.neuron_decider import NeuronDecider
from stars_processing.deciders.supervised_deciders import SVCDec


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
        self.qda_decider = SVCDec()

    def tearDown(self):
        pass

    def _testProbabSpace(self):
        star_filter = StarsFilter(
            [self.lc_shape_descriptor, self.hist_shape_descriptor], [self.qda_decider])

        star_filter.learn(
            self.s_stars[self.N / 3:2 * self.N / 3], self.c_stars[2 * self.N / 3:])

        plotProbabSpace(
            np.linspace(12, 17, 500), np.linspace(1, 4, 500), star_filter, option="return")

        plot_opts1 = {
            "s": 20, "edgecolor": 'red', "color": "blue", "linewidth": 0.6,
            "label": "searched"}
        plot_opts2 = {
            "s": 15, "edgecolor": 'blue', "color": "red", "linewidth": 0.6,
            "label": "cont"}
        x1, y1 = np.array(star_filter.getSpaceCoordinates(self.s_stars)).T
        x2, y2 = np.array(star_filter.getSpaceCoordinates(self.c_stars)).T

        plotParamsSpace(x1, y1, plot_opts=plot_opts1, show=False)
        plotParamsSpace(x2, y2, plot_opts=plot_opts2, show=True)

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
