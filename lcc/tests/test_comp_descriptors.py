import unittest

import numpy as np

from lcc.entities.star import Star
from lcc.stars_processing.descriptors.curve_shape_descr import CurvesShapeDescr
from lcc.stars_processing.descriptors.hist_shape_descr import HistShapeDescr
from lcc.stars_processing.descriptors.variogram_shape_descr import VariogramShapeDescr


class TestComparative(unittest.TestCase):

    def setUp(self):
        self.star1 = Star()
        x = np.linspace(1, 10, 100)
        x2 = x**2
        self.star1.putLightCurve([x, x2 / x2[-1]])
        self.star2 = Star()
        self.star2.putLightCurve([x, np.cos(x)])
        self.star3 = Star()
        xx = np.linspace(1,45, 600)
        self.star3.putLightCurve([xx, np.cos(xx + 0.1)*xx])

    def testCurveShape(self):
        lcdes = CurvesShapeDescr([self.star2], 0.6, 10)
        assert lcdes.getSpaceCoords(
            [self.star3])[0] < lcdes.getSpaceCoords([self.star1])[0]

    def testHistShape(self):
        hist = HistShapeDescr([self.star2], 10, 5)
        assert hist.getSpaceCoords(
            [self.star3])[0] > hist.getSpaceCoords([self.star1])[0]

    def testVarioShape(self):
        vario = VariogramShapeDescr([self.star2], 10, 5)
        assert vario.getSpaceCoords(
            [self.star3]) > vario.getSpaceCoords([self.star1])


if __name__ == "__main__":
    unittest.main()
