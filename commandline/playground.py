from db_tier.stars_provider import StarsProvider

from stars_processing.filtering_manager import FilteringManager 
from stars_processing.filters_impl.compare import ComparingFilter
from stars_processing.filters_impl.word_filters  import  HistShapeFilter,\
    VariogramShapeFilter
from stars_processing.filters_impl.abbe_value import AbbeValueFilter
from stars_processing.filters_impl.color_index import ColorIndexFilter

from utils.output_process_modules import saveIntoFile
from utils.stars import plotStarsPicture

from entities.right_ascension import RightAscension
from entities.declination import Declination
from conf import settings

from stars_processing.deciders.base_decider import BaseDesider
from stars_processing.deciders.distance_desider import DistanceDesider
from astroML.classification.gmm_bayes import GMMBayes

import numpy as np
from sklearn.lda import LDA
import sys
from sklearn.naive_bayes import BernoulliNB

from matplotlib import pyplot as plt
from stars_processing.deciders.supervised_deciders import QDADec, GaussianNBDec


        

N = 20

#Path to the folder with quasar light curves
qso_path = settings.STARS_PATH["quasars"]
files_prov = StarsProvider().getProvider(path=qso_path,
                                         files_limit=N,
                                         obtain_method="FileManager",
                                         star_class="quasar")
quasars =  files_prov.getStarsWithCurves()
stars_path = settings.STARS_PATH["stars"]
files_prov2 = StarsProvider().getProvider(path=stars_path,
                                         files_limit=N,
                                         obtain_method="FileManager",
                                         star_class="star")
stars =  files_prov2.getStarsWithCurves()
cf = []
cf.append(HistShapeFilter)  
cf.append(VariogramShapeFilter)
filtering_params = { "hist_days_per_bin": 97,
                    "vario_days_per_bin": 9,
                    "vario_alphabet_size" : 17,
                    "hist_alphabet_size" : 7
                    }

comp_filt = ComparingFilter( cf, quasars[:N/3], filters_params = filtering_params, decider= GaussianNBDec(0.5))


comp_filt.learn(quasars[N/3:2*N/3], stars[N/2:N])



print comp_filt.getStatistic( quasars[N/3:2*N/3], stars[N/2:N] )


filteringManager = FilteringManager(quasars[N/3:2*N/3])
filteringManager.loadFilter(comp_filt)

print len(filteringManager.performFiltering()), "/", len(quasars[N/3:2*N/3])

filteringManager = FilteringManager(stars[N/2:N])
filteringManager.loadFilter(comp_filt)

print len(filteringManager.performFiltering()), "/", len(stars[N/2:N])
#####


"""qso_coords1 = comp_filt.getSpaceCoordinates(quasars[N/3:2*N/3])
qso_coords2 = comp_filt.getSpaceCoordinates(quasars[2*N/3:N])
stars_coords = comp_filt.getSpaceCoordinates(stars[N/2:N])

#plt.plot(qso_coords1, "bo")
#plt.plot(stars_coords, "ro")
#plt.show()

decider = GaussianNBDec()
#decider = DistanceDesider(17)

decider.learn(qso_coords1, stars_coords)

print decider.getStatistic(qso_coords1, stars_coords)
decider.plotProbabSpace()"""

"""
x = []
y = []
for prob in np.linspace(0.1, 0.9, 50):
    decider.treshold = prob
    stat = decider.getStatistic(qso_coords1, stars_coords)
    x.append(stat["false_positive_rate"])
    y.append(stat["true_positive_rate"])
print x, y    
plt.plot(x,y,"bo")
plt.show()"""

sys.exit()


obtain_params = {
     "ra":RightAscension(5.56*15),
         "dec":Declination(-69.99),
         "delta":3,
         "target":"lmc"
         }

#------    Get qusars with light curves    -----------

files_prov = StarsProvider().getProvider(path=qso_path,
                                         files_limit=15,
                                         obtain_method="FileManager",
                                         star_class="quasar")
quasars =  files_prov.getStarsWithCurves()


#----  Download  stars from OGLE II database    ------

ogle_prov = StarsProvider().getProvider(obtain_method="OgleII",
                                        obtain_params=obtain_params)
stars = ogle_prov.getStarsWithCurves()

#Filter which compares two stars according to given subfilters
cf = []
cf.append(HistShapeFilter)  
cf.append(VariogramShapeFilter)

#Load comparative sub filters, template stars 
#of quasars and decision function
filtering_params = { "hist_days_per_bin": 50,
                    "vario_days_per_bin": 50,
                    "vario_alphabet_size" : 5,
                    "hist_alphabet_size" : 5
                    }
comp_filt = ComparingFilter( cf, quasars,decider() , filters_params = filtering_params)



#-------------   Perform filtering    ----------------
#Load inspected stars and filters
filteringManager = FilteringManager(stars)
filteringManager.loadFilter(comp_filt)

#Perform filtering and return stars passed thru filter
result_stars = filteringManager.performFiltering()    


#-----   Plot and save stars passed thru filter   ----

print result_stars
#Plot stars
plotStarsPicture(result_stars)
