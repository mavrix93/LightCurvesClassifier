import logging

from lcc.data_manager.package_reader import PackageReader
from lcc.entities.star import Star
import unittest
import numpy as np

logging.basicConfig(level=logging.DEBUG)


class TestDescriptors(unittest.TestCase):

    n_stars = 10

    def setUp(self):
        self.descriptors = PackageReader.getClassesDict("descriptors")
        self.stars = []
        for i in range(self.n_stars):
            star = Star()
            x = np.linspace(0, 100, 100)
            y = np.sin(x**i)
            y[0] = np.nan
            x[:20] = np.linspace(-30, -10, 20)
            star.putLightCurve([x, y])
            self.stars.append(star)

    def testAbbe(self):
        abbe_filter = self.descriptors["AbbeValueDescr"]
        abbe_values = abbe_filter(bins=10).getSpaceCoords(self.stars)
        self.assertTrue(len(abbe_values) == self.n_stars)
        assert not np.isnan(abbe_values).all()
        # TODO
        # assert False not in [abbe_values[i] < abbe_values[i + 1] for i in range(len(abbe_values) - 1)]

    def testSkewness(self):
        skewness_descr = self.descriptors["SkewnessDescr"]
        sk_values = skewness_descr(bins=30).getSpaceCoords(self.stars)
        assert not np.isnan(sk_values).all()

    def testComparative(self):
        logging.debug("Starting comparative test")
        descr = self.descriptors["HistShapeDescr"](self.stars[:4], 10, 10)


if __name__ == "__main__":
    unittest.main()
