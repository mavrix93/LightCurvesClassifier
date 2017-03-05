'''
Created on Nov 20, 2016

@author: martin
'''

import os

from conf import settings
from db_tier.stars_provider import StarsProvider
from db_tier.local_stars_db.crossmatch_mapper import CrossmatchMapper

file_path = os.path.join(settings.TO_THE_DATA_FOLDER, "crossmatch", "milliquas_ogle", "crossmatch")

def parse_file( file_path ):
    #264823;LMC_SC20_114295;J054646.2-710855

    
    fi =  open( file_path )
    
    queries = []
    for line in fi.readlines(): 
        
        parts = line.split(";")
        
        id = parts[0]
        field1, field2, starid = parts[1].split("_")
        
        target = field1[:3].lower()
        og_q = {"field": field1+"_"+field2, "target":target, "starid" : starid}
        
        queries.append((og_q, {"id" : id, "db_key" : "milliquas" }))
        
        
    return queries

def map_to_db( file_path ):
    
    
    for og_q, m_q in parse_file( file_path ):  
        og_star = StarsProvider().getProvider(obtain_params = og_q, obtain_method = "OgleII").getStarsWithCurves()
        mil_star = StarsProvider().getProvider(obtain_params = m_q, obtain_method = "LocalDbClient").getStarsWithCurves()
    
        lc_path = og_star[0].saveStar( settings.STARS_PATH["crossmatch"])
        mapper = CrossmatchMapper()
        mapper.uploadStar(og_star[0], mil_star[0], lc_path)
    
    
    




if __name__ == "__main__":    
    map_to_db( file_path )