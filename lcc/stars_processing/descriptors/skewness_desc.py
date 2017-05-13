import numpy as np
from scipy.stats import skew

from lcc.stars_processing.utilities.base_descriptor import BaseDescriptor
from lcc.utils.data_analysis import to_ekvi_PAA


class SkewnessDescr(BaseDescriptor):

    """
    SkewnessDescr describes stars by skewness

    Attributes
    ----------
    bins : int, NoneType
        Dimension of reduced light curve. If it is `None` whole curve is taken.

    absolute : bool
        Absolute value of skewness is taken if it is `True`
    """
    LABEL = "Skewness"

    def __init__(self, bins=None, absolute=False):
        """
        Parameters
        ----------
        bins : int, NoneType
            Dimension of reduced light curve. If it is `None` whole curve is taken.

        absolute : bool
            Absolute value of skewness is taken if it is True
        """
        self.bins = bins
        self.absolute = absolute

    def getSpaceCoords(self, stars):
        """
        Get list of skewness values

        Parameters
        -----------
        stars : list of Star objects
            Stars which contain light curves

        Returns
        -------
        list
            List of list of floats
        """
        skew_list = []
        for star in stars:
            if star.lightCurve:
                lc = star.lightCurve
                if self.bins:
                    _, mags = to_ekvi_PAA(lc.time, lc.mag, self.bins)
                else:
                    mags = lc.mag
                sk =skew(mags)

                if self.absolute:
                    sk = abs(sk)
            else:
                sk = None

            skew_list.append(sk)

        return skew_list
