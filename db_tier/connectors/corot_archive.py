'''
Created on Dec 7, 2016

@author: Martin Vo
'''

import collections
import os
import requests
import cStringIO
import pyfits

from db_tier.base_query import LightCurvesDb
from utils.data_analysis import to_ekvi_PAA
from db_tier.vizier_tap_base import VizierTapBase



class CorotBrightArchive( VizierTapBase, LightCurvesDb ):
    '''
    CoRoT connector. TAP query and downloading the light curve fits are ran
    on Vizier catalog.
    
    EXAMPLES:
    ---------
        queries = [ {"ra": 102.707, "dec" : -0.54089, "delta" : 10},
                    {"CoRot" : 116}]       
        client = StarsProvider().getProvider( obtain_method = "CorotBrightArchive", obtain_params = queries)
        stars = client.getStarsWithCurves(max_bins = 10000 )
            
    '''

    LC_URL = "http://vizier.u-strasbg.fr/viz-bin/nph-Cat?-plus=-%2b&B/corot/files/"
    TABLE = "B/corot/Bright_star"
  
    NAME = "{Star}"
    LC_FILE = "FileName"
    
    LC_META = {"xlabel" : "Terrestrial time",
               "xlabel_unit" : "days", 
               "ylabel" : "Flux",
               "ylabel_unit" : "Electrons per second",
               "color" : "N/A",
               "invert_yaxis" : False}
 
    IDENT_MAP = collections.OrderedDict((("VizierDb", "Star"), ("CorotBrightArchive", "CoRoT")))
    MORE_MAP = collections.OrderedDict((("(B-V)", "b_v_mag"),
                                        ("SpT" , "spectral_type"),
                                        ("Vmag" , "v_mag"),
                                        ("VMAG" , "abs_v_mag"),
                                        ("Teff" , "temp")))

            
    def _getLightCurve(self, file_name, max_bins = 1e3, *args, **kwargs):
        """
        Obtain light curve 
        
        Parameters:
        -----------
            file_name : str
                Path to the light curve file from root url
                 
            max_bins : int
                Maximal number of dimension of the light curve
                
        Returns:
        --------
            Tuple of times, mags, errors lists
        """
        
        response = requests.get( os.path.join(self.LC_URL, file_name))

        
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
    """
    Corot archive of faint stars
    
        
    EXAMPLES:
    ---------
        queries = [ { "Corot" : "102706554"},
                    {"ra": 100.94235, "dec" : -00.89651, "delta" : 10}]        
        client = StarsProvider().getProvider( obtain_method = "CorotFaintArchive", obtain_params = queries)
        stars = client.getStarsWithCurves(max_bins = 10000 )    
    """
    
    TABLE = "B/corot/Faint_star"
    IDENT_MAP = {"CorotFaintArchive" : "CoRoT"}
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