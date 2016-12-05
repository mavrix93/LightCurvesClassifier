'''
Created on Nov 3, 2016

@author: Martin Vo
'''
from db_tier.local_stars_db.stars_mapper import StarsMapper
from db_tier.local_stars_db.models import Stars


def show_all_stars( db_key = "local"):
    """
    This method shows all stars in a database
    
    Parameters:
    -----------
        db_key : str
            Key for a database specified in settings
            
    Example:
    --------
        show_all_stars( "ogleII" )
    
    """
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
        
        
      
