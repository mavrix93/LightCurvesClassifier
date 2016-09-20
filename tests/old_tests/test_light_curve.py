'''
Created on Feb 22, 2016

@author: Martin Vo
'''
from base_test_class import BaseTestClass
from entities.light_curve import LightCurve
import numpy


class TestLightCurve(BaseTestClass):
    '''Testing light curves'''

    def setUp(self):
        self.mag = [10,12,14,15,14,12,10]
        self.time = [1,2,3,4,5,6,7]
        self.err = [1,2,1,2,1,2,0]
        self.tuples = [(1,10),(2,12),(3,14),(4,15),(5,14),(6,12),(7,10)]
    
        self.lc =LightCurve([self.time,self.mag,self.err])
        self.lc_default_error = LightCurve([self.time,self.mag])
        self.lc_tuples = LightCurve(self.tuples)

    def testLoadFromList(self):
        self.failUnless(self.lc.mag.tolist() == self.mag)
        self.failUnless(self.lc.time.tolist() == self.time)
        self.failUnless(self.lc.err.tolist()== self.err)
        
        self.failUnless(self.lc_tuples.mag.tolist() == self.mag)
        self.failUnless(self.lc_tuples.time.tolist() == self.time)
        
        
    def testFillErrorArray(self):
        self.failUnless(self.lc_default_error.err.tolist() == numpy.zeros(len(self.lc.mag)).tolist())
        self.failUnless(self.lc_tuples.err.tolist() == numpy.zeros(len(self.lc.mag)).tolist())
        
        
    def testNotFillErrorArray(self):
        self.failIf(self.lc.err.tolist() == numpy.zeros(len(self.lc.mag)).tolist())
        
        
    #def testOpenFromFile(self):
        
        
        
   