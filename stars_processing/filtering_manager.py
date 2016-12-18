from conf import settings
from entities.exceptions import NotFilterTypeClass
from entities.star import Star
from stars_processing.filters_tools.base_filter import BaseFilter
from utils.helpers import verbose


class FilteringManager(object):
    '''
    This class is responsible for filtering stars according to given filters
    (their own implementation of filtering)
    Class is initialized with inspected stars as argument. Additionally stars
    can be added thru add method. Each filter has its own implementation
    of preparing

    Attributes
    ----------
    stars : list of `Star` objects
        Stars to be filtered

    filters : list of filters
        Filters which are used to filtering given stars
    '''

    def __init__(self, stars=[]):
        '''
        stars : list of `Star` objects
            Stars which will be filtered
        '''

        self.stars = stars
        self.filters = []

    def loadFilter(self, stars_filter):
        '''
        Load filters

        Parameters
        ----------
        stars_filter : list of filters
            Star filters object responsible for filtering stars

        Returns
        -------
            None
        '''

        self._check_filter_validity(stars_filter)
        self.filters.append(stars_filter)

    def performFiltering(self):
        '''
        Apply all filters to stars and return stars which passed
        thru all filters

        Returns
        -------
        list of `Star`s
            Stars which passed thru filtering
        '''

        stars = self.stars
        for st_filter in self.filters:
            stars = st_filter.applyFilter(stars)
        verbose("Filtering is done\nNumber of stars passed filtering: %i / %i" %
                (len(stars), len(self.stars)), 3, settings.VERBOSITY)
        return stars

    def addStars(self, stars):
        '''
        Add list of stars or one star to the list of stars for filtering

        Parameters
        ----------
        stars : list of `Star` objects
            Stars to be filtered

        Returns
        -------
            None
        '''

        ty_stars = type(stars)
        if (ty_stars == list):
            self.stars += stars
        elif (ty_stars == Star):
            self.stars.append(stars)

    def _check_filter_validity(self, stars_filter):
        '''Check whether filter class inherit BaseFilter'''

        if not isinstance(stars_filter, BaseFilter):
            raise NotFilterTypeClass(stars_filter.__class__.__name__)
