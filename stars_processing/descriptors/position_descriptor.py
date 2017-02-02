from lcc.stars_processing.utilities.base_decider import BaseDecider


class PositionDescriptor(BaseDecider):
    '''
    Describe stars according their position on the sky
    '''

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
            coords.append([star.coo.ra.degree, star.coo.dec.degree])
        return coords