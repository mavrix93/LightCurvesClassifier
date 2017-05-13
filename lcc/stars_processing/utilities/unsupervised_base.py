from matplotlib import pyplot as plt

import numpy as np
from lcc.stars_processing.utilities.base_decider import BaseDecider
from lcc.entities.exceptions import QueryInputError


class UnsupervisedBase(BaseDecider):
    '''
    classdocs
    '''

    def __init__(self,  classifier, params, treshold=0.5, **kwargs):
        super(UnsupervisedBase, self).__init__(**kwargs)
        self.classifier = classifier(**params)

    def learn(self, coords):
        coords = [c for c in coords if not np.NaN in c and not None in c]
        if coords:
            self.X = np.array(coords)
            self.classifier.fit(coords)
        else:
            raise QueryInputError("No coordinates for learning")

    def evaluate(self, star_coords):
        return self.classifier.predict(star_coords)
