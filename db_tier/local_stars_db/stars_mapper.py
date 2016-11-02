'''
Created on Nov 2, 2016

@author: martin
'''

from sqlalchemy.ext.declarative import declarative_base
from db_tier.local_stars_db.models import db_connect, Stars
from sqlalchemy.orm import sessionmaker


class StarsMapper(object):
    '''
    classdocs
    '''


    def __init__(self):
        '''
        Constructor
        '''
        
        self.session = self.getSession()
        
        
    def getSession( self ):
        """
        Obtain session to stars db
        """
        
        Base = declarative_base()    
        engine = db_connect()
        Base.metadata.create_all(engine)
        Base.metadata.bind = engine
        DBSession = sessionmaker(bind=engine, autoflush=False)
        return DBSession() 
    
    def uploadStar(self, star, lc_path = None):
        """
        Parameters:
        -----------
        
        
        Save star object to the database according to mapper specified in mapStar
        """
        maped_star = self.mapStar(star, lc_path)
        self.session.add( maped_star )
        self.session.commit()
    
    
    def mapStar(self, star, lc_path = None):
        
        if star.lightCurve:
            lc_n = len(star.lightCurve.time)
            lc_time_delta = star.lightCurve.time[-1] - star.lightCurve.time[0]
        else:
            lc_n = None
            lc_time_delta = None

        if star.ident.keys():
            db_origin = star.ident.keys()[0]
            print db_origin
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
    def createStar(self):
        pass