from __future__ import  division
import numpy as np

from lcc.stars_processing.utilities.base_descriptor import BaseDescriptor
from lcc.utils.data_analysis import to_ekvi_PAA, to_PAA


class CurveDescr(BaseDescriptor):
    """
    Attributes
    ----------
    bins : int
        Dimension of reduced light curve

    height : int
        Range of points in magnitude axis
    """
    LABEL = "Light curve points"

    def __init__(self, bins=None, height=None):
        """
        Parameters
        ----------
        bins : int
            Dimension of reduced light curve

        height : int
            Range of points in magnitude axis
        """
        self.bins = bins
        self.height = height

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
                #x, y = to_ekvi_PAA(
                #    star.lightCurve.time, star.lightCurve.mag, self.bins)

                # TODO!
                y, _ = to_PAA(star.lightCurve.mag, self.bins)
                y = np.array(y)

                if self.height:
                    y = self.height * y / (y.max() - y.min())
                    y = np.array([int(round(q)) for q in y])
                else:
                    y = y / (y.max() - y.min())

                y -= y.mean()
                coords.append(y)

        if coords:
            self.LABEL = ["" for _ in coords[0]]
        return coords