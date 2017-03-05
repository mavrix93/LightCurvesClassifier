
# coding: utf-8

# In[9]:

import sys
import os

sys.path.append("..")

import numpy as np


# In[8]:

from db_tier.stars_provider import StarsProvider
from db_tier.local_stars_db.models_crossmatch_milliquas_ogle import StarsMO


# In[3]:

un_ogle_connector = StarsProvider().getProvider(obtain_method = "OgleII")
un_loc_connector = StarsProvider().getProvider(obtain_method = "LocalDbClient")


# In[29]:

#ost = get_ogle_by_coo( 5.549147*15, -70.55792,"lmc", 10)
#ost.ident["ogle"]["name"]


# In[40]:

def get_milliquas_by_id( id ):
    obtain_params = {"db_key" : "milliquas", "id": id}
    loc_connector = un_loc_connector(obtain_params)
    stars = loc_connector.getStarsWithCurves()
    if stars:
        return stars[0]
    return None

def get_ogle_by_coo( ra, dec, target, delta ):
    obtain_params = {"db_key" : "OgleII", "ra": ra, "dec": dec, "delta": delta, "target" : target}
    ogle_connector = un_ogle_connector(obtain_params)
    stars = ogle_connector.getStars()
    if stars:
        if len(stars) > 1:
            print "multiple stars"
            print [star.name for star in stars]
        return stars[0]
    return None

def crossmatch( id, delta = 10 ):
    TARGETS = ["lmc", "smc", "bul"]
    for target in TARGETS:
        milliquas_star = get_milliquas_by_id( id )
        ra = milliquas_star.ra.degrees
        dec = milliquas_star.dec.degrees
        return get_ogle_by_coo( ra, dec, target, delta ), milliquas_star
    
    return None
    


# In[38]:

def crossmatch_all(from_n, to_n):
    DELTA = 10
    # 6000
    found = 0
    for i in range(from_n, to_n):
        st, m_st = crossmatch( i , DELTA )
        if st:
            print st.name
            found += 1
            #id,ogle_name, milliquas_name
            data = [[i,st.ident["ogle"]["name"], m_st.ident["milliquas"]["name"] ]]
            with open("crossmatch",'a') as f_handle:
                np.savetxt(f_handle,data,fmt='%s', delimiter=";")

        print i, found
        


# In[39]:

crossmatch_all(6000, 1500000)

