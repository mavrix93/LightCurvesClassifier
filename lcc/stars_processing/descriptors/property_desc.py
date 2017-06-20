from lcc.stars_processing.utilities.base_descriptor import BaseDescriptor


class PropertyDescr(BaseDescriptor):
    """
    Descriptor which using star's attributes

    Attributes
    -----------
    attribute_names : iterable, str
        Keys of star's objects `more` attribute
	
	For example:
	    `["pm_ra", "pm_de"]`

    ifnot : str, NoneType
        Value of coordinates which will be assigned if there is no
        `attribute_name` value


    """

    LABEL = "Star's property"
    LC_NEEDED = False

    def __init__(self, attribute_names, ifnot=None):
        """
        Parameters
        -----------
        attribute_names : iterable, str
            Keys of star's objects `more` attribute

        ifnot : str, NoneType
            Value of coordinates which will be assigned if there is no
            `attribute_name` value
        """
        if hasattr(attribute_names, "__iter__"):
            attribute_names = list(attribute_names)
        else:
            attribute_names = [attribute_names]

        self.attribute_names = attribute_names
        self.ifnot = ifnot

        self.LABEL = attribute_names

    def getFeatures(self, star):
        """
        Get desired attributes

        Parameters
        -----------
        star : lcc.entities.star.Star object
            Star to process

        Returns
        -------
        list
            Desired more attributes of the investigated star
        """
        coo = [star.more.get(attribute_name, self.ifnot)
               for attribute_name in self.attribute_names]
        if coo != self.ifnot:
            try:
                coo = [float(c) for c in coo]
            except ValueError:
                raise ValueError(
                    "Attributes of stars for PropertyDescriptors have to be numbers.\nGot: %s" % coo)

        return coo
