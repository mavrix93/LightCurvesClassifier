from entities.exceptions import QueryInputError
from stars_processing.filters_tools.base_filter import BaseFilter, Learnable
from utils.commons import returns, accepts


class ColorIndexFilter(BaseFilter, Learnable):
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

    def __init__(self, colors=["b_mag", "v_mag", "i_mag"],
                 pass_not_found=False, raise_if_not=False,
                 without_notfound=True, *args, **kwargs):
        '''
        Parameters
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

        '''
        self.pass_not_found = pass_not_found
        self.colors = colors
        self.labels = self.colors
        self.raise_if_not = raise_if_not
        self.without_notfound = without_notfound

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
            colors = []
            for col in self.colors:
                if "-" not in col:
                    colors.append(star.more.get(col))
                else:
                    try:
                        mag1_txt, mag2_txt = col.split("-")
                        mag1, mag2 = star.more.get(
                            mag1_txt.strip(), None), star.more.get(mag2_txt.strip(), None)
                        if mag1 and mag2:
                            col_index = mag1 - mag2
                        else:
                            col_index = None

                        colors.append(col_index)
                    except:
                        raise QueryInputError(
                            "Invalid color index input.\nThere have to be mag1-mag2.")

            if None not in colors:
                coords.append([float(c) for c in colors])
            else:
                if self.raise_if_not:
                    raise Exception("Star %s has no color index." % star.ident)

                if not self.without_notfound:
                    coords.append(None)
        return coords
