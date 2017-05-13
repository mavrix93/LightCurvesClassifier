from lcc.stars_processing.utilities.base_descriptor import BaseDescriptor


class AbbeValueDescr(BaseDescriptor):

    """
    AbbeValueDescr describes stars by Abbe values

    Attributes
    ----------
    bins : int
        Dimension of reduced light curve from which Abbe value
        is calculated
    """
    LABEL = "Abbe value"

    def __init__(self, bins=None):
        """
        Parameters
        ----------
        bins : int
            Dimension of reduced light curve from which Abbe value
            is calculated

        """
        self.bins = bins

    def getSpaceCoords(self, stars):
        """
        Get list of Abbe values

        Parameters
        -----------
        stars : list of Star objects
            Stars which contain light curves

        Returns
        -------
        list
            List of list of floats
        """
        abbe_values = []

        for star in stars:
            if star.lightCurve:

                if not self.bins:
                    bins = len(star.lightCurve.time)
                else:
                    bins = self.bins

                ab = star.lightCurve.getAbbe(bins=bins)
            else:
                ab = None

            abbe_values.append(ab)

        return abbe_values
