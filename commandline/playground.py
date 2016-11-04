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
from conf.package_reader import PackageReader

ra = RightAscension(5.549147, "hours")
dec = Declination( -70.55792)

query =  {"ra" : ra.degrees, "dec": dec.degrees, "delta":20,"target":"lmc"}
stars = StarsProvider().getProvider(obtain_method = "OgleII", **query).getStars()

print stars[0].more

"""query = {"db_origin" : "ogle"}

stars = StarsProvider().getProvider(obtain_method = "LocalDbClient", **query).getStarsWithCurves()

fi = ColorIndexFilter( GaussianNBDec(), colors = ["b_mag", "v_mag"])

fi.learn(stars[:3], stars[3:])

fi_man = FilteringManager ( stars )
fi_man.loadFilter( fi )
print fi_man.performFiltering()

fi.decider.plotProbabSpace()"""
        
