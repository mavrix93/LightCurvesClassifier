'''
Created on Jul 20, 2016

@author: martin
'''
import unittest
from db_tier.file_manager import FileManager


class Test(unittest.TestCase):



    def testLoadFromFile(self):
        stars = FileManager({"path":"./test_light_curves/"}).getStarsWithCurves()
        print stars[0].resolveIdent("ogle")
