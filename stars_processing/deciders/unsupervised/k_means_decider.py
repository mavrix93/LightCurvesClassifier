'''
Created on Dec 8, 2016

@author: Martin
'''

from sklearn.cluster.k_means_ import KMeans

import numpy as np
from matplotlib import pyplot as plt
from stars_processing.deciders.unsupervised.unsupervised_base import UnsupervisedBase

class KMeansDecider( UnsupervisedBase ):
    '''
    classdocs
    '''


    def __init__(self, treshold = 0.5):
        '''
        Constructor
        '''
        params = { "n_clusters" : 2}
        super( KMeansDecider, self ).__init__( classifier = KMeans, params = params, treshold = treshold )

 