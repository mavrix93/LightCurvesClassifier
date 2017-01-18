from stars_processing.descriptors.curve_shape import CurvesShape
from entities.star import Star
import numpy as np
import unittest
from stars_processing.descriptors.hist_shape import HistShape
from stars_processing.descriptors.variogram_shape import VariogramShape


class Test(unittest.TestCase):

    def setUp(self):
        self.star1 = Star()
        x = np.linspace(1, 10, 100)
        self.star1.lightCurve = [x, np.sin(x)]
        self.star2 = Star()
        self.star2.lightCurve = [x, np.cos(x)]
        self.star3 = Star()
        self.star3.lightCurve = [x, np.cos(x + 0.5)]

    def testCurveShape(self):
        lcdes = CurvesShape(50, 5)
        lcdes.loadCompStars([self.star2, self.star3])
        assert lcdes.getSpaceCoords(
            [self.star1], "closest")[0] < lcdes.getSpaceCoords([self.star1])[0]

    def testHistShape(self):
        hist = HistShape(10, 5)
        hist.loadCompStars([self.star2, self.star3])
        assert hist.getSpaceCoords(
            [self.star1], "closest")[0] == hist.getSpaceCoords([self.star1])[0]

    def testVarioShape(self):
        vario = VariogramShape(10, 5)
        vario.loadCompStars([self.star2, self.star3])
        assert vario.getSpaceCoords(
            [self.star1]) == vario.getSpaceCoords([self.star1], "closest")


if __name__ == "__main__":
    unittest.main()
