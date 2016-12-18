from matplotlib import pyplot as plt
from sklearn.cluster.k_means_ import KMeans

import numpy as np
from stars_processing.deciders._unsupervised.unsupervised_base import UnsupervisedBase


class KMeansDecider(UnsupervisedBase):
    '''
    classdocs
    '''

    def __init__(self, treshold=0.5):
        '''
        Constructor
        '''
        params = {"n_clusters": 2}
        super(KMeansDecider, self).__init__(
            classifier=KMeans, params=params, treshold=treshold)