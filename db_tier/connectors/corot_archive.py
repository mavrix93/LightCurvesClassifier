'''
Created on Dec 7, 2016

@author: Martin Vo
'''

import collections
from entities.star import Star
import os
import requests
import cStringIO
import pyfits

from db_tier.TAP_query import TapClient
from db_tier.base_query import LightCurvesDb
from utils.data_analysis import to_ekvi_PAA, to_PAA
from entities.exceptions import QueryInputError



class CorotBrightArchive( TapClient, LightCurvesDb ):
    '''
    CoRoT connector. TAP query and downloading the light curve fits are ran
    on Vizier catalog.
    '''

    TAP_URL = "http://tapvizier.u-strasbg.fr/TAPVizieR/tap"
    FILES_URL = "http://vizier.u-strasbg.fr/viz-bin/nph-Cat?-plus=-%2b&B/corot/files/"
    
    
    TABLE = "B/corot/Bright_star"
    
    RA = "RAJ2000" # Deg
    DEC = "DEJ2000" # Deg
    NAME = "Star"
    LC_FILE = "FileName"
    
    LC_META = {"xlabel" : "Terrestrial time",
               "xlabel_unit" : "days", 
               "ylabel" : "Flux",
               "ylabel_unit" : "Electrons per second",
               "color" : "N/A",
               "invert_yaxis" : False}
    
    TIME_COL = 0
    MAG_COL = 1
    ERR_COL = 2
    
    ERR_MAG_RATIO = 1.
    
    IDENT_MAP = collections.OrderedDict((("vizier", "Star"), ("corot", "CoRoT")))
    MORE_MAP = collections.OrderedDict((("(B-V)", "b_v_mag"),
                                        ("SpT" , "spectral_type"),
                                        ("Vmag" , "v_mag"),
                                        ("VMAG" , "abs_v_mag"),
                                        ("Teff" , "temp")))

            
    def _getLightCurve(self, file_name, max_bins = 1e3, *args, **kwargs):
        
        response = requests.get( os.path.join(self.FILES_URL, file_name))
        
        _fits = cStringIO.StringIO(response.content)
        fits = pyfits.open( _fits )
        
        time = []
        mag = []
        err = []
        
        for line in fits[1].data:
            time.append(line[ self.TIME_COL ])
            mag.append(line[ self.MAG_COL ])
            err.append(line[ self.ERR_COL ] / self.ERR_MAG_RATIO)
            
        if len(time) > max_bins:
            red_time, red_mag = to_ekvi_PAA(time, mag, bins = max_bins)
            red_time, red_err = to_ekvi_PAA( time, err, bins = max_bins )
            
        fits.close()
        _fits.close()
        return red_time, red_mag, red_err
    
            
class CorotFaintArchive( CorotBrightArchive ):
    TABLE = "B/corot/Faint_star"
    IDENT_MAP = {"corot" : "CoRoT"}
    NAME = "CoRoT"
    
    MORE_MAP = collections.OrderedDict((("SpT" , "spectral_type"),
                                        ("Vmag" , "v_mag"),
                                        ("Rmag" , "r_mag"),
                                        ("Bmag" , "b_mag"),
                                        ("Imag" , "i_mag"),
                                        ("Gmean" , "g_mag")))
    
    LC_META = {"xlabel" : "Terrestrial time",
               "xlabel_unit" : "days", 
               "ylabel" : "Flux",
               "ylabel_unit" : "Electrons per 32 second",
               "color" : "R",
               "invert_yaxis" : False}
    
    TIME_COL = 1
    MAG_COL = 4
    ERR_COL = 5
    
    ERR_MAG_RATIO = 16.