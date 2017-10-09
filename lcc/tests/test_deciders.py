import numpy as np

import lcc.stars_processing.deciders.supervised_deciders as dec
from lcc.stars_processing.deciders.neuron_decider import NeuronDecider


def set_up():
    deciders = [dec.AdaBoostDec(), dec.ExtraTreesDec(), dec.GaussianNBDec(), dec.LDADec(), dec.QDADec(),
                         dec.RandomForestDec(), dec.SVCDec(), dec.TreeDec(),
                NeuronDecider(hidden_neurons=10, maxEpochs=500)]

    return np.random.random_sample((100, 7)), np.random.random_sample((100, 7)) + 1, deciders


def test():
    search_sample1, others_sample1, deciders = set_up()

    eee = {}
    for dec in deciders:
        dec.learn(search_sample1, others_sample1)
        p1 = dec.evaluate(search_sample1)
        p2 = dec.evaluate(others_sample1)
        eee[dec.__class__.__name__] = np.mean(p1) - np.mean(p2)
        assert np.mean(p1) - np.mean(p2) > 0.95

