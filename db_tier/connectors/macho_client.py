'''
Created on Jan 5, 2016

@author: Martin Vo
'''
from db_tier.base_query import LightCurvesDb
import collections
from db_tier.vizier_tap_base import VizierTapBase


class MachoDb(VizierTapBase, LightCurvesDb):
    '''
    Client for Macho database  
    
    EXAMPLES:
    ---------
        queries = [ {"ra" : 0.4797, "dec": -67.1290, "delta" : 10},
                    {"Field" : 1 , "Tile": 3441, "Seqn" : 25}]
        client = StarsProvider().getProvider( obtain_method = "MachoDb", obtain_params = queries)
        stars = client.getStarsWithCurves()
        
    '''
   
    TABLE = "II/247/machovar"
    LC_URL = "http://cdsarc.u-strasbg.fr/viz-bin/nph-Plot/w/Vgraph/txt?II%2f247%2f.%2f{macho_name}&F=b%2br&P={period}&-x&0&1&-y&-&-&-&--bitmap-size&600x400"

    NAME = "{Field}.{Tile}.{Seqn}"
    LC_FILE = ""
    
    LC_META = {"color" : "V"}
    
    IDENT_MAP = {"MachoDb" :  ("Field", "Tile", "Seqn") }
    MORE_MAP = collections.OrderedDict((("Class" , "var_type"),
                                        ("Vmag" , "v_mag"),
                                        ("Rmag" , "r_mag"),
                                        ("rPer" , "period_r"),
                                        ("bPer" , "period_b")))



