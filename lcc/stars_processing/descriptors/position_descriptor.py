from lcc.stars_processing.utilities.base_descriptor import BaseDescriptor


class PositionDescriptor(BaseDescriptor):
    """
    Describe stars according their position on the sky
    """

    LABEL = ["Right ascension", "Declination"]
    LC_NEEDED = False

    def getFeatures(self, star):
        """
        Get coordinates

        Parameters
        -----------
        star : lcc.entities.star.Star object
            Star to process

        Returns
        -------
        list
            Abbe value of the investigated star
        """
        if star.coo:
            return [star.coo.ra.degree, star.coo.dec.degree]
        else:
            return [None, None]

