from __future__ import division

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
    '''

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
            Densities of points per time lag
        """
        coo = []
        for star in stars:
            if star.lightCurve:
                x, _ = to_ekvi_PAA(star.lightCurve.time, star.lightCurve.mag)
                ren = x.max() - x.min()
                coo.append([len(x) / ren])
            else:
                coo.append([None])
        return coo
