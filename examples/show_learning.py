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
from stars_processing.deciders.supervised_deciders import QDADec, GaussianNBDec,\
    GMMBayesDec
from stars_processing.deciders.neuron_decider import NeuronDecider


def show_learning(quasars, stars, deciders = []):
    for decider in deciders:
        comp_filt = ComparingFilter( cf, quasars[:N/3], filters_params = filtering_params, decider = decider() )
        comp_filt.learn(quasars[N/3:2*N/3], stars[N/2:N])
        
if __name__ == "__main__":    
      
    N = 40
    
    files_prov = StarsProvider().getProvider(path= settings.STARS_PATH["quasars"],
                                             files_limit=N,
                                             obtain_method="FileManager",
                                             star_class="quasar")
    quasars =  files_prov.getStarsWithCurves()
    
    files_prov2 = StarsProvider().getProvider(path=settings.STARS_PATH["stars"],
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
    deciders = [NeuronDecider, QDADec, GaussianNBDec, GMMBayesDec]
    show_learning(quasars, stars, deciders)

