'''
Created on Dec 7, 2016

@author: Martin Vo
'''

import collections
import requests
import numpy as np

from db_tier.TAP_query import TapClient
from db_tier.base_query import LightCurvesDb

class AsasArchive( TapClient, LightCurvesDb):
    '''
    classdocs
    '''
    TAP_URL = "http://tapvizier.u-strasbg.fr/TAPVizieR/tap"
    LC_URL = "http://cdsarc.u-strasbg.fr/viz-bin/nph-Plot/Vgraph/txt?II%2f264%2f.%2f{asas_id}&P=0"
    
    
    TABLE = "II/264/asas3"
    
    RA = "_RA" # Deg
    DEC = "_DE" # Deg
    NAME = "ASAS"
    LC_FILE = NAME
    
    LC_META = {"color" : "V"}
    
    TIME_COL = 0
    MAG_COL = 1
    ERR_COL = 2
    
    ERR_MAG_RATIO = 1.
    DELIM = " "
    
    IDENT_MAP = {"asas" :  "ASAS"}
    MORE_MAP = collections.OrderedDict((("Per", "period"),
                                        ("Class" , "var_type"),
                                        ("Jmag" , "j_mag"),
                                        ("Kmag" , "k_mag"),
                                        ("Hmag" , "h_mag")))

    def _getLightCurve(self, file_name, star, do_per = False):
        url = self.LC_URL.format(asas_id = file_name )
        
        if do_per:    
            per = star.more.get( "period", None )  
            if per:      
                url = url[:-1] + "%f" % per
                self.LC_META = {"xlabel" : "Period",
                           "xlabel_unit" : "phase"}
            
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
        