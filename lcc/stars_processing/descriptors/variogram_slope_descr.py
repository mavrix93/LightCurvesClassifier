import numpy as np
from lcc.stars_processing.utilities.base_descriptor import BaseDescriptor


class VariogramSlopeDescr(BaseDescriptor):
    """
    This filter sorting stars according slopes of their variograms

    Attributes
    ----------
    days_per_bin : float
        Rate between light curve dimension and days

    absolute : bool
        If True absolute value of slope is taken
    """

    LABEL = "Light curve's variogram slope"
    LC_NEEDED = True

    def __init__(self, days_per_bin, absolute=False):
        """
        Parameters
        ----------
        days_per_bin : float
            Rate between light curve dimension and days

        absolute : bool
            If True absolute value of slope is taken
        """
        self.days_per_bin = days_per_bin
        self.absolute = absolute

    def getFeatures(self, star):
        """
        Get variogram slope

        Parameters
        -----------
        star : lcc.entities.star.Star object
            Star to process

        Returns
        -------
        float
            Variogram slope of the investigated star
        """
        x, y = star.lightCurve.getVariogram(
            days_per_bin=self.days_per_bin)
        slope = np.polyfit(x, y, 1)[0]
        if self.absolute:
            return abs(slope)
        return slope

