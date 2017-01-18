import json
import random

import numpy as np

from entities.exceptions import QueryInputError
from stars_processing.stars_filter import StarsFilter


class ParamsEstimation(object):
    '''
    Attributes
    ----------
    searched : list of `Star` objects
        Searched stars

    others : list of `Star` objects
        Contamination stars

    descriptors : list, iterable
        Unconstructed descriptor objects

    deciders : list, iterable
        Decider instances

    tuned_params : list of dicts
        List of parameters to tune

    static_params : dict
            Constant values for descriptors and deciders
    '''

    def __init__(self, searched, others, descriptors, deciders, tuned_params,
                 split_ratio=0.75, static_params={}, **kwargs):
        '''
        Parameters
        ----------
        searched : list
            Searched stars

        others : list
            Contamination stars

        descriptors : list, iterable
            Unconstructed descriptors object

        deciders : list, iterable
            Unconstructed decider instances

        tuned_params : list of dicts
            List of parameters to tune

            EXAMPLE
            [{'AbbeValue' : {'bins' : 10, ..}, 'NeuronDecider' : {'hidden_layers': 2, ..}, .. ]
        split_ratio : float
            Percentage number of train sample

        static_params : dict
            Constant values for descriptors and deciders
        '''

        # TODO: Custom split ratio

        random.shuffle(searched)
        random.shuffle(others)

        self.searched_train = searched[:int(len(searched) * split_ratio)]
        self.searched_test = searched[int(len(searched) * split_ratio):]
        self.others_train = others[:int(len(others) * split_ratio)]
        self.others_test = others[int(len(others) * split_ratio):]
        self.descriptors = descriptors
        self.tuned_params = tuned_params
        self.static_params = static_params

    def fit(self, score_func):
        """
        Find best combination of filter parameters

        Parameters
        ----------
        score_func : function
            Function which takes dict of statistical values and return
            a score

        Returns
        -------
        object
            Filter created from the best parameters

        dict
            Statistical values of the best combination

        dict
            Input parameters of the best combination
        """
        scores = []
        filters = []
        stats_list = []
        i = 0
        for tun_param in progressbar(self.tuned_params,
                                     "Estimating combinations: "):
            i += 1

            stars_filter, stats = self.evaluate(tun_param)
            stats_list.append(stats)
            filters.append(stars_filter)
            scores.append(score_func(stats))

        best_id = np.argmax()

        print "*" * 30
        try:
            print "Best params:\n%s\n" % json.dumps(self.tuned_params[best_id],
                                                    indent=4)
        except:
            pass
        print "Statistic:\n%s\n" % json.dumps(stats_list[best_id], indent=4)

        return filters[best_id], stats_list[best_id], self.tuned_params[best_id]

    def evaluate(self, combination):
        """
        Parameters
        ----------
        combination : dict
            Dictionary of dictionaries - one per a descriptor.

            EXAMPLE
                {'AbbeValue': {'bin':10, .. }, .. }

        Returns
        -------
        tuple
            Stars filter, statistical values
        """

        deciders = []
        for decider in self.deciders:
            params = self.static_params.get(decider.__name__)
            if isinstance(params, dict):
                deciders.append(decider(**params))

            elif isinstance(params, (list, tuple)):
                deciders.append(decider(*params))

            elif params is None:
                deciders.append(decider())

            else:
                deciders.append(decider(params))

        descriptors = []
        for descriptor in self.descriptors:
            try:
                static_params = self.static_params.get(descriptor.__name__, {})
                params = combination.get(descriptor.__name__, {})
                params.update(static_params)
                descriptors.append(descriptor(**params))

            except TypeError:
                raise QueryInputError("Not enough parameters to construct constructor {0}\nGot: {1}".format(
                    descriptor.__name__, params))

        stars_filter = StarsFilter(descriptors, deciders)
        stars_filter.learn(self.searched_train, self.others_train)

        stat = stars_filter.getStatistic(self.searched_test, self.others_test)

        return stars_filter, stat
