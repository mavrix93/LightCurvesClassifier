import os

from conf import settings
from conf.package_reader import PackageReader
from utils.output_process_modules import loadFromFile


class FilterLoader(object):
    '''
    This class is responsible for reconstructing filter objects from files

    Attributes
    -----------
    FILTER_PATH : str
        Path to the folder of filter conf files

    FILTERS_KEY : str
        Identifier for filters in PackageReader

    file_name : str
        Name of the configuration file

    available_filters : list
        List of available filters
    '''

    FILTER_PATH = settings.FILTERS_PATH
    FILTERS_KEY = "filters"

    def __init__(self, file_name, pickle_object=False):
        '''
        Parameters
        ----------
        file_name : str
            Name of the configuration file
        '''

        self.file_name = file_name
        self.available_filters = PackageReader().getClasses(self.FILTERS_KEY)
        self.pickle_object = pickle_object

    def getFilter(self):
        """
        Get stars filter object

        Returns
        -------
        BaseFilter instance
            Constructed filter object
        """
        return self._loadFromPickle()

    def _loadFromPickle(self):
        return loadFromFile(os.path.join(self.FILTER_PATH, self.file_name))

    def _matchFilter(self, filter_name):
        for filt in self.available_filters:
            if filt.__name__ == filter_name:
                return filt
        return None
