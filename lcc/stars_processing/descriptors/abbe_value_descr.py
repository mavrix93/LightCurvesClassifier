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
    LC_NEEDED = True

    def __init__(self, bins=None):
        """
        Parameters
        ----------
        bins : int
            Dimension of reduced light curve from which Abbe value
            is calculated

        """
        self.bins = bins

    def getFeatures(self, star):
        """
        Get  Abbe value

        Parameters
        -----------
        star : lcc.entities.star.Star object
            Star to process

        Returns
        -------
        float
            Abbe value of the investigated star
        """
        if not self.bins:
            bins = len(star.lightCurve.time)
        else:
            bins = self.bins

        return star.lightCurve.getAbbe(bins=bins)

