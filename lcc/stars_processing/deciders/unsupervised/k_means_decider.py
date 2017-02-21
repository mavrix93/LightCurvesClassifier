from matplotlib import pyplot as plt
from sklearn.cluster.k_means_ import KMeans

import numpy as np
from lcc.stars_processing.utilities.unsupervised_base import UnsupervisedBase


class KMeansDecider(UnsupervisedBase):
    '''
    classdocs
    '''

    def __init__(self, treshold=0.5, n_clusters=3):
        '''
        Constructor
        '''
        params = {"n_clusters": n_clusters}
        super(KMeansDecider, self).__init__(
            classifier=KMeans, params=params, treshold=treshold)
