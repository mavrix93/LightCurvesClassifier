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
            Variogram slopes
        """

        coords = []
        for star in stars:
            if star.lightCurve:
                x, y = star.lightCurve.getVariogram(
                    days_per_bin=self.days_per_bin)
                slope = np.polyfit(x, y, 1)[0]
                if self.absolute:
                    slope = abs(slope)
                coords.append(slope)
            else:
                coords.append(None)
        return coords
