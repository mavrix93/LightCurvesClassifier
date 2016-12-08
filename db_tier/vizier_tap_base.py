'''
Created on Dec 8, 2016

@author: martin
'''

from entities.star import Star
from entities.exceptions import QueryInputError
import requests

class VizierTapBase(object):
    '''
    classdocs
    '''
    
    TAP_URL = "http://tapvizier.u-strasbg.fr/TAPVizieR/tap"
    
    RA = "RAJ2000" 
    DEC = "DEJ2000" 
    
    TIME_COL = 0
    MAG_COL = 1
    ERR_COL = 2
    
    ERR_MAG_RATIO = 1.
    
    # Split at any number of white spaces
    DELIM = None

    def __init__(self, queries):
        '''
        Parameters:
        -----------
            queries : list, dict
                List of dicts - each dict's item is pair "query param" : "value"
        '''
        
        # Case of just one query
        if type(queries) is dict: queries = [queries]
        
        self.queries = queries

    def getStars(self, lc = False, **kwargs):
        '''
        Parameters:
        ----------
            lc : bool
                Star is appended by light curve if True
        
        Returns:
        --------
            List of stars
        '''
        select =  set([self.RA, self.DEC, self.LC_FILE] + self.MORE_MAP.keys())
        
        for val in self.IDENT_MAP.values():
            if isinstance(val, (tuple, list, set) ):
                for it in val:
                    select.add(it)
            else:
                select.add( val )
         
        select = [ s for s in select if s]
        select = list(select)
        
        raw_stars = []
        for que in self.queries:
            if "ra" in que and "dec" in que:
                que[self.RA] = que.pop("ra")
                que[self.DEC] = que.pop("dec")
            
                if "delta" in que:
                    delta = que.pop( "delta" )
                    que[self.RA], que[self.DEC] = self._areaSearch( que[self.RA], que[self.DEC], delta)
            
            conditions = []            
            for key, value in que.iteritems():
                if isinstance(value, (list, tuple) ):
                    if len(value) == 2:
                        conditions.append( (key, value[0], value[1]) )
                    else:
                        raise QueryInputError("Invalid range query")
                else:
                    conditions.append( (key, value))
                    
            query_inp = {"table": self.TABLE,
                          "select": select,
                          "conditions": conditions ,
                          "URL": self.TAP_URL}
            res = self.postQuery(query_inp)
            if res:
                raw_stars.append( res[0] )
        
        return self._createStar( raw_stars, select, lc, **kwargs)
    
    def getStarsWithCurves(self, **kwargs):
        '''
        Returns:
        --------
            List of stars with their light curves
        '''
        return self.getStars( lc = True, **kwargs )
        
    def _createStar(self, data, keys, lc_opt, **kwargs):
        
        stars = []
        for raw_star in data:
            
            ident = {}
            for key, value in self.IDENT_MAP.iteritems():
                if isinstance(value, (list, tuple) ):
                    db_ident = {}
                    for ide in value:
                        db_ident[ide] = raw_star[ keys.index(ide) ]
                
                name = self.NAME.format( **db_ident )
                
                if not db_ident:
                    db_ident = None 
                
                ident[key] = {"name" : name, "identifier" : db_ident}
            
            more = {}
            for key, value in self.MORE_MAP.iteritems():
                more_item = raw_star[ keys.index(key)]
                more[value] = more_item
            raw_star_dict = dict(zip(keys, raw_star))
            
            star = Star(name = self.NAME.format(**raw_star_dict),
                        ra = raw_star_dict[self.RA], 
                        dec = raw_star_dict[self.DEC],
                        ident = ident,
                        more = more)
            
            if lc_opt:
                star.putLightCurve( self._getLightCurve( star = star, **kwargs  ), meta = self.LC_META )
            
            stars.append(star)
            
        return stars
    
    
    def _getLightCurve(self, star, do_per = False, period_key = "period", *args, **kwargs):
        if do_per:
            period = star.more.get( period_key , None)
            if period:
                self.LC_META = {"xlabel" : "Period",
                               "xlabel_unit" : "phase"}
        else:
            period = 0
        
        url = self.LC_URL.format( macho_name = star.name, period = period )
          
        response = requests.get( url )
        time = []
        mag = []
        err = []
        for line in response.iter_lines():
            line = line.strip()
            if not line.startswith( (" ", "#") ):
                parts = line.split( self.DELIM )
                if len(parts) == 3:
                    time.append( float(parts[ self.TIME_COL ]))
                    mag.append( float(parts[ self.MAG_COL ]))
                    err.append( float(parts[ self.ERR_COL ]) / self.ERR_MAG_RATIO)
            
        return time, mag, err
            
    
        