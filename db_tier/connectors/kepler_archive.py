'''
Created on Nov 30, 2016

@author: Martin Vo
'''
import kplr

from entities.light_curve import LightCurve
from entities.star import Star
from db_tier.base_query import LightCurvesDb
from entities.right_ascension import RightAscension
from entities.declination import Declination
from astroquery.exceptions import InvalidQueryError

class KeplerArchive( LightCurvesDb ):
    '''
    This is connector to Kepler archive of light curves using kplr package. 
    So far there are two options of query:
    
        1) By kic number 
        
        2) By coordinates and radius for square search

    As all LightCurvesDb it have methods for obtaining Star objects with light curves
    '''
    
    RA_IDENT = "kic_degree_ra"
    DEC_IDENT = "kic_dec"
    
    NAME = "_name"
    
    IDENTIFIER = {"kic_2mass_id" : "2mass",
                  "_name" : "kepler"}
    
    STAR_MORE_MAP = {"kic_zmag" : "z_mag",                     
                    "kic_umag" : "u_mag",                
                    "kic_kmag" : "k_mag",
                    "kic_jmag" : "j_mag",
                    "kic_hmag" : "h_mag",
                    "kic_imag" : "i_mag",
                    "kic_gmag" : "g_mag",
                    "kic_teff" : "teff"}


    def __init__(self, obtain_params):
        '''
        Parameters:
        -----------
            obtain_params : list, iterable
                Array of dictionaries of queries. There have to be one of these
                set of keys in the dictionary:
                
                1) "kic_num" - for query by the kepler unique identifier
                
                2) "ra" (degrees), "dec" (degrees), "delta" (arcseconds) - for query in certain are 
        '''
        if type( obtain_params ) == dict:
            obtain_params = [ obtain_params ]
        self.query = obtain_params
        self.client = kplr.API()
        
    def getStarsWithCurves( self ):
        """
        Returns:
        --------
            List of Star objects with light curves according to queries
        """
        return self.getStars( lc = True )
        
    def getStars(self, lc = False):
        """
        Returns:
        --------
            List of Star objects according to queries
        """
        stars = []
        for que in self.query:
            stars += self._getStars( que, lc )
        return stars
        
    
    def _getStars(self, que, lc = True ):  
        """Get stars from one query"""
        
        kic_num = que.get( "kic_num", None)
        ra = que.get( "ra" , None)
        dec = que.get( "dec", None)
        delta = que.get( "delta", None )
        
        if kic_num:
            _stars = [self.client.star( kic_num )]
               
        elif ra and dec and delta:
            try:
                ra = float(ra)
                dec = float(dec)
                delta = float(delta) / 3600.0
            except:
                raise InvalidQueryError("Coordinates parameters conversion to float has failed")     
            
            query = {"kic_degree_ra" : "%f..%f" %(ra-delta/2, ra+delta/2),
                     "kic_dec" : "%f..%f" %(dec-delta/2, dec +delta/2)}
            
            _stars = self.client.stars( **query )
            
        else:
            raise InvalidQueryError("Unresolved query parameters")

        stars = []
        
        for _star in _stars:
            stars.append( self._parseStar(_star, lc))
            
        return stars
    
    def _parseStar(self, _star, lc):
        """Transform kplr Star object into package Star object"""
        
        star = Star()
        more = {}
        ident = {}
        for key, value in _star.__dict__.iteritems():
            
            if key in self.STAR_MORE_MAP.keys():
                more[self.STAR_MORE_MAP[key]] = value
            
            elif key in self.IDENTIFIER.keys():
                ident[ self.IDENTIFIER[key] ] = {}
                ident[ self.IDENTIFIER[key] ]["identifier"] = value
                ident[ self.IDENTIFIER[key] ]["name"] = "kic_" + value
                
            elif key == self.RA_IDENT:
                star.ra = RightAscension( value ) 
            
            elif key == self.DEC_IDENT:
                star.dec = Declination( value )
            
            elif key == self.NAME:
                star.name = value
        
        if lc:    
            star.lightCurve = self._getLightCurve( _star, lim = 1 ) 
        star.ident = ident
        star.more =  more
        return star       
        
    def _getLightCurve(self, star, lim = None ):
        """Obtain light curve"""
        
        lcs = star.get_light_curves(short_cadence=False)[ :lim]
        
        time, flux, ferr, quality = [], [], [], []
        for lc in lcs:
            with lc.open() as f:
                hdu_data = f[1].data
                time += hdu_data["time"].tolist()
                flux += hdu_data["sap_flux"].tolist()
                ferr += hdu_data["sap_flux_err"].tolist()
                quality += hdu_data["sap_quality"].tolist()
                
        return LightCurve( [time, flux, ferr] )
        