'''
Created on Nov 2, 2016

@author: Martin Vo
'''

from sqlalchemy.ext.declarative import declarative_base
from db_tier.local_stars_db.models import db_connect, Stars
from sqlalchemy.orm import sessionmaker


class StarsMapper(object):
    '''
    This class is responsible for communication between Star objects
    and Stars database 
    '''

    def __init__(self):
        '''
        Attributes:
        -----------
            session : session instance
                Instance which communicates with database
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
        if st:
            self.session.delete( st )
            self.session.commit()
        
        self.session.add( maped_star )
        self.session.commit()
    
    
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
        
        
    def isInDb(self, star):
        pass
        #self.session.query( Stars ).filter( Stars.name = star)
        
    # TODO: Create Star object from db star
    def createStar(self):
        pass