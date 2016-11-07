'''
Created on Nov 3, 2016

@author: martin
'''
from db_tier.local_stars_db.stars_mapper import StarsMapper
from db_tier.base_query import LightCurvesDb
from db_tier.local_stars_db.models import Stars
from sqlalchemy.exc import InvalidRequestError
from entities.exceptions import QueryInputError
import warnings
import re

# TODO: Allow query with two same keys in order to get closed ranges

class LocalDbClient(LightCurvesDb):
    """
    
    
    Example:
    ---------
        query = {"redshift": "<100", "id" : "<10" }
        db = LocalDbClient(query, db_key = "milliquas")        
        stars =  db.getStarsWithCurves() 
    
    """
    
    def __init__(self, obtain_params = {}, db_key = "local", raise_if_not = True):
        self.mapper = StarsMapper( db_key )
        self.obtain_params = obtain_params
        self.raise_if_not = raise_if_not
        
    def getStarsWithCurves(self):
        
        stars = []
        
        for param in self.obtain_params:
            try:
                que = self._getWithRanges( self.mapper.session.query( Stars ), param )
                db_stars = que.all()
            except InvalidRequestError:
                raise InvalidRequestError(" Invalid query for local db: %s" % self.obtain_params)
            
            if not db_stars:            
                if self.raise_if_not:
                    raise QueryInputError("There are no stars in db for query %s" % self.obtain_params)
                else:
                    warnings.warn("There are no stars in db for query %s" % self.obtain_params)
            
            stars += [ self.mapper.createStar(db_star) for db_star in db_stars]
        
        return stars
    
    
    def _getWithRanges(self, que, params_dict):
        

        for key, value in params_dict.iteritems():            
            
            mat =  re.match( "^(?P<sym>[>|<])(?P<num>\d+)",  str(value))
            
            mat2 =  re.match( "^(?P<sym>!=)(?P<num>\d+)",  str(value))
            
            if mat:        
                if mat.group("sym") == ">":
                    que = que.filter( getattr(Stars, key) >= mat.group("num") )
                    
                elif mat.group("sym") == "<":
                    que = que.filter( getattr(Stars, key) <= mat.group("num") )
                    
                else:
                    raise Exception("Parsing < > failed.\n%s" % mat.groupdict())
                
            elif mat2:
                que = que.filter( getattr(Stars, key) != mat2.group("num") )                
                
            else:
                que = que.filter( getattr(Stars, key) == value )
        return que
        
                
