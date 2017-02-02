import abc

from lcc.utils.commons import returns, accepts


class BaseDescriptor(object):
    __metaclass__ = abc.ABCMeta
    '''
    Base class for all filters. It is something like interface (check whether
    subclasses have certain methods
    '''

    LABEL = ""

    @accepts(list)
    @returns(list)
    def getSpaceCoords(self, stars):
        """
        Get list of parameters coordinates according to descriptor
        implementation

        Parameters
        -----------
        stars : list of Star objects
            Stars with color magnitudes in their 'more' attribute

        Returns
        -------
        list
            List of coordinates
        """
        raise NotImplementedError

    # TODO: Check whether these lists contains object of Star class type


class Learnable(object):
    """
    Common class for all filters which are able to call "learn" by yourself.
    All these classes need to be able obtain their space coordinates via
    getSpaceCoords. Then the learning is the same (see learn method below).

    Optionally there can be labels on plots if a class has label attribute,
    which is list of string contains label for data.

    Also after learning the 'learned' attribute is set to 'True' if exists.

    Moreover plot is saved if class has  plot_save_path attribute
    is not None or ''
    """

    def getSpaceCoords(self, stars):
        """
        Parameters
        -----------
        stars : list of Star objects

        Returns
        --------
        list of lists
            List of list of numbers (coordinates)
        """
        raise NotImplementedError(
            "getSpaceCoords need to be implemented in all  Learnable classes")

    def learn(self, searched_stars, contamination_stars, learn_num=""):
        """
        Teach filter to recognize searched stars

        Parameters
        ----------
        searched_stars : list of `Star` objects
            Searched stars to learn

        contamination_stars : list of `Star` objects
            Contamination stars to learn

        learn_num : str, int
            Optional identifier for the learning

        Returns
        -------
            None
        """
        self.decider.learn(self.getSpaceCoords(searched_stars),
                           self.getSpaceCoords(contamination_stars))
