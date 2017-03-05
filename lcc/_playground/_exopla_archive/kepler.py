'''
Created on Nov 24, 2016

@author: martin
'''
from db_tier.connectors._exopla_archive.base import BaseArchive
from db_tier.base_query import LightCurvesDb

class KeplerArchive( BaseArchive, LightCurvesDb ):
    
    """
    For catalog documentation see http://exoplanetarchive.ipac.caltech.edu/docs/API_keplerstellar_columns.html
    
    """
    
    TABLE = "keplerstellar"
    NAME =  "kepid"
    IDENT = NAME    
    RA, RA_UNIT = "ra", "degrees"
    DEC, DEC_UNIT = "dec", "degrees"
    IDENT = "kepid"
    MORE = ( "tm_designation", "kepmag" )    
    
    LC_TABLE = "keplertimeseries"
    LC_IDENT = "kepid"
    TIME = "start_time"
    MAG = "npts"
  