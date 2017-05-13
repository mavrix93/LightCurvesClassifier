from __future__ import division

from astropy.coordinates.sky_coordinate import SkyCoord
import numpy
from warnings import warn

import astropy.units as u
from lcc.entities.exceptions import StarAttributeError
from lcc.entities.light_curve import LightCurve
import warnings


class Star(object):
    """
    Star is base object in astronomy. This class is responsible for keeping
    basic informations about stellar objects. It's possible to create empty
    star and add parameters additionally

    Attributes
    -----------
    ident : dict
            Dictionary of identifiers of the star. Each key of the dict
            is name of a database and its value is another dict of database
            identifiers for the star (e.g. 'name') which can be used
            as an unique identifier for querying the star. For example:
                ident = {"OgleII" : {"name" : "LMC_SC1_1",
                                    "db_ident" : {"field_num" : 1,
                                                  "starid" : 1,
                                                  "target" : "lmc"},
                                                  ...}
            Please keep convention as is shown above. Star is able to
            be queried again automatically if ident key is name of
            database connector and it contains dictionary called
            "db_ident". This dictionary contains unique query for
            the star in the database.
    name : str
        Optional name of the star across the all databases
    coo : astropy.coordinates.sky_coordinate.SkyCoord
        Coordinate of the star
    more : dict
        Additional informations about the star in dictionary. This
        attribute can be considered as a container. These parameters
        can be then used for filtering. For example it can contains
        color indexes:
            more = { "b_mag" : 17.56, "v_mag" : 16.23 }
    star_class : str
        Name of category of the star e.g. 'cepheid', 'RR Lyrae', etc.
    light_curves : list
        Light curve objects of the star
    EPS : float
        Max distance in degrees to consider two stars equal
    """

    EPS = 0.000138

    def __init__(self, ident={}, name=None, coo=None, more={},
                 starClass=None):
        """
        Parameters
        -----------
        ident : dict
            Dictionary of identifiers of the star. Each key of the dict
            is name of a database and its value is another dict of database
            identifiers for the star (e.g. 'name') which can be used
            as an unique identifier for querying the star. For example:

                ident = {"OgleII" : {"name" : "LMC_SC1_1",
                                    "db_ident" : {"field_num" : 1,
                                                  "starid" : 1,
                                                  "target" : "lmc"},
                                                  ...}

            Please keep convention as is shown above. Star is able to
            be queried again automatically if ident key is name of
            database connector and it contains dictionary called
            "db_ident". This dictionary contains unique query for
            the star in the database.
        name : str
            Optional name of the star across the all databases
        coo : SkyCoord object
            Coordinate of the star
        more : dict
            Additional informations about the star in dictionary. This
            attribute can be considered as a container. These parameters
            can be then used for filtering. For example it can contains
            color indexes:

                more = { "b_mag" : 17.56, "v_mag" : 16.23 }
        star_class : str
            Name of category of the star e.g. 'cepheid', 'RR Lyrae', etc.
        """
        self.ident = ident
        self.coo = coo
        self.more = more
        self.light_curves = []
        self.starClass = starClass

        self.name = name

    def __eq__(self, other):
        if not (isinstance(other, Star)):
            return False

        if other is None:
            return False

        elif self.ident:
            for db_key in self.ident.keys():
                if db_key in other.ident:
                    if self.ident[db_key] == other.ident[db_key]:
                        return True
        return self.getInRange(other, self.EPS)

    def __str__(self):
        star_text = ""
        for db_key in self.ident:
            star_text += "%s identifier:\t" % db_key
            for key in self.ident[db_key]:
                star_text += "%s: %s\t" % (key, self.ident[db_key][key])
            star_text += "\n"

        if self.coo:
            star_text += "\tCoordinate: %s" % self.coo.to_string("hmsdms")
        return star_text

    @property
    def coo(self):
        return self._coo

    @coo.setter
    def coo(self, given_coo):
        if given_coo and given_coo.__class__.__name__ != "SkyCoord":
            if None not in [it for it in given_coo]:
                try:
                    if len(given_coo) == 3:
                        unit = given_coo[2]
                    else:
                        unit = "deg"
                    given_coo = SkyCoord(given_coo[0], given_coo[1], unit=unit)

                except:
                    warnings.warn("""Invalid values for
                                            constructing coordinate object""")
                    given_coo = None
            else:
                given_coo = None
        self._coo = given_coo

    @property
    def lightCurve(self):
        if self.light_curves:
            return self.light_curves[0]
        return None

    @lightCurve.setter
    def lightCurve(self, lc):
        self.putLightCurve(lc)

    @property
    def name(self):
        if self._name:
            return self._name
        return self.getIdentName()

    @name.setter
    def name(self, name):
        self._name = name

    def getInRange(self, other, eps):
        '''
        This method decides whether other star is in eps range of this star
        according to coordinates

        Parameters
        -----------
            other : Star object
                Star to compare with
            eps : float, astropy.unit.quantity.Quantity
                Range in degrees

        Returns
        --------
        bool
            If in range
        '''
        if not isinstance(eps, u.quantity.Quantity):
            eps = eps * u.deg

        if self.coo is None:
            warn("Star {0} has no coordinates".format(
                self.name))

        return self.getDistance(other) < eps

    def getDistance(self, other):
        '''
        Compute distance between this and other star in degrees

        Parameters
        -----------
            other : Star object
                Another star object to compare with

        Returns
        --------
        astropy.coordinates.angles.Angle
            Distance of stars in degrees
        '''
        return self.coo.separation(other.coo)

    def getIdentName(self, db_key=None):
        """
        Parameters
        -----------
            db_key : str
                Database key

        Returns
        --------
        str
            Name of the star in given database. If it is not specified,
            the first database will be taken to construct the name
        """

        if db_key is None:
            if len(self.ident.keys()) == 0:
                return "Unknown"
            db_key = self.ident.keys()[0]

        if "name" in self.ident[db_key]:
            return self.ident[db_key]["name"]
        star_name = db_key
        for key in self.ident[db_key]:
            star_name += "_%s_%s" % (key, self.ident[db_key][key])
        return star_name

    def putLightCurve(self, lc, meta={}):
        '''
        Add light curve to the star

        Parameters
        ----------
        lc : list, numpy.ndarray
            Light curve

        Returns
        -------
            None
        '''
        if not isinstance(lc, numpy.ndarray) and not lc:
            warn("Invalid light curve: %s\nLight curve not created to star %s" % (
                lc, self.name))

        if hasattr(lc, "__iter__") and len(lc) and isinstance(lc[0], LightCurve):
            self.light_curves += lc

        elif not isinstance(lc, LightCurve) and len(lc):
            self.light_curves.append(LightCurve(lc, meta=meta))

        elif lc:
            self.light_curves.append(lc)
