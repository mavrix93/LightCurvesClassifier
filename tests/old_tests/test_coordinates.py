'''
Created on Feb 22, 2016

@author: Martin Vo
'''
import unittest
from entities.declination import Declination
from entities.right_ascension import RightAscension
from base_test_class import BaseTestClass

class TestCoordinates(BaseTestClass):
    '''
    Testing of coordinate classes
    '''
            
    def setUp(self):
        self.validDegreeNum = 55.45
        self.validDegreeStr = "0"
        self.invalidDegreeNum = 400
        self.invalidDegreeStr = "notNumberJustText"


    def testVerificateDec(self):
        self.failUnless(Declination(self.validDegreeNum))
        self.failUnlessRaises(Declination(self.validDegreeStr))
        
    def testNotVerificateDec(self):
        self.failIfRaises(Declination,self.invalidDegreeNum)
        self.failIfRaises(Declination,self.invalidDegreeStr)
        
        
    def testVerificateRa(self):
        self.failUnless(RightAscension(self.validDegreeNum))
        self.failUnlessRaises(RightAscension(self.validDegreeStr))
        self.failUnless(RightAscension(self.validDegreeNum).getHours()==self.validDegreeNum/15.0 )
        
    def testNotVerificateRa(self):
        self.failIfRaises(RightAscension,self.invalidDegreeNum)
        self.failIfRaises(RightAscension,self.invalidDegreeStr)
    
    

        
