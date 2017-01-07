import collections
import json
import os

from conf import settings
import numpy as np
from stars_processing.systematic_search.status_resolver import StatusResolver
from utils.helpers import progressbar, clean_path, create_folder
from utils.output_process_modules import saveIntoFile
import random


class DeciderEstimation(object):
    '''
    Attributes
    ----------
    searched : list of `Star` objects
        Searched stars

    others : list of `Star` objects
        Contamination stars

    star_filter : `BaseFilter` object
        Filter object (uninstancied)

    tuned_params : list of dicts
        List of parameters to tune

    log_path : str, NoneType
        Path to the folder where log file will be saved

    save_filter_name : str, NoneType
        Name of filter file if it is not None

    split_ratio : float
            Percentage number of train sample
    '''

    def __init__(self, searched, others, star_filter, tuned_params,
                 log_path=None, save_filter_name=None, split_ratio=0.75,
                 **kwargs):
        '''
        Parameters
        ----------
        searched : list of `Star` objects
            Searched stars

        others : list of `Star` objects
            Contamination stars

        star_filter : `BaseFilter` object
            Filter object (uninstancied)

        tuned_params : list of dicts
            List of parameters to tune

        log_path : str, NoneType
            Path to the folder where log file will be saved

        save_filter_name : str, NoneType
            Name of filter file if it is not None

        split_ratio : float
            Percentage number of train sample
        '''

        # TODO: Custom split ratio

        random.shuffle(searched)
        random.shuffle(others)

        self.searched_train = searched[:int(len(searched) * split_ratio)]
        self.searched_test = searched[int(len(searched) * split_ratio):]
        self.others_train = others[:int(len(others) * split_ratio)]
        self.others_test = others[int(len(others) * split_ratio):]
        self.star_filter = star_filter
        self.tuned_params = tuned_params
        self.log_path = log_path

        if not save_filter_name:
            save_filter_name = star_filter.__class__.__name__ + \
                "_tunedfilter." + settings.OBJECT_SUFFIX
        self.save_filter_name = save_filter_name

        self.params = kwargs
        if log_path:
            create_folder(log_path)
            if not os.path.isdir(log_path):
                raise Exception("There is no folder %s" % log_path)

    def fit(self):
        """
        Find best combination of filter parameters

        Returns
        -------
        `BaseFilter` instance
            Filter created from the best parameters
        """
        precisions = []
        filters = []
        stats = []
        i = 0
        for tun_param in progressbar(self.tuned_params,
                                     "Estimating combinations: "):
            i += 1

            x = tun_param.copy()
            x.update(self.params)
            filt = self.star_filter(**x)

            filt.learn(self.searched_train, self.others_train, learn_num=i)

            st = filt.getStatistic(self.searched_test, self.others_test)
            precisions.append(st["precision"])
            filters.append(filt)
            stats.append(st)

            z = collections.OrderedDict(tun_param).copy()
            z.update(collections.OrderedDict(st))

            if self.save_filter_name:
                StatusResolver.save_query([z], fi_name=clean_path(
                    self.save_filter_name) + "_log.dat", PATH=self.log_path,
                    DELIM="\t")

        best_id = np.argmax(precisions)

        print "*" * 30
        try:
            print "Best params:\n%s\n" % json.dumps(self.tuned_params[best_id],
                                                    indent=4)
        except:
            pass
        print "Statistic:\n%s\n" % json.dumps(stats[best_id], indent=4)

        if self.save_filter_name:
            saveIntoFile(
                filters[best_id], path=settings.FILTERS_PATH,
                file_name=self.save_filter_name)

        return filters[best_id]
