'''
Created on Nov 24, 2016

@author: Martin Vo
'''

import requests
import json
from entities.exceptions import QueryInputError
from entities.light_curve import LightCurve
from entities.star import Star
from entities.right_ascension import RightAscension
from entities.declination import Declination



class BaseCatalog(object):
    
    URL = "http://exoplanetarchive.ipac.caltech.edu/cgi-bin/nstedAPI/nph-nstedAPI?"
    
    FORMAT = "json"
    
    TABLE = None
    RA, RA_UNIT = "ra", "degrees"
    DEC, DEC_UNIT = "dec", "degrees"
    IDENT = ""
    NAME = ""
    MORE = ( )  
    
    
    
    
    """
    Attributes:
    -----------
    
    
    """
    
    def __init__(self, query):
        self.query = query
        
        self.star_select = self.getSelect( self.RA,
                                               self.DEC,
                                               self.NAME,
                                               *self.MORE)
        self.lc_select = self.getSelect( self.TIME, self.MAG, self.ERR )
        
    
    def getStars( self ):
        print "Starting query.."
        self.result = self.post( self.query, self.TABLE, self.star_select )[:1]
        print self.result
        return [self.mapStar( st ) for st in self.result]
    

    def post(self, query, table, select ):
        query["table"] = table
        query["select"] = select
        query["format"] = self.FORMAT
            
        result = requests.post( self.URL, query )        
        try:
            return json.loads( result.text )
        except ValueError:
            raise
            raise QueryInputError( "Invalid query" )
    
    def mapStar(self, query_result):
        ra = RightAscension( query_result[ self.RA], self.RA_UNIT)
        dec = Declination( query_result[ self.DEC], self.DEC_UNIT)
        
        ident = { self.TABLE: {"name" : query_result[ self.NAME ],
                                                           "ident" : "%s:%s" % (self.IDENT, query_result[self.IDENT]) }}
        
        
        more = {}
        if self.MORE:            
            for key, value in query_result.iteritems():
                if key in self.MORE:
                    more[key] = value
        

        
        return Star( ra = ra,
                     dec = dec,
                     ident = ident,
                     more = more )
        
        
    def getSelect(self, *select_list):
        select_text = ""
        for it in select_list:
            select_text += "%s " %it
            
        return select_text



class BaseArchive(BaseCatalog):
    
    LC_TABLE = ""
    LC_IDENT = ""
    TIME = ""
    MAG = ""
    ERR = ""  
    
    """
    Attributes:
    -----------
    
    
    """
    
    def getStarsWithCurves(self):
        
        stars = self.getStars()
        _light_curves = [self.post( {self.LC_IDENT : lc[self.LC_IDENT]}, self.LC_TABLE, self.lc_select ) for lc in self.result]
        
        light_curves = [ self.mapLightCurve( lc ) for lc in _light_curves ]
        print light_curves
        for st, lc in zip(stars, light_curves ):
            st.lightCurve = lc
        return stars
        
    def mapLightCurve(self, query_result):
        """
        
        """
       
        lc = []        
        for entry in query_result:
            print "ma", entry
            lc.append( (entry[ self.TIME ],
                        entry[ self.MAG ],
                        entry.get( self.ERR , 0 ) ))
            
            
        return LightCurve( lc )
    
        
        
        
        
        
            