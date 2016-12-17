import numpy as np
from stars_processing.filters_tools.base_filter import BaseFilter, Learnable
from utils.commons import returns, accepts


class VariogramSlope(BaseFilter, Learnable):
    '''
    This filter sorting stars according slopes of their variograms

    Attributes
    ----------
    variogram_days_bin : float
        Rate between light curve dimension and days

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

    def __init__(self, variogram_days_bin, decider,
                 plot_save_path=None, plot_save_name="", *args, **kwargs):
        '''
        Parameters
        ----------
        variogram_days_bin : float
            Rate between light curve dimension and days

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
        self.decider = decider
        self.variogram_days_bin = variogram_days_bin
        self.plot_save_path = plot_save_path
        self.plot_save_name = plot_save_name

    @accepts(list)
    @returns(list)
    def applyFilter(self, stars):
        '''
        Filter stars

        Parameters
        ----------
        stars : list
            List of `Star` objects (containing light curves)

        Returns
        -------
        list
            List of star-like objects passed thru filtering
        '''
        stars_coords = self.getSpaceCoords(stars)

        return [star_coo for star_coo, passed in zip(stars_coords,
                                                     self.decider.filter(stars_coords)) if passed]

    def getSpaceCoords(self, stars):
        """
        Get list of desired colors

        Parameters
        -----------
        stars : list of Star objects
            Stars with color magnitudes in their 'more' attribute

        Returns
        -------
        list
            List of list of floats
        """

        coords = []
        for star in stars:
            if star.lightCurve:
                x, y = star.lightCurve.getVariogram(
                    days_per_bin=self.variogram_days_bin)

                coords.append([np.polyfit(x, y, 1)[0]])
            else:
                coords.append([None])
        return coords
