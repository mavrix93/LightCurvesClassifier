import unittest

import lcc.stars_processing.deciders.supervised_deciders as dec


class TestDeciders(unittest.TestCase):
    def setUp(self):
        self.deciders = [dec.AdaBoostDec, dec.ExtraTreesDec, dec.GaussianNBDec, dec.LDADec, dec.QDADec,
                         dec.RandomForestDec, dec.SVCDec, dec.TreeDec]


    def test_init(self):
        [d() for d in self.deciders]


if __name__ == '__main__':
    unittest.main()
