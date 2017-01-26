from matplotlib import pyplot
import unittest

from lcc.entities.star import Star
import numpy as np


class Test(unittest.TestCase):

    def setUp(self):
        N = 50

        x = np.linspace(0, 10, 100)

        self.variables = []
        for ii in range(N):
            st = Star(name="VariableStar%i" % ii)
            st.putLightCurve([x, np.sin(x) + np.random.normal(x) * 0.1])
            self.variables.append(st)

        self.noisy = []
        for ii in range(N):
            st = Star(name="VariableStar%i" % ii)
            st.putLightCurve([x, np.random.normal(x) * 2])
            self.noisy.append(st)

    def testAbbe(self):
        var_abbes = [st.lightCurve.getAbbe(bins=500) for st in self.variables]
        noisy_abbes = [st.lightCurve.getAbbe(bins=500) for st in self.noisy]

        pyplot.hist(var_abbes)
        pyplot.hist(noisy_abbes)
        pyplot.show()

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testAbbe']
    unittest.main()
