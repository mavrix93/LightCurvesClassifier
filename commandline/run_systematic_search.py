'''
Created on May 11, 2016

@author: Martin Vo
'''
#Relative imports fix
import sys, os
from conf.settings import MQS_QSO_PATH, OGLE_QSO_PATH
myPath = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, myPath + '/../')
from conf.filters_params.qso import *

from stars_processing.filters_impl.color_index import ColorIndexFilter
from stars_processing.filters_impl.curve_density import CurveDensityFilter
from stars_processing.filters_impl.word_filters import HistShapeFilter,\
    VariogramShapeFilter
from stars_processing.filters_impl.compare import ComparingFilter
from stars_processing.filters_impl.abbe_value import AbbeValueFilter



from db_tier.stars_provider import StarsProvider
from stars_processing.systematic_search.ogle_systematic_search import OgleSystematicSearch

def search_qso_ogle():
    #aa = int(sys.argv[1])
    #bb = int(sys.argv[2])
    
    aa = 1
    bb = 1


    quasars =  StarsProvider().getProvider(path=MQS_QSO_PATH,obtain_method="file",star_class="qso").getStarsWithCurves()  
    quasars +=  StarsProvider().getProvider(path=OGLE_QSO_PATH,obtain_method="file",star_class="qso").getStarsWithCurves()  
    def dec_func_t(distances):
        hist_dist,vario_dist = distances
        a = VAR_HIST_A
        b = VAR_HIST_B-3
        return a * hist_dist + b > vario_dist
    
    filt_params = {"treshold":dec_func_t,
                    "hist_days_per_bin":HIST_DAYS_PER_BIN,
                    "hist_alphabet_size":HIST_ALPHABET_SIZE,
                    "vario_days_per_bin":VARIO_DAYS_PER_BIN,
                    "vario_alphabet_size":VARIO_ALPHABET_SIZE,
                    "abbe":ABBE_LIM}
    

            
    #Load histogram and variogram shape filter
    cf = []
    cf.append(HistShapeFilter(filt_params["hist_days_per_bin"], filt_params["hist_alphabet_size"]))
    cf.append(VariogramShapeFilter(filt_params["vario_days_per_bin"], filt_params["vario_alphabet_size"]))    
    comp_filt = ComparingFilter(cf, quasars[:1], filt_params["treshold"], search_opt="passing")
    
    abbe_filt = AbbeValueFilter(filt_params["abbe"])
    
    curve_dens_filt = CurveDensityFilter(0.23)
            
    #Color index filter with its decision function
    def dec_func_c(bv,vi): return bv <= BV_MIN and vi <= VI_MIN
    
    color_filt = ColorIndexFilter(dec_func_c,pass_not_found=True)
     

    filters_list = [color_filt,curve_dens_filt,abbe_filt,comp_filt]         
     
    searcher = OgleSystematicSearch(filters_list,SAVE_LIM=5,save_path=MATCHED_QSO_PATH) 
    searcher.systematic_ogle_search(target="lmc",field_num=aa,start_starid=bb) 
    




if __name__ == '__main__':
    search_qso_ogle()