'''
Created on Jan 5, 2016

@author: Martin Vo
'''

from entities.right_ascension import RightAscension
from entities.declination import Declination
from db_tier.TAP_query import TapClient
from entities.star import Star
from db_tier.base_query import LightCurvesDb


class MachoDb(TapClient, LightCurvesDb):
    '''
    DESCRIP:      TAP_app object is nonposted query object, ready to be posted via tap protocol and retrieve data) 
    '''
   
    
    #Macho parameters        
    CURVE_TABLE = "photometry_view"
    STAR_TABLE = "public.star_view"
    CURVE_SELECT_COLUMN = "dateobs,bmag" 
    STAR_SELECT_COLUMN = "rarad,decrad, seqn, tile" 
    STAR_FIELD_COLUMN = "fieldid"
    STAR_TILE_COLUMN = "tileid"
    STAR_SEQN_COLUMN = "seqn"
    STAR_ID_COLUMN = "starid"
    MACHO_URL = "http://machotap.asvo.nci.org.au/ncitap/tap"
    
    def __init__(self,starids):
        self.starids = starids
        
        

    def getStarsWithCurves(self):
        '''
        @return: List of stars with their light curves
        '''
        
        stars = []
        for starid in self.starids:
            stars.append(self.getLightCurve(starid))
        return stars
    
    def getStars(self):
        stars = []
        for starid in self.starids:
            rarad, decrad,seqn, tile = self.getStarInfo(starid)
            star =  Star(None,starid, RightAscension(rarad,"radians"),Declination(decrad,"radians"))
            stars.append(star)            
        return stars
    
    

        
    def getLightCurve(self,starid):
        rarad, decrad,seqn, tile = self.getStarInfo(starid)
        lc_query = {"table":self.CURVE_TABLE,
                      "select": self.CURVE_SELECT_COLUMN,
                      "conditions":[(self.STAR_SEQN_COLUMN,seqn),(self.STAR_TILE_COLUMN,tile)],
                      "URL":self.MACHO_URL}
        
        lc =  self.postQuery(lc_query)[0]
        
        star =  Star(None,starid, RightAscension(rarad,"radians"),Declination(decrad,"radians"))
        star.putLightCurve(lc)
        return star
    
        
    
    def getStarInfo(self,starid):
        star_query = {"table":self.STAR_TABLE,
                      "select": self.STAR_SELECT_COLUMN,
                      "conditions":[(self.STAR_ID_COLUMN,starid)],
                      "URL":self.MACHO_URL}
        
        rarad,decrad,seqn, tile = self.postQuery(star_query)[0]
        return rarad,decrad,seqn, tile    





