'''
Created on Nov 3, 2016

@author: martin
'''
from db_tier.local_stars_db.stars_mapper import StarsMapper
from db_tier.local_stars_db.models import Stars


def count_stars( db_key = "local"):
    session = StarsMapper( db_key ).session
    
    print session.query( Stars ).count()

def show_all_stars( db_key = "local"):
    delim = "\t"
    
    session = StarsMapper( db_key ).session
    
    all_stars = session.query( Stars ).all()
    
    if all_stars:
        rows = ""
        for i,star in enumerate(all_stars):
            d =  star.__dict__
            d["uploaded"] = d["uploaded"].isoformat()
            if d["crossmatch_id"]: d["crossmatch_id"] = d["crossmatch_id"].id
            del d["_sa_instance_state"]
            
            if i < 1:
                keys = d.keys()
                header = ""
                for k in keys:
                    header += "%s%s" % (k, delim)
            
            row = ""
            for k in keys:
                row += "%s\t" % d[k]
            rows += "%s\n" % row
        
        separ = "-" * (len(header) + (len(keys)-2)* 4)
        print "%s\n%s\n%s" % (header, separ,rows)
        
    print len(all_stars)
        
 
#count_stars( "ogleII" )       
show_all_stars( "ogleII" )