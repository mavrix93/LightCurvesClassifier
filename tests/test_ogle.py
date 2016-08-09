'''
Created on Jul 20, 2016

@author: Martin Vo
'''
import unittest
from db_tier.stars_provider import StarsProvider
from entities.right_ascension import RightAscension
from entities.declination import Declination



class Test(unittest.TestCase):






    def testNameParsing(self):
        print parseFieldIdFromName("test_light_curves/LMC_SC10173573.dat")
        

"""    def testName(self):
        obtain_params = {
        "ra":RightAscension(5.56*15),
        "dec":Declination(-69.99),
        "delta":3,
        "target":"lmc"
         }
        
        
        ogle_prov = StarsProvider().getProvider(obtain_method="ogle",
                                        obtain_params=obtain_params)
        stars = ogle_prov.getStarsWithCurves()
        
        print stars[0].ident["ogle"]["name"]"""


