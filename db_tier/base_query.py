'''
Created on Feb 28, 2016

@author: Martin Vo
'''

import abc
import astropy.units as u
from entities.exceptions import QueryInputError


class StarsCatalogue(object):
    __metaclass__ = abc.ABCMeta
    '''Common class for all catalogues containing informations about stars'''

    def getStars(self):
        raise NotImplementedError

    def coneSearch(self, coo1, coo2, delta_deg):
        try:
            if not isinstance(delta_deg, u.quantity.Quantity):
                delta_deg = float(delta_deg) * u.deg

            if coo1.separation(coo2) < delta_deg:
                return True
            else:
                return False

        except AttributeError:
            raise QueryInputError("Invalid query coordinates")


class LightCurvesDb(StarsCatalogue):
    __metaclass__ = abc.ABCMeta
    '''This is common class for every database containing light curves'''

    def getStarsWithCurves(self):
        raise NotImplementedError
