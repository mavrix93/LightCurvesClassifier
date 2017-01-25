import json
import random

import numpy as np

from utils.helpers import progressbar
from entities.exceptions import QueryInputError
from stars_processing.stars_filter import StarsFilter
from entities.exceptions import InvalidOption
from stars_processing.tools.stats_manager import StatsManager


class ParamsEstimator(object):
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
            Constant values for descriptors and deciders. Format is the
            same one item of tuned_params
        '''

        random.shuffle(searched)
        random.shuffle(others)

        self.searched_train = searched[:int(len(searched) * split_ratio)]
        self.searched_test = searched[int(len(searched) * split_ratio):]
        self.others_train = others[:int(len(others) * split_ratio)]
        self.others_test = others[int(len(others) * split_ratio):]
        self.descriptors = descriptors
        self.deciders = deciders
        self.tuned_params = tuned_params
        self.static_params = static_params

        self.stats_list = None
        self.filters = None

    def evaluateCombinations(self):
        """
        Evaluate all combination of the filter parameters

        Returns
        -------
        list
            Filters created from particular combinations

        list
            Statistical values of all combinations

        list
            Input parameters of all combinations
        """
        filters = []
        stats_list = []
        i = 0
        for tun_param in progressbar(self.tuned_params,
                                     "Evaluating the combinations: "):
            i += 1

            stars_filter, stats = self.evaluate(tun_param)
            stats_list.append(stats)
            filters.append(stars_filter)

        self.stats_list = stats_list
        self.filters = filters

        return stats_list, filters, self.tuned_params

    def fit(self, score_func, opt="max", save_params={}):
        """
        Find the best combination of the filter parameters

        Parameters
        ----------
        score_func : function
            Function which takes dict of statistical values and return
            a score

        opt : str
            Option for evaluating scores
                "max" - Returns the highest score
                "min" - Returns the lowerest score

        save_params : dict
            Parameters for saving outputs. For each output there are some
            mandatory keys:

            ROC plot:
                "roc_plot_path"
                "roc_plot_name"
                "roc_plot_title" - optional

            ROC data file:
                "roc_data_path"
                "roc_data_name"
                "roc_data_delim" - optional

            Statistical params of all combinations:
                "stats_path"
                "stats_name"
                "stats_delim" - optional


        Returns
        -------
        object
            Filter created from the best parameters

        dict
            Statistical values of the best combination

        dict
            Input parameters of the best combination
        """
        stats_list, filters, tuned_params = self.evaluateCombinations()

        try:
            self.saveOutput(save_params)
        except:
            raise
            raise Exception("Error during saving outputs...")

        scores = []
        for stat in stats_list:
            scores.append(score_func(**stat))

        if opt == "max":
            best_id = np.argmax(scores)
        elif opt == "min":
            best_id = np.argmin(scores)
        else:
            raise InvalidOption("Available options are: 'max' or 'min'.")

        return filters[best_id], stats_list[best_id], tuned_params[best_id]

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

    def saveOutput(self, save_params):
        """
        Parameters
        ----------
        save_params : dict
            Parameters for saving outputs. For each output there are some
            mandatory keys:

            ROC plot:
                "roc_plot_path"
                "roc_plot_name"
                "roc_plot_title" - optional

            ROC data file:
                "roc_data_path"
                "roc_data_name"
                "roc_data_delim" - optional

            Statistical params of all combinations:
                "stats_path"
                "stats_name"
                "stats_delim" - optional
        """
        man = StatsManager(self.stats_list)
        if "roc_plot_path" in save_params and "roc_plot_name" in save_params:
            man.plotROC(save=True,
                        title=save_params.get("roc_plot_title", "ROC"),
                        path=save_params.get("roc_plot_path"),
                        file_name=save_params.get("roc_plot_name"))

        if "roc_data_path" in save_params and "roc_data_name" in save_params:
            man.saveROCfile(path=save_params.get("roc_data_path"),
                            file_name=save_params.get("roc_data_name"),
                            delim=save_params.get("stats_delim", "\t"))

        if "stats_path" in save_params and "stats_name" in save_params:
            man.saveStats(path=save_params.get("stats_path"),
                          file_name=save_params.get("stats_name"),
                          delim=save_params.get("stats_delim", "\t"),
                          overwrite=True)
