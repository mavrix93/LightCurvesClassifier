'''
Created on Jul 20, 2016

@author: martin
'''
import unittest
from db_tier.connectors.file_manager import FileManager


class Test(unittest.TestCase):

    def testLoadFromFile(self):
        stars = FileManager({"path":"./test_light_curves/", "files_to_load": "LMC_SC1_1.dat"}).getStarsWithCurves()
        print stars
