import random
import types
import warnings

import pathos.multiprocessing as multiprocessing
import sys

import time
from lcc.entities.exceptions import InvalidOption
from lcc.entities.exceptions import QueryInputError
from lcc.stars_processing.stars_filter import StarsFilter
from lcc.stars_processing.tools.stats_manager import StatsManager
import numpy as np


class ParamsEstimator(object):
    """
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

    num_proc : NoneType, bool, int
        Number of cores to use for parallel computing. If 'True' all cores will be used
        
    multiproc : bool, int
        If True task will be distributed into threads by using all cores. If it is number,
        just that number of cores are used
    """

    def __init__(self, searched, others, descriptors, deciders, tuned_params,
                 split_ratio=0.7, static_params={}, multiproc=True):
        """
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

        multiproc : bool, int
            If True task will be distributed into threads by using all cores. If it is number,
            just that number of cores are used            
        """

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

        self.stats_list = []
        self.stats = {}
        self.filters = []

        self.multiproc = multiproc

    def evaluateCombinations(self, tuned_params=None):
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

        if not tuned_params:
            tuned_params = self.tuned_params

        if self.multiproc:
            if self.multiproc is True:
                n_cpu = multiprocessing.cpu_count()
            else:
                n_cpu = self.multiproc

            pool = multiprocessing.Pool(n_cpu)

            result = pool.map_async(self.evaluate, tuned_params)
            pool.close()  # No more work
            n = len(tuned_params)
            while True:
                if result.ready():
                    break
                sys.stderr.write('\rEvaluated combinations: {0} / {1}'.format(n - result._number_left, n))
                time.sleep(0.6)
            result = result.get()
            sys.stderr.write('\rAll {0} combinations have been evaluated'.format(n))

            # result = pool.map(self.evaluate, tuned_params)
        else:
            result = [self.evaluate(tp) for tp in tuned_params]

        for stars_filter, stats in result:
            self.stats_list.append(stats)
            self.filters.append(stars_filter)

        return self.stats_list, self.filters, tuned_params

    def fit(self, score_func=None, opt="max", save_params=None):
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
                "min" - Returns the lowermost score

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
        if not save_params:
            save_params = {}

        stats_list, filters, tuned_params = self.evaluateCombinations()

        try:
            self.saveOutput(save_params)
        except Exception as e:
            warnings.warn("\nError during saving outputs...:\n\t%s" % e)

        scores = []
        for stat in stats_list:
            if not score_func:
                score = stat.get("precision", 0)
            else:
                score = score_func(**stat)
            scores.append(score)

        if opt == "max":
            best_id = np.argmax(scores)
        elif opt == "min":
            best_id = np.argmin(scores)
        else:
            raise InvalidOption("Available options are: 'max' or 'min'.")

        self.best_id = best_id

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

        descriptors = []
        deciders = []
        n = len(self.descriptors)
        for i, des in enumerate(self.descriptors + self.deciders):
            try:
                static_params = self.static_params.get(des.__name__, {})
                _params = combination.get(des.__name__, {})
                params = _params.copy()
                params.update(static_params)

                if i < n:
                    descriptors.append(des(**params))
                else:
                    deciders.append(des(**params))

            except TypeError:
                raise QueryInputError("Not enough parameters to construct constructor {0}\nGot: {1}".format(
                    des.__name__, params))

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
        to_save = self._prepareStatus(self.stats_list, self.tuned_params)
        self.stats = to_save
        man = StatsManager(to_save)
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

    def _prepareStatus(self, stats_list, tuned_params):
        result = []
        for st, tun in zip(stats_list, tuned_params):
            x = st.copy()
            unpacked_tun = self._mergeTwoDict(st, tun)
            x.update(unpacked_tun)
            result.append(x)
        return result

    def _mergeTwoDict(self, stat, tun):
        unpacked_tun = []
        for prefix, inner_dict in tun.iteritems():
            for key, value in inner_dict.iteritems():
                if hasattr(value, "__iter__"):
                    # if len(value) > 0 and not isinstance(value[0], types.InstanceType):
                    #    unpacked_tun.append((key,value))
                    #
                    pass

                elif not isinstance(value, types.InstanceType):
                    unpacked_tun.append((":".join([prefix, key]), value))
        return unpacked_tun
