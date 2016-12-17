from stars_processing.filters_tools.base_filter import BaseFilter, Learnable
from utils.commons import returns, accepts
from utils.data_analysis import to_ekvi_PAA


class CurveDensityFilter(BaseFilter, Learnable):
    '''
    This filter throw out stars with low density light curves. It means light
    curves with huge non observing gaps or light curves with low amount
    of observations

    Attributes
    ----------
    decider : Decider instance
        Classifier object

    plot_save_path : str, NoneType
        Path to the folder where plots are saved if not None, else
        plots are showed immediately

    plot_save_name : str, NoneType
        Name of plotted file
    '''

    def __init__(self, decider, plot_save_path=None, plot_save_name="",
                 *args, **kwargs):
        '''
        Parameters
        ----------
        decider : Decider instance
            Classifier object

        plot_save_path : str, NoneType
            Path to the folder where plots are saved if not None, else
            plots are showed immediately

        plot_save_name : str, NoneType
            Name of plotted file
        '''
        self.decider = decider
        self.plot_save_path = plot_save_path
        self.plot_save_name = plot_save_name

    @returns(list)
    @accepts(list)
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
        Get list of curve densities

        Parameters
        -----------
        stars : list of Star objects
            Stars with color magnitudes in their 'more' attribute

        Returns
        -------
        list
            List of list of floats
        """
        coo = []
        for star in stars:
            if star.lightCurve:
                x, _ = to_ekvi_PAA(star.lightCurve.time, star.lightCurve.mag)
                ren = x.max() - x.min()
                coo.append([float(len(x)) / ren])
            else:
                coo.append([None])
        return coo
