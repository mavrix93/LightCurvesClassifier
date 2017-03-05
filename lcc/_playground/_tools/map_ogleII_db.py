'''
Created on Nov 6, 2016

@author: martin
'''
from stars_processing.systematic_search.stars_searcher import StarsSearcher


def ogle_to_local_db():
    
    queries = get_queries(1,100, 1, "lmc")
    
    searcher = StarsSearcher( filters_list =  [], OBTH_METHOD = "OgleII", db_key = "ogleII")
    
    searcher.queryStars( queries )
    
    
def get_queries( from_id, to_id, field_num, target ):
    queries = []
    
    for starid in range(from_id, to_id):
        queries.append( {"field_num" : field_num, "starid" : starid, "target": target} )
        
    return queries
    
    


if __name__ == "__main__": 
    ogle_to_local_db()