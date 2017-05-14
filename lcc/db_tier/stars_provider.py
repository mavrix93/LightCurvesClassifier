from lcc.data_manager.package_reader import PackageReader


class StarsProvider(object):
    """
    Stars provider is an interface between end-user and database connectors. All
    database connectors have to inherit `StarsCatalog` class.

    Attributes
    ----------
    STARS_PROVIDER : dict

    """

    STARS_PROVIDERS = PackageReader().getClassesDict("connectors")

    @classmethod
    def getProvider(cls, obtain_method, *obtain_params):
        """
        Get database connector via name of its class

        Parameters
        -----------
        obtain_method : str
            Name of connector class
        obtain_params :  list of dicts
            List of queries

        Returns
        --------
        instance
            Constructed database connector or uninstanced  if there is
            no queries
        """

        if obtain_method not in cls.STARS_PROVIDERS:
            raise AttributeError(
                "Unresolved stars provider\nAvaible stars providers: %s" % cls.STARS_PROVIDERS.keys())

        provider = cls.STARS_PROVIDERS[obtain_method]

        if len(obtain_params) == 0:
            return provider
        return provider(*obtain_params)
