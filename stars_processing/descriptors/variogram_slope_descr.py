import numpy as np
from lcc.stars_processing.utilities.base_descriptor import BaseDescriptor


class VariogramSlopeDescr(BaseDescriptor):
    '''
    This filter sorting stars according slopes of their variograms

    Attributes
    ----------
    variogram_days_bin : float
        Rate between light curve dimension and days
    '''

    LABEL = "Light curve's variogram slope"

    def __init__(self, variogram_days_bin):
        '''
        Parameters
        ----------
        variogram_days_bin : float
            Rate between light curve dimension and days
        '''
        self.variogram_days_bin = variogram_days_bin

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
                    days_per_bin=self.variogram_days_bin)
                coords.append(np.polyfit(x, y, 1)[0])
            else:
                coords.append(None)
        return coords
