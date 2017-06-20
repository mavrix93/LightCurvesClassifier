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
        for _ in range(self.n_stars):
            star = Star()
            x = np.linspace(0,100)
            y = np.sin(x)
            star.putLightCurve([x,y])
            self.stars.append(star)

    def testAbbe(self):
        first_abbe = 1.7096658186181843

        abbe_filter = self.descriptors["AbbeValueDescr"]
        abbe_values = abbe_filter(bins=10).getSpaceCoords(self.stars)
        print abbe_values
        self.failUnless(len(abbe_values) == self.n_stars)
        self.failUnless(abbe_values[0] == first_abbe)


    def testComparative(self):
        logging.debug("Starting comparative test")
        descr = self.descriptors["HistShapeDescr"](self.stars[:4], 10, 10)
        print "vv", descr.getSpaceCoords(self.stars[5:])

if __name__ == "__main__":
    unittest.main()