'''
Created on Aug 7, 2016

@author: Martin Vo
'''
import unittest
from entities.right_ascension import RightAscension
from entities.declination import Declination

import numpy as np
from entities.light_curve import LightCurve
from entities.star import Star
from utils.stars import plotStarsPicture


class TestEntities(unittest.TestCase):


    def setUp(self):
        self.ra_value = 5.5
        self.ra_unit = "hours"
        self.dec_value = 49.1
        self.dec_unit = "degrees"
        
        self.db_origin = "ogleII"
        self.identifier = {"field": "LMC_SC1", "starid": 123456, "target":"lmc"}
        
        self.time_data = np.linspace(245000, 245500, 500)
        self.mag_data = np.sin(np.linspace(0,10,500)) + np.random.rand()
        self.err_data = np.random.rand(500)
        
        self.v_mag = 17.86
        self.b_mag = 18.42


    def testCreateStar(self):
        ra = RightAscension(self.ra_value,self.ra_unit)
        dec = Declination(self.dec_value, self.dec_unit)
        
        lc = LightCurve([self.time_data, self.mag_data, self.err_data])
        
        star = Star({self.db_origin: self.identifier}, ra, dec, {"v_mag" : self.v_mag, "b_mag" : self.b_mag})
        star.putLightCurve(lc)
        
        print star


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()