from matplotlib import pyplot
import unittest

from lcc.entities.star import Star
import numpy as np

# TODO


class Test(unittest.TestCase):

    def setUp(self):
        N = 100

        x = np.linspace(0, 10, 1000)

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
        N = 1000
        var_abbes = [st.lightCurve.getAbbe(bins=N) for st in self.variables]
        noisy_abbes = [st.lightCurve.getAbbe(bins=N) for st in self.noisy]
        print np.mean(var_abbes)
        print np.mean(noisy_abbes)
        pyplot.hist(var_abbes, color="b")
        pyplot.hist(noisy_abbes, color="r")
        pyplot.show()

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testAbbe']
    unittest.main()
