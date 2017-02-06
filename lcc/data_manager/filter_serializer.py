import os

from lcc.utils.output_process_modules import loadFromFile
from lcc.utils.output_process_modules import saveIntoFile


class FiltersSerializer(object):
    '''
    This class is responsible for saving and reconstructing filter
    objects from files

    Attributes
    -----------
    file_name : str
        Name of the filter name

    path : str
        Path to the filter location
    '''

    def __init__(self, file_name, path):
        '''
        Parameters
        ----------
        file_name : str
            Name of the filter name

        path : str
            Path to the filter location
        '''

        self.file_name = file_name
        self.path = path

    def loadFilter(self):
        """
        Get stars filter object

        Returns
        -------
        BaseFilter instance
            Constructed filter object
        """
        return self._loadFromPickle()

    def saveFilter(self, star_filter):
        """
        Parameters
        ----------
        star_filter : BaseFilter instance
            Save object as pickle

        Returns
        -------
            None
        """
        saveIntoFile(star_filter, self.path, self.file_name)

    def _loadFromPickle(self):
        return loadFromFile(os.path.join(self.path, self.file_name))
