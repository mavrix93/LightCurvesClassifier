from lcc.stars_processing.utilities.base_descriptor import BaseDescriptor
from lcc.utils.data_analysis import to_ekvi_PAA


class CurveDescr(BaseDescriptor):

    '''
    Attributes
    ----------
    bins : int
        Dimension of reduced light curve 
    '''
    LABEL = "Light curve points"

    def __init__(self, bins=None):
        '''
        Parameters
        ----------
        bins : int
            Dimension of reduced light curve

        '''
        self.bins = bins

    def getSpaceCoords(self, stars):
        """
        Get reduced light curve as coordinates

        Parameters
        -----------
        stars : list of Star objects
            Stars with color magnitudes in their 'more' attribute

        Returns
        -------
        list
            List of list of floats
        """
        coords = []

        for star in stars:
            if star.lightCurve:
                x, y = to_ekvi_PAA(
                    star.lightCurve.time, star.lightCurve.mag, self.bins)
                coords.append(y.tolist())

        if coords:
            self.LABEL = ["" for _ in coords[0]]
        return coords
