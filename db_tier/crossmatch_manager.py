'''
Created on Mar 22, 2016

@author: Martin Vo
'''

from utils.helpers import verbose
from commandline.parameters import params as p


class CrossmatchManager(object):
    '''
    This class is responsible for crossmatching of stars (with coordinates) with
    given database 
    
    
    @Example:   stars = OgleQso({"ra":60,"dec":-69.25,"rad":5000000000}).getStars()
                CrossmatchManager(OgleII).crossmatch(stars)
    '''


    def __init__(self, catalogue):
        '''
        @param catalogue: Db client for matching
        '''
        self.catalogue = catalogue
        
    def crossmatch(self,stars):
        '''
        Perform matching of databases 
                
        @param stars: Stars which will be matching         
        @return: List of pairs matching star - matched star
        '''
        
        
        crossmatched_stars = []
        i = 0
        for star in stars:
            pair = self.findStarInCatalogue(star)
            if pair: crossmatched_stars.append(pair)
            i+=1
        st = []
        for stars in crossmatched_stars:
            st.append(stars[0].putMatchStar(stars[1]))
            
        return crossmatched_stars
    
    def findStarInCatalogue(self,star,MAX_DELTA=10,MAX_ITER = 60,MIN_DELTA = 0.005):
        '''
        This method is searching for star in given catalogue according its coordinates.
        Search radius will be resizing until it finds nearest star to coordinates of given star.
        
        @param star: Star which coordinates will be used for searching
        @param MAX_DELTA: Maximal radius of searching
        @param MAX_ITER: Maximal number of iterations of radius resizing
        @param MIN_DELTA: In case of reaching this value during radius resizing
                          loop will be interrupted and first star will be returned
                          
        @return: Matching star and matched star or None if searching was failed        
        '''
        
        #star = self.updateStar(star)
        ra,dec = star.ra.degrees, star.dec.degrees
        
        delta = 3
        i = 0
        verbose("Start.." % star,2,p.VERBOSITY)
        while (delta <MAX_DELTA and i < MAX_ITER):
            query = {"ra":ra,"dec":dec,"delta":delta,"target":"lmc"}
            result = self.catalogue(query).getStars()
            results_num = len(result)
            
            if (results_num == 1):
                verbose("Successfully matched",2,p.VERBOSITY)
                return star, result[0]
               
            
            elif (results_num > 1):
                delta = delta - delta/2.0
            elif (results_num < 1):
                delta = delta + delta/2.0
                
                if (delta < MIN_DELTA):
                    verbose("Multiple matches!",1,p.VERBOSITY)
                    return  star, result[0]

            i += 1
        verbose("Match was not found",1,p.VERBOSITY)
        return None
    

    #TODO
    def _getStarsFromCatalogue(self,catalogue,coo):
        '''Obtain stars from given catalogue and coordinate ranges'''
        NotImplemented
    