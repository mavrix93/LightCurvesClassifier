'''
Created on Nov 2, 2016

@author: Martin Vo
'''

from sqlalchemy.ext.declarative import declarative_base
from db_tier.local_stars_db.models import db_connect, Stars
from sqlalchemy.orm import sessionmaker
from entities.star import Star
from entities.light_curve import LightCurve
from conf import settings
import os
import warnings
from utils.helpers import progressbar
from db_tier.local_stars_db.models_crossmatch_milliquas_ogle import StarsMO

#NOTE: Hardcoded for Ogle-Milliquas
class CrossmatchMapper(object):
    '''
    This class is responsible for communication between Star objects
    and Stars database 
    '''

    def __init__(self, db_key = None):
        '''
        Attributes:
        -----------
            session : session instance
                Instance which communicates with database
        '''
        
        self.db_key = "og_milli_crossmatch"
        self.session = self.getSession()
                
        
    def getSession( self ):
        """
        Obtain session to stars db
        """
        
        Base = declarative_base()    
        engine = db_connect( self.db_key )
        Base.metadata.create_all(engine)
        Base.metadata.bind = engine
        DBSession = sessionmaker(bind=engine, autoflush=False)
        return DBSession() 
    
    def uploadStar(self, og_star, mil_star, lc_path = None):
        
        maped_star = self.mapStar(og_star, mil_star, lc_path)
        
        
        self.session.add( maped_star )
        self.session.commit()
    
    
    def mapStar(self, og_star, mil_star, lc_path = None):
        """
        Transform Star object into Stars db table object which can be uploaded
        into the stars db
        
        Parameters:
        -----------
            star : Star
                Star to be uploaded to db
                
            lc_path : str
                Path to the light curve file of this star
                
        Returns:
        -------
            Mapped db star object
        
        """
        
        if og_star.lightCurve:
            lc_n = len(og_star.lightCurve.time)
            lc_time_delta = og_star.lightCurve.time[-1] - og_star.lightCurve.time[0]
        else:
            lc_n = None
            lc_time_delta = None
       

        identifier_milliquas = mil_star.ident[ "milliquas" ]["name"]
        
        name_ogle = og_star.ident[ "ogle" ][ "name" ] 
        identifier_ogle = name_ogle
        name_milliquas = mil_star.ident[ "milliquas" ]["name"]
        
        b = mil_star.more.get( "b_mag", None)
        if str(b) == "0.0":
            b = None
            
        r = mil_star.more.get( "r_mag", None)
        if str(r) == "0.0":
            r = None

                    
        return StarsMO(identifier_ogle = identifier_ogle,
                   identifier_milliquas = identifier_milliquas,
                   name_ogle = name_ogle,
                   name_milliquas = name_milliquas,
                   ra_milliquas = mil_star.ra.degrees,
                   dec_milliquas = mil_star.dec.degrees,
                   ra_ogle = og_star.ra.degrees,
                   dec_ogle = og_star.dec.degrees,
                   star_class = mil_star.starClass,
                   light_curve = lc_path,
                   angle_dist = int( round(mil_star.getDistance( og_star )*3600)),
                   redshift = mil_star.more["redshift"],
                   b_mag_milliquas = b,
                   b_mag_ogle = og_star.more.get( "b_mag", None),
                   v_mag_ogle = og_star.more.get( "v_mag", None),
                   i_mag_ogle = og_star.more.get( "i_mag", None),
                   r_mag_milliquas = r,
                   lc_n = lc_n,
                   lc_time_delta = lc_time_delta)
        
    # TODO: Create Star object from db star
    def createStar(self, db_star):
            
        ident = { "milliquas" : {"identifier" : db_star.identifier_milliquas, "name" : db_star.name_milliquas},
                     "ogle" : {"identifier" : db_star.identifier_ogle, "name" : db_star.name_ogle}}
        
            
        more = {"b_mag_milliquas" : db_star.b_mag_milliquas,
                "b_mag_ogle" : db_star.b_mag_ogle,
                "v_mag_ogle" : db_star.v_mag_ogle,
                "i_mag_ogle" : db_star.i_mag_ogle,
                "r_mag_milliquas" : db_star.r_mag_milliquas,
                "lc_time_delta" : db_star.lc_time_delta,
                "lc_n" : db_star.lc_n,
                "uploaded" : db_star.uploaded,
                "redshift" : db_star.redshift,
                "ra_milliquas" : db_star.ra_milliquas,
                "dec_milliquas" : db_star.dec_milliquas,
                "ra_ogle" : db_star.ra_ogle,
                "dec_ogle" : db_star.dec_ogle}
        
        star = Star(ident = ident,
                    ra = db_star.ra_ogle,
                    dec = db_star.dec_ogle,
                    more = more,
                    starClass = db_star.star_class)
        
        if db_star.light_curve:
            lc = LightCurve( os.path.join(settings.LC_FOLDER, db_star.light_curve))        
            star.lightCurve = lc
            
        return star
        
        
    def uploadViaKeys(self, values):
        """
        Upload star into db via key and values
        
        Parameters:
        ----------
            values : list of dicts
                Every item of the list is dictionary with key corresponds with
                Stars model key
        """
        
        for value in progressbar(values, "Uploading: "):
            db_star = Stars( **value )            
            self.session.add( db_star )
            
        self.session.commit()
            
        
        