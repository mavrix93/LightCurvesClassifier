'''
Created on Jan 25, 2017

@author: Martin Vo
'''
import unittest
import numpy as np

from lcc.stars_processing.deciders.supervised_deciders import QDADec
from lcc.stars_processing.tools.params_estim import ParamsEstimator
from lcc.stars_processing.descriptors.abbe_value_descr import AbbeValueDescr
from lcc.entities.star import Star
from matplotlib import pyplot
from lcc.stars_processing.tools.visualization import plotProbabSpace
from lcc.stars_processing.descriptors.variogram_slope_descr import VariogramSlopeDescr
from lcc.stars_processing.descriptors.curve_shape_descr import CurvesShapeDescr


# TODO: Need to be fixed
class Test(unittest.TestCase):

    def setUp(self):
        N = 20

        x = np.linspace(0, 10, 100)

        self.template = []
        for ii in range(N):
            st = Star(name="TemplateStar%i" % ii)
            st.putLightCurve([x, np.cos(x) + np.random.normal(x) * 0.1])
            self.template.append(st)

        self.variables = []
        for ii in range(N):
            st = Star(name="VariableStar%i" % ii)
            st.putLightCurve([x, np.sin(x) + np.random.normal(x) * 0.1])
            self.variables.append(st)

        self.noisy = []
        for ii in range(N):
            st = Star(name="NonvariableStar%i" % ii)
            st.putLightCurve([x, np.random.normal(x) * 2])
            self.noisy.append(st)

    def testName(self):
        deciders = [QDADec]
        descriptors = [AbbeValueDescr, CurvesShapeDescr]
        static_params = {"AbbeValueDescr": {"bins": 100},
                         "CurvesShapeDescr": {"comp_stars": self.template}}
        tuned_params = [{"CurvesShapeDescr": {"days_per_bin": 3, "alphabet_size": 10}},
                        {"CurvesShapeDescr": {"days_per_bin": 0.5, "alphabet_size": 12}}]
        
        est = ParamsEstimator(self.variables, self.noisy, descriptors, deciders,
                              tuned_params, static_params=static_params)

        star_filter, stat, best_params = est.fit()
        assert best_params != None

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
