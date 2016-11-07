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
import os
from db_tier.local_stars_db.stars_mapper import StarsMapper
from db_tier.local_stars_db.models import Stars
import re
from db_tier.connectors.local_db_client import LocalDbClient
from stars_processing.systematic_search.status_resolver import StatusResolver
from utils.helpers import get_combinations


target = ["lmc", "smc"]

starid = [i+1 for i in range(1000)]
field = [i+1 for i in range(13)]


q = get_combinations(["target", "starid", "field"], target, starid, field)

StatusResolver.save_query(q)
