'''
Created on Feb 22, 2016

@author: Martin Vo
'''

import base_test_class


from db_tier.file_manager import FileManager
from entities.star import Star
import utils.commons as co


#TODO: Parsing starcat/field_starid do not work properly    

class TestParse(base_test_class.BaseTestClass):
    '''This test class check parsing star identificators (coordinates and identifiers)'''

    def testParseStarcat(self):
        #starcat = "OGLE05323408-6959497"
        starcat = "050833.29-685427.5"
        expected_ra = 5.542800
        expected_dec = -69.99715
        ra,dec = co.parseCooFromStarcat(starcat)
        print "rrrrr", ra, dec
        #self.assertAlmostEqual(ra.getHours(), expected_ra, 3)
        #self.assertAlmostEqual(dec.getDegrees(), expected_dec, 3)
        
        
    def testParseFileName(self):
        starcatPath = "./data/lcs/OGLE05323408-6959497.mag"
        identifierPath = "./test_light_curves/LMC_SC10173573.dat"
        st = Star(None,None,(5+32/60.0+34.08/3600.0)*15, -69-59/60.0-49.7/3600.0)        
        
        #Test if parsing field and starid is done properly
        self.failUnless(("LMC_SC10","173573",None,None) ==FileManager.parseFileName(identifierPath))
        
        #Test if coordinates were parsed properly
        field,starid,ra,dec = FileManager.parseFileName(starcatPath)
        print "fff",field,starid,ra,dec
        self.failUnless(st ==Star(field,starid,ra,dec,None))
       
    def test_starcat_clean(self):
        starcat = "OGLE05323408-6959497"
        print co.clean_starcat(starcat) 
        
      

       
        
        