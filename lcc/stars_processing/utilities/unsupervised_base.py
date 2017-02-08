from matplotlib import pyplot as plt

import numpy as np
from lcc.stars_processing.utilities.base_decider import BaseDecider


class UnsupervisedBase(BaseDecider):
    '''
    classdocs
    '''

    def __init__(self,  classifier, params, treshold=0.5, **kwargs):
        super(UnsupervisedBase, self).__init__(**kwargs)
        self.classifier = classifier(**params)

    def learn(self, coords):
        self.X = np.array(coords)
        self.classifier.fit(coords)

    def evaluate(self, star_coords):
        return self.classifier.predict(star_coords)
