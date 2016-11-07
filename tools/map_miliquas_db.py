'''
Created on Nov 6, 2016

@author: martin


There are methods for dealing with miliquas_db
'''
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from conf import settings
from db_tier.local_stars_db.stars_mapper import StarsMapper


file_path = os.path.join(settings.TO_THE_DATA_FOLDER, "other", "miliquas_db", "miliquas.txt")

def upload_to_db( file_path ):
    
    NUM_ROWS = 1422219  
    BY_BYTE_KEY = [0, 11, 23, 50, 53, 55, 60, 65, 69, 71, 73, 80]
    SAVE_LIM = 3e5
    MAX_ERRORS = 100
    
    data = open( file_path )
    
    values = []
   
    line = "line"
    from_id = 0
    err_counter = 0
    k = 0
    save_counter = 0
    while line != "":
        try:
            print k, "/", NUM_ROWS
            line = data.readline()
            
            if k > from_id:
                splt_line =  [ line[i:j].strip() for i,j in zip(BY_BYTE_KEY, BY_BYTE_KEY[1:])]
                
                # Verify parsing
                try:
                    ra = float( splt_line[0] )            
                    dec = float( splt_line[1] )
                    r_mag = float( splt_line[5] )
                    b_mag = float( splt_line[6] )
                except ValueError:
                    print splt_line
                    print line
                    raise Exception("Parse error in line %i " % k)
                
                if not splt_line[10]:
                    z = None
                else:
                    z = float(splt_line[10])
                    
                values.append({"ra" : ra,
                             "dec" : dec,
                             "name" : splt_line[2],
                             "star_class" : splt_line[3],
                             "r_mag" : r_mag,
                             "b_mag" : b_mag,
                             "redshift" : z})
        except:
            if err_counter > MAX_ERRORS:
                raise
            err_counter += 1
            print "hups"
        
        if save_counter > SAVE_LIM:
            mapper = StarsMapper( db_key = "milliquas")
            mapper.uploadViaKeys(values)
            values = []
            save_counter = 0
            
        k += 1
        save_counter += 1

    mapper = StarsMapper( db_key = "milliquas")
    mapper.uploadViaKeys(values)
    print "Done. Number of errors: %i" % err_counter-1
    data.close()
    
        
        
        
if __name__ == "__main__":    
    #upload_to_db( file_path )
    pass
