import numpy as np
from scipy.stats import kurtosis

from lcc.stars_processing.utilities.base_descriptor import BaseDescriptor
from lcc.utils.data_analysis import to_ekvi_PAA


class KurtosisDescr(BaseDescriptor):

    """
    KurtosisDescr describes stars by kurtosis

    Attributes
    ----------
    bins : int, NoneType
        Dimension of reduced light curve. If it is `None` whole curve is taken.

    absolute : bool
        Absolute value of kurtosis is taken if it is `True`
    """
    LABEL = "Kurtosis"

    def __init__(self, bins=None, absolute=False):
        """
        Parameters
        ----------
        bins : int, NoneType
            Dimension of reduced light curve. If it is `None` whole curve is taken.

        absolute : bool
            Absolute value of kurtosis is taken if it is `True`
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
        kurtosis_list = []
        for star in stars:
            if star.lightCurve:
                lc = star.lightCurve
                if self.bins:
                    _, mags = to_ekvi_PAA(lc.time, lc.mag, self.bins)
                else:
                    mags = lc.mag
                kurt = kurtosis(mags)

                if self.absolute:
                    kut = abs(kurt)

            else:
                kurt = None
            kurtosis_list.append(kurt)
        return kurtosis_list