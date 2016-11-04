'''
Created on Nov 3, 2016

@author: martin
'''
from db_tier.local_stars_db.stars_mapper import StarsMapper
from db_tier.base_query import LightCurvesDb
from db_tier.local_stars_db.models import Stars
from sqlalchemy.exc import InvalidRequestError
from entities.exceptions import QueryInputError


class LocalDbClient(LightCurvesDb):
    
    def __init__(self, obtain_params = None):
        self.mapper = StarsMapper()
        self.obtain_params = obtain_params
        
    def getStarsWithCurves(self):
        try:
            db_stars = self.mapper.session.query( Stars ).filter_by( **self.obtain_params ).all()
        except InvalidRequestError:
            raise InvalidRequestError(" Invalid query for local db: %s" % self.obtain_params)
        
        if not db_stars:
            raise QueryInputError("There are no stars in db for query %s" % self.obtain_params)
        
        return [ self.mapper.createStar(db_star) for db_star in db_stars]
        
                
