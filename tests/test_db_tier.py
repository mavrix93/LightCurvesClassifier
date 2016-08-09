'''
Created on Aug 7, 2016

@author: Martin Vo
'''
import unittest
from entities.right_ascension import RightAscension
from entities.declination import Declination
from db_tier.stars_provider import StarsProvider
from utils.stars import plotStarsPicture


class TestDbTier(unittest.TestCase):


    def setUp(self):
        self.db_key = "ogle"
        self.query = {
        "ra":RightAscension(5.56*15),
        "dec":Declination(-69.99),
        "delta":3,
        "target":"lmc"
         }



    def testObtainStars(self):
        ogle_prov = StarsProvider().getProvider(obtain_method="ogle",
                                        obtain_params = self.query)
        stars = ogle_prov.getStarsWithCurves()
        plotStarsPicture(stars)
