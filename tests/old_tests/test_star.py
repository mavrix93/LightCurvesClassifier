'''
Created on Feb 25, 2016

@author: Martin Vo
'''
import unittest
from entities.star import Star


class TestStars(unittest.TestCase):
    '''Testing star objects'''

    def setUp(self):
        self.star = Star(ident={"ogle":{"field":1,"starid":1,"target":"lmc"}},ra=5.0, dec=20)
        self.near_star =  Star(ident={"ogle":{"field":1,"starid":2,"target":"lmc"}} , ra=5.0, dec=20.0001)       
        self.far_star =  Star(ident={"ogle":{"field":1,"starid":3,"target":"smc"}} , ra=5.0, dec=25) 
        self.same_name_star = Star(ident={"ogle":{"field":1,"starid":1,"target":"lmc"}})
    

    def testNearStar(self):
        self.failUnless(self.near_star== self.star)
        
    def testFarStar(self):
        self.failIf(self.far_star==self.star)
    
    def testSameName(self):
        self.failUnless(self.same_name_star==self.star)
        
    def testPrint(self):
        print self.star
        
    def testSave(self):
        self.star.saveStar()
        

