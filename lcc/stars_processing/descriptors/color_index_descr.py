from lcc.entities.exceptions import QueryInputError
from lcc.stars_processing.utilities.base_descriptor import BaseDescriptor


class ColorIndexDescr(BaseDescriptor):
    '''
    Filter star according their color indexes

    Attributes
    -----------
    colors : list of strings
        List of magnitudes which will be used. They are keys to color indexes
        in star's object attribute 'more', where can be stored anything

    pass_not_found : bool
        If False stars without color index will be denied

    raise_if_not : bool
        If True it throws exception whenever a star has no color index

    without_notfound : bool
        If False coordinates of stars which have no color indexes will
        be returned as well, but with None instead of coordinates (list of
        values)

    labels : list of strings
        Labels of color-diagram axis
    '''

    def __init__(self, colors=[("b_mag", "v_mag"), ("v_mag", "i_mag")],
                 pass_not_found=False, raise_if_not=False,
                 without_notfound=True, *args, **kwargs):
        '''
        Parameters
        -----------
        colors : list of strings
            List of magnitudes which will be used. They are keys to color indexes
            in star's object attribute 'more', where can be stored anything.
            It can be list of keys (in stars more attribute) or list of tuples
            of two keys. In this case differences of these two values is taken.  


        pass_not_found : bool 
            If False stars without color index will be denied

        raise_if_not : bool
            If True it throws exception whenever a star has no color index

        without_notfound : bool
            If False coordinates of stars which have no color indexes will
            be returned as well, but with None instead of coordinates (list of
            values)

        '''
        self.pass_not_found = pass_not_found
        self.colors = colors
        self.labels = self.colors
        self.raise_if_not = raise_if_not
        self.without_notfound = without_notfound

        if colors and len(colors) == 2 and len(colors[0]) == 2:
            self.LABEL = [
                str(colors[0][1]) + "-" + str(colors[0][0]), str(colors[1][1]) + "-" + str(colors[1][0])]
        else:
            self.LABEL = colors

    def getSpaceCoords(self, stars):
        """
        Get list of desired colors

        Parameters
        -----------
        stars : list of Star objects
            Stars with color magnitudes in their 'more' attribute

        Returns
        -------
        List of list of floats
        """
        coords = []
        for star in stars:
            this_coords = []
            for col in self.colors:
                if hasattr(col, "__iter__"):
                    if len(col) == 2:
                        mag1 = star.more.get(col[0])
                        mag2 = star.more.get(col[1])
                        if mag1 and mag2:
                            this_coords.append(float(mag2) - float(mag1))
                        else:
                            this_coords.append(None)
                    else:
                        raise QueryInputError(
                            "Colors have to be list of tuples of the length of two (second - first magnitude)")
                else:
                    this_coords.append(star.more.get(col))
            coords.append(this_coords)
        return coords
