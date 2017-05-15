"""
Created on Mar 5, 2017

@author: martin
"""
import unittest
import numpy as np
from lcc.utils.data_analysis import to_ekvi_PAA


class Test(unittest.TestCase):

    def setUp(self):
        N = 80
        self.eq_x = np.linspace(0, 20, N)
        self.eq_y = np.sin(self.eq_x)

        self.noneq_x = self.eq_x**3
        # self.noneq_x = np.array([1, 5, 20, 35, 40, 60, 80, 90, 150, 190])

    def testEqPAA(self):
        x1, y1 = to_ekvi_PAA(self.eq_x, self.eq_y)
        x2, y2 = to_ekvi_PAA(self.noneq_x, self.eq_y, 5)

        print len(x2), x2.tolist()
        print len(self.noneq_x), self.noneq_x.tolist()

        # plt.plot(self.eq_x, self.eq_y, "bo")
        # plt.plot(x1, y1, "ro")
        # plt.show()
        # plt.plot(self.noneq_x, self.eq_y, "bo")
        # plt.plot(x2, y2, "ro")
        # plt.show()


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
