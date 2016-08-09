'''
Created on Apr 2, 2016

@author: Martin Vo
'''

#Relative imports fix
import sys, os
from conf.glo import TO_THE_DATA_FOLDER
from conf.filters_params.qso import *
myPath = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, myPath + '/../')

from db_tier.stars_provider import StarsProvider
from utils.clustering import getClusters



if __name__ == '__main__':
    save_plots = False
    
    path1 = TO_THE_DATA_FOLDER+"light_curves/qso_eyer"
    path2 = TO_THE_DATA_FOLDER+"light_curves/quasars"
    path3 = TO_THE_DATA_FOLDER+"light_curves/some_stars"
    path5 = TO_THE_DATA_FOLDER+"light_curves/be_eyer"
    path6 = TO_THE_DATA_FOLDER+"light_curves/mqs_quasars"
    path7 = TO_THE_DATA_FOLDER+"light_curves/dpv"
    path8 = TO_THE_DATA_FOLDER+"light_curves/rr_lyr"
    path9 = TO_THE_DATA_FOLDER+"light_curves/cepheids"
    
    stars = []
    qsos = []
    a = 2
    qsos += StarsProvider().getProvider(path=path2,obtain_method="file",star_class="OGLE QSO").getStarsWithCurves()[:a]
    qsos +=  StarsProvider().getProvider(path=path1,obtain_method="file",star_class="qso_eyer").getStarsWithCurves()[:a]
    stars +=  StarsProvider().getProvider(path=path3,obtain_method="file",star_class="star").getStarsWithCurves()[:a]    
    stars +=  StarsProvider().getProvider(path=path5,obtain_method="file",star_class="be_eyer").getStarsWithCurves()[:a]
    qsos +=  StarsProvider().getProvider(path=path6,obtain_method="file",star_class="MACHO QSO").getStarsWithCurves()[:a]
    stars +=  StarsProvider().getProvider(path=path7,obtain_method="file",star_class="dpv").getStarsWithCurves()[:a]
    stars +=  StarsProvider().getProvider(path=path8,obtain_method="file",star_class="RR Lyr").getStarsWithCurves()[:a]
    stars +=  StarsProvider().getProvider(path=path9,obtain_method="file",star_class="cep").getStarsWithCurves()[:a]
    
    
    clusters = getClusters(stars+qsos,VARIO_ALPHABET_SIZE, HIST_DAYS_PER_BIN, HIST_ALPHABET_SIZE, VARIO_DAYS_PER_BIN, "ogle" )
    
    #getVarioHistSpace(qsos,stars,hist_days_per_bin,hist_alphabet_size,vario_days_per_bin,vario_alphabet_size)
    
    
