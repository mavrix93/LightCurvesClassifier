from lcc.stars_processing.utilities.base_descriptor import BaseDescriptor


class PositionDescriptor(BaseDescriptor):
    '''
    Describe stars according their position on the sky
    '''

    LABEL = ["Right ascension", "Declination"]

    def getSpaceCoords(self, stars):
        """
        Get list of desired attributes

        Parameters
        -----------
        stars : list of Star objects
            Stars with `coo` attribute

        Returns
        -------
        list
            List of list of floats
        """

        coords = []
        for star in stars:
            if star.coo:
                coords.append([star.coo.ra.degree, star.coo.dec.degree])
            else:
                coords.append([None, None])
        return coords
