'''
Created on Feb 29, 2016

@author: Martin Vo
'''
import unittest
from db_tier.stars_provider import StarsProvider
from utils.advanced_query import repeated_query, query_starcats_from_file
from entities.exceptions import *
from warnings import warn

'''
This test class checking validity of output (list of stars) of star managers
'''
class TestObtainStars(unittest.TestCase):
    '''Check if the first star of returned list of stars is valid star object'''
    def checkValidityOfStar(self,stars):
        self.failUnless(len(stars))
        self.failUnless(stars[0].ra.__class__.__name__=="RightAscension")
        self.failUnless(stars[0].dec.__class__.__name__=="Declination")
        self.failUnless(stars[0].lightCurve.__class__.__name__=="LightCurve")
        self.failUnless(len(stars[0].lightCurve.time))
        self.failUnless(len(stars[0].lightCurve.mag)) 
                        
class TestProviders(TestObtainStars):

    def test_query_folder(self):
        '''Test obtaining stars from folder'''
        
        path1 = "./tests/test_data"
        path2 = "./test_data"
        
        params = {"path":path2,
                  "suffix":"dat",
                  "star_class":"star",
                  "files_limit" : None
                  }
        try:
            stars = StarsProvider().getProvider(obtain_method="file",**params).getStarsWithCurves()
        except InvalidFilesPath:
            params["path"] = path1
            stars = StarsProvider().getProvider( obtain_method="file",**params).getStarsWithCurves()
        self.checkValidityOfStar(stars)
        

 
    def test_coo_query_ogle(self):
        '''Test query stars from Ogle db'''
        
        ogle_coo_query = {"ra":5.560274*15,
                 "dec":-69.99812,
                 "delta":0.7,
                 "target":"lmc"
                 }
        stars = StarsProvider().getProvider(obtain_method="ogle",obtain_params=ogle_coo_query).getStarsWithCurves()
        self.checkValidityOfStar(stars)
        
    def test_starcat_query_ogle(self):
        ogle_query = {"starcat":"053234.08-695949.7", "target":"lmc"}
        stars = StarsProvider().getProvider(obtain_method="ogle",starcat="053234.08-695949.7", target="lmc").getStarsWithCurves()
        self.failUnless(len(stars)>0)
        self.checkValidityOfStar(stars)
        
    
    def test_repeated_query(self): 
        '''Test query stars via starcats'''
        target = "lmc"  
        q1 = {"starcat":"053233.09-695949.0","target":target}
        q2 = {"starcat":"053234.15-695943.8","target":target}
        q3 =  {"starcat":"053234.08-695949.7", "target":target}
        
        self.failUnless(repeated_query([q1,q2,q3], "ogle")) 
        
         
    def test_load_stars_object(self):
        path1 = "./tests/test_data"
        path2 = "./test_data"
        
        params = {"path":path2,
                  "object_file_name":"stars.object",
                  "star_class":"star",
                  }
        try:
            stars = StarsProvider().getProvider(obtain_method="file",**params).getStarsWithCurves()
        except InvalidFilesPath:
            params["path"] = path1
            stars = StarsProvider().getProvider(obtain_method="file",**params).getStarsWithCurves()
        except InvalidFile,e:
            warn(str(e))
            return True
        
        self.checkValidityOfStar(stars)
    
        
        
        

        
        
        
        

    
   


