from __future__ import division

from lcc.utils.data_analysis import to_ekvi_PAA
from lcc.stars_processing.utilities.base_descriptor import BaseDescriptor


class CurveDensityDescr(BaseDescriptor):
    """
    This filter throw out stars with low density light curves. It means light
    curves with huge non observing gaps or light curves with low amount
    of observations

    Attributes
    ----------
    """

    LABEL = "Curve density [points per time lag]"
    LC_NEEDED = True

    def getFeatures(self, star):
        """
        Get density of the star's light curve

        Parameters
        -----------
        star : lcc.entities.star.Star object
            Star to process

        Returns
        -------
        list, iterable, int, float
            Density (points per time lag) of the investigated star
        """
        x, _ = to_ekvi_PAA(star.lightCurve.time, star.lightCurve.mag)
        ren = x.max() - x.min()
        return len(x) / ren

