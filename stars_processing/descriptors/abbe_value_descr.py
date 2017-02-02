from lcc.stars_processing.utilities.base_descriptor import BaseDescriptor


class AbbeValueDescr(BaseDescriptor):

    '''
    Filter implementation which denies stars with lower value then a limit
    of Abbe value

    Attributes
    ----------
    bins : int
        Dimension of reduced light curve from which Abbe value
        is calculated
    '''
    LABEL = "Abbe value"

    def __init__(self, bins=None):
        '''
        Parameters
        ----------
        bins : int
            Dimension of reduced light curve from which Abbe value
            is calculated

        '''
        self.bins = bins

    def getSpaceCoords(self, stars):
        """
        Get list of Abbe values

        Parameters
        -----------
        stars : list of Star objects
            Stars with color magnitudes in their 'more' attribute

        Returns
        -------
        list
            List of list of floats
        """
        abbe_values = []

        for star in stars:
            if not self.bins:
                bins = len(star.lightCurve.time)
            else:
                bins = self.bins
            abbe_values.append(star.lightCurve.getAbbe(bins=bins))

        return abbe_values
