from __future__ import  division
import numpy as np

from lcc.entities.exceptions import QueryInputError
from lcc.stars_processing.utilities.base_descriptor import BaseDescriptor
from lcc.utils.data_analysis import to_ekvi_PAA, to_PAA
from sklearn import decomposition


class CurveDescr(BaseDescriptor):
    """
    Attributes
    ----------
    bins : int
        Dimension of reduced light curve

    height : int
        Range of points in magnitude axis

    red_dim : int, NoneType
        If not None dimension is reduced by PCA into given size
    """
    LABEL = "Light curve points"

    def __init__(self, bins=None, height=None, red_dim=None):
        """
        Parameters
        ----------
        bins : int
            Dimension of reduced light curve

        height : int
            Range of points in magnitude axis

        red_dim : int, NoneType
            If not None dimension is reduced by PCA into given size
        """
        self.bins = bins
        self.height = height
        self.pca = None
        self.red_dim = red_dim

        if red_dim:
            self.LABEL = ["Light curve point " + str(i+1) for i in range(red_dim)]
        elif bins:
            self.LABEL = ["Light curve point " + str(i+1) for i in range(bins)]

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
        if not self.bins:
            self.bins = np.min([len(st.lightCurve.mag) for st in stars if st.lightCurve])
            self.LABEL = ["Light curve point " + str(i+1) for i in range(self.bins)]
            print "Setting bins as min: ", self.bins

        coords = []
        for star in stars:
            if star.lightCurve:
                x, y = to_ekvi_PAA(
                    star.lightCurve.time, star.lightCurve.mag)

                if len(y) > self.bins:
                    y, _ = to_PAA(y, self.bins)
                else:
                    y, _ = to_PAA(star.lightCurve.mag, self.bins)
                y = np.array(y)

                if self.height:
                    y = self.height * y / (y.max() - y.min())
                    y = np.array([int(round(q)) for q in y])
                else:
                    y = y / (y.max() - y.min())

                y -= y.mean()
                coords.append(y.tolist())
            else:
                coords.append(None)

        if self.red_dim:
            _coords = [c for c in coords if c]

            if len(_coords[0]) > self.red_dim:
                _coords = self._reduceDimension(_coords)
            else:
                QueryInputError("Number of samples have to be greater then reduced dimension")

            k = 0
            red_coo = []
            for c in coords:
                if c:
                    red_coo.append(_coords[k])
                    k += 1
                else:
                    red_coo.append([np.NaN])
            coords = red_coo

        return coords

    def _reduceDimension(self, data):
        try:
            if not self.pca:
                self.pca = decomposition.PCA(n_components=self.red_dim)
                self.pca.fit(data)
            return self.pca.transform(data).tolist()
        except ValueError as e:
            raise QueryInputError(str(e))
