'''
Created on Jul 20, 2016

@author: martin
'''
from sklearn.grid_search import GridSearchCV
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.cross_validation import train_test_split
from db_tier.stars_provider import StarsProvider
from conf.glo import OGLE_QSO_PATH, STARS_PATH
from stars_processing.filtering_manager import FilteringManager
from stars_processing.filters_impl.abbe_value import AbbeValueFilter
import numpy as np
from utils.stars import count_types
from conf.params_estim import ParamsEstimation
from entities.right_ascension import RightAscension
from entities.declination import Declination


obtain_params = {
     "ra":RightAscension(5.56*15),
         "dec":Declination(-69.99),
         "delta":3,
         "target":"lmc"
         }

ogle_prov = StarsProvider().getProvider(obtain_method="ogle",
                                        obtain_params=obtain_params)
stars = ogle_prov.getStars()

print stars[0]

'''
files_prov = StarsProvider().getProvider(path=OGLE_QSO_PATH,
                                         files_limit=10,
                                         obtain_method="file",
                                         star_class="qso")
quasars =  files_prov.getStarsWithCurves()   

files_prov2 = StarsProvider().getProvider(path=STARS_PATH,
                                         files_limit=10,
                                         obtain_method="file",
                                         star_class="star")
stars =  files_prov2.getStarsWithCurves() 


filt = AbbeValueFilter


#find_symbolic_space_params(stars,quasars,{"params":[{"abbe_lim": 0.37},{"abbe_lim": 0.4}]},Estim(),filt)

es = ParamsEstimation(quasars,stars,filt, [{"abbe_lim": 0.37},{"abbe_lim": 0.4}])
es.fit()'''