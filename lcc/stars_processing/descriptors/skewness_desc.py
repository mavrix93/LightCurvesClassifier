import numpy as np
from scipy.stats import skew

from lcc.stars_processing.utilities.base_descriptor import BaseDescriptor
from lcc.utils.data_analysis import to_ekvi_PAA


class SkewnessDescr(BaseDescriptor):

    """
    SkewnessDescr describes stars by skewness

    Attributes
    ----------
    bins : int
        Dimension of reduced light curve
    """
    LABEL = "Skewness"

    def __init__(self, bins=None):
        """
        Parameters
        ----------
        bins : int
            Dimension of reduced light curve

        """
        self.bins = bins

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
            else:
                sk = None

            skew_list.append(sk)

        return skew_list
