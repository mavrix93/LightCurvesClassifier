from stars_processing.filters_tools.base_filter import BaseFilter, Learnable
from utils.commons import returns, accepts


class AbbeValueFilter(BaseFilter, Learnable):

    '''
    Filter implementation which denies stars with lower value then a limit
    of Abbe value

    Attributes
    ----------
    bins : int
        Dimension of reduced light curve from which Abbe value
        is calculated

    decider : Decider instance
        Classifier object

    plot_save_path : str, NoneType
        Path to the folder where plots are saved if not None, else
        plots are showed immediately

    plot_save_name : str, NoneType
        Name of plotted file
    '''

    def __init__(self, bins=None, decider=None, plot_save_path=None,
                 plot_save_name=None, *args, **kwargs):
        '''
        Parameters
        ----------
        bins : int
            Dimension of reduced light curve from which Abbe value
            is calculated

        decider : Decider instance
            Classifier object

        plot_save_path : str, NoneType
            Path to the folder where plots are saved if not None, else
            plots are showed immediately

        plot_save_name : str, NoneType
            Name of plotted file
        '''
        self.bins = bins
        self.decider = decider

        self.plot_save_path = plot_save_path
        self.plot_save_name = plot_save_name

    @accepts(list)
    @returns(list)
    def applyFilter(self, stars):
        '''
        Filter stars by Abbe value filter

        Parameters
        ----------
        stars : list
            List of `Star` objects (containing light curves)

        Returns
        -------
        list
            List of star-like objects passed thru filtering
        '''
        abbe_values = self.getSpaceCoords(stars)
        return [star for star, passed in zip(stars,
                                             self.decider.filter(abbe_values)) if passed]

    def getSpaceCoords(self, stars):
        """
        Get list of Abbe values

        Parameters
        -----------
        stars : list of Star objects
            Stars with color magnitudes in their 'more' attribute

        Returns
        -------
        list
            List of list of floats
        """
        abbe_values = []

        for star in stars:
            if not self.bins:
                bins = len(star.lightCurve.time)
            else:
                bins = self.bins
            abbe_values.append([star.lightCurve.getAbbe(bins=bins)])

        return abbe_values
