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


class StarsMapper(object):
    '''
    This class is responsible for communication between Star objects
    and Stars database 
    '''

    def __init__(self, db_key = "local"):
        '''
        Attributes:
        -----------
            session : session instance
                Instance which communicates with database
        '''
        
        self.db_key = db_key
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
    
    def uploadStar(self, star, lc_path = None):
        """
        Save star object to the database according to mapper specified in mapStar
        
        Parameters:
        -----------
            star : Star
                Star to be uploaded to db
                
            lc_path : str
                Path to the light curve file of this star
        """
        maped_star = self.mapStar(star, lc_path)
        st = self.session.query( Stars ).filter( Stars.identifier == maped_star.identifier,
                                                 Stars.db_origin == maped_star.db_origin,
                                                 Stars.light_curve == maped_star.light_curve ).first()
        
        
        # TODO: Ask for updating
        if not st:
            #self.session.delete( st )
            #self.session.commit()
        
            self.session.add( maped_star )
            self.session.commit()
        else:
            return False
        return True
    
    
    def mapStar(self, star, lc_path = None):
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
        
        if star.lightCurve:
            lc_n = len(star.lightCurve.time)
            lc_time_delta = star.lightCurve.time[-1] - star.lightCurve.time[0]
        else:
            lc_n = None
            lc_time_delta = None

        if star.ident.keys():
            db_origin = star.ident.keys()[0]
            identifier = star.ident[ db_origin ]
            name = identifier.get( "name", None )
        else:
            db_origin = None
            identifier = None
            name = None
                    
        return Stars(identifier = str(identifier)[1:-1],
                   name = name,
                   db_origin = db_origin,
                   ra = star.ra.degrees,
                   dec = star.dec.degrees,
                   star_class = star.starClass,
                   light_curve = lc_path,
                   b_mag = star.more.get( "b_mag", None),
                   v_mag = star.more.get( "v_mag", None),
                   i_mag = star.more.get( "i_mag", None),
                   lc_n = lc_n,
                   lc_time_delta = lc_time_delta)
        

        
    # TODO: Create Star object from db star
    def createStar(self, db_star):
        if db_star.db_origin:
            ident = { db_star.db_origin : {"identifier" : db_star.identifier, "name" : db_star.name},
                     "local_db" : {"id" : db_star.id}}
        else:
            ident = {"local_db" : {"id" : db_star.id} }
            
        more = {"b_mag" : db_star.b_mag,
                "v_mag" : db_star.v_mag,
                "i_mag" : db_star.i_mag,
                "lc_time_delta" : db_star.lc_time_delta,
                "lc_n" : db_star.lc_n,
                "uploaded" : db_star.uploaded}
        
        star = Star(ident = ident,
                    ra = db_star.ra,
                    dec = db_star.dec,
                    more = more,
                    starClass = db_star.star_class)
        
        
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
            
        
        