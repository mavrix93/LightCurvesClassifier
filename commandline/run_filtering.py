from db_tier.stars_provider import StarsProvider

from stars_processing.filtering_manager import FilteringManager 
from stars_processing.filters_impl.compare import ComparingFilter
from stars_processing.filters_impl.word_filters  import  HistShapeFilter,\
    VariogramShapeFilter
from stars_processing.filters_impl.abbe_value import AbbeValueFilter
from stars_processing.filters_impl.color_index import ColorIndexFilter

from utils.output_process_modules import saveIntoFile
from utils.stars import plotStarsPicture

from conf.settings import *
from conf.filters_params.qso import *
from entities.right_ascension import RightAscension
from entities.declination import Declination
from conf import settings

#
#Path to the folder with quasar light curves
qso_path = settings.STARS_PATH["ogle"]

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
cf.append(HistShapeFilter(days_per_bin=HIST_DAYS_PER_BIN,
                          alphabet_size=HIST_ALPHABET_SIZE))  
  
cf.append(VariogramShapeFilter(days_per_bin=VARIO_DAYS_PER_BIN,
                               alphabet_size=VARIO_ALPHABET_SIZE))


#Decision function which decides whether a star
#will pass thru filtering (according its histogram
#and variogram distance from template
def dec_func_t(distances):
    hist_dist,vario_dist = distances
    return VAR_HIST_A * hist_dist + VAR_HIST_B > vario_dist

#Load comparative sub filters, template stars 
#of quasars and decision function
comp_filt = ComparingFilter(cf, quasars, dec_func_t,
                            search_opt="closest")

#Abbe value limit filter
abbe_filter = AbbeValueFilter(abbe_lim=ABBE_LIM)


#Color index filter with its decision function
def dec_func_c(bv,vi): return bv >= BV_MIN and vi >= VI_MIN

color_filter = ColorIndexFilter(dec_func_c)


#-------------   Perform filtering    ----------------
#Load inspected stars and filters
filteringManager = FilteringManager(stars)
filteringManager.loadFilter(comp_filt)
filteringManager.loadFilter(abbe_filter)
filteringManager.loadFilter(color_filter)

#Perform filtering and return stars passed thru filter
result_stars = filteringManager.performFiltering()    


#-----   Plot and save stars passed thru filter   ----

print result_stars
#Plot stars
plotStarsPicture(result_stars)
