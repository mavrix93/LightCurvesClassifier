'''
Created on Jan 5, 2016

@author: Martin Vo
'''
import numpy as np

from entities.right_ascension import RightAscension
from entities.declination import Declination
from db_tier.TAP_query import TapClient
from entities.star import Star


class _MachoDb(TapClient):
    '''
    Client for Macho database  
    '''
   
    # Macho parameters        
    CURVE_TABLE = "photometry_view"
    STAR_TABLE = "public.star_view"
    CURVE_SELECT_COLUMN = "dateobs, bmag" 
    STAR_SELECT_COLUMN = "rarad, decrad, seqn, tile, field" 
    STAR_FIELD_COLUMN = "fieldid"
    STAR_TILE_COLUMN = "tileid"
    STAR_SEQN_COLUMN = "seqn"
    STAR_ID_COLUMN = "starid"
    
    # Conversion rate of coordinates from degrees
    COO_UNIT_CONV = np.pi / 180.
    
    LC_META = {"color" : "B"}
    
    MACHO_URL = "http://machotap.asvo.nci.org.au/ncitap/tap"
    

    def getStarsWithCurves(self):
        '''
        Returns:
        --------
            List of stars with their light curves
        '''
        
        stars = []
        for que in self.queries:
            stars.append(self.getLightCurve(que))
        return stars
    
    def getStars(self):
        '''
        Returns:
        --------
            List of stars 
        '''
        stars = []
        for que in self.queries:
            rarad, decrad, seqn, tile, starid = self.getStarInfo(que)
            
            ident = {"macho" : {"name" : starid}}
            
            star =  Star(ident,starid, RightAscension(rarad,"radians"),Declination(decrad,"radians"))
            stars.append(star)            
        return stars
    

    def getLightCurve(self,starid):
        raw_star = self.getStarInfo(starid)
        if raw_star:
            rarad, decrad,seqn, tile, starid = raw_star
            lc_query = {"table": self.CURVE_TABLE,
                          "select": self.CURVE_SELECT_COLUMN,
                          "conditions": [(self.STAR_SEQN_COLUMN, seqn),(self.STAR_TILE_COLUMN, tile)],
                          "URL": self.MACHO_URL}
            
            lc =  self.postQuery(lc_query)[0]
            
            ident = {"macho" : {"name" : starid}}
            star =  Star( ident, starid, RightAscension(rarad, "radians"),Declination(decrad, "radians"))
            star.putLightCurve(lc, meta = self.LC_META)
            return star

    def getStarInfo(self, que ):
        star_query = {"table":self.STAR_TABLE,
                      "select": self.STAR_SELECT_COLUMN,
                      "conditions": que.items(),
                      "URL":self.MACHO_URL}
        
        result = self.postQuery(star_query)
        if result:
            return result[0]   





