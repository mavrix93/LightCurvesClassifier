import os
import random

from lcc.data_manager.status_resolver import StatusResolver
from lcc.db_tier.stars_provider import StarsProvider
from lcc.entities.exceptions import QueryInputError
from lcc.utils.helpers import progressbar


def getStars(queries, lcs_fold, query_path=None, progb_txt="Querying stars: "):
    """
    Get stars from query text. According to format of the query text different
    methods are called.

        1.QUERY:db_name:query_file_in_inputs_folder
            --> Remote database is queried (db key is name of connector class)

        2.stars_folder_key:number or stars_folder_key:float_number or stars_folder_key
            --> Light curves from folder according to first key is loaded
                (according to settings.STARS_PATH dictionary). All stars are
                loaded if there is no number and ':', in case of integer after
                ':' just this number of stars are loaded and if there are float
                number after ':' this percentage number of all stars are loaded.

    """
    ORDINARY_QUERY_KEY = "QUERY:"

    stars = []
    for query in progressbar(queries, progb_txt):
        query = query.strip()

        if query.startswith(ORDINARY_QUERY_KEY):
            stars += getStarsFromRemoteDb(
                query[len(ORDINARY_QUERY_KEY):], query_path)

        else:
            stars += getStarsFromFolder(query, lcs_fold)

    if not stars:
        raise QueryInputError("There no stars. Your query: %s" % queries)

    return stars


def getStarsFromFolder(single_path, lcs_fold):
    """
    Get stars from folder/s. If path is iterable (case that more folders were
    given, light curves from that all folder will be loaded

    Parameters
    -----------
        single_path : str
            Name of the folder of lightcurves from "light_curve" directory (specified
            in settings).

    Returns
    --------
        stars : List of Star objects
            Stars from the folder
    """
    p, restr = _check_sample_name(single_path)
    try:
        st = StarsProvider().getProvider(
            "FileManager", {"path": os.path.join(lcs_fold, p)}).getStars()
        stars = _split_stars(st, restr)

    except KeyError:
        raise IOError("\n\nThere no folder with light curves named %s." % (p))

    if not stars:
        raise Exception(
            "There are no stars in path with given restriction %s " % single_path)

    random.shuffle(stars)
    return stars


def getStarsFromRemoteDb(query, query_path):
    """
    This method parsing the query text in order to return desired stars
    from remote database.

    Parameters
    -----------
        query : str
            Query text contains db_key and query file separated by ':'

    Returns
    --------
        List of Star objects

    Example
    -------
        _getStarsFromRemoteDb("OgleII:query_file.txt") --> [Star objects]

        query_file.txt:
            #starid;field;target
            1;1;lmc
            10;1;smc
    """

    try:
        db_key, query_file = query.split(":")
    except:
        QueryInputError(
            "Key for resolving stars source was not recognized:\n%s" % query)

    queries = StatusResolver(
        os.path.join(query_path, query_file)).getQueries()

    stars = []
    for query in progressbar(queries, "Querying stars: "):
        starsProvider = StarsProvider().getProvider(obtain_method=db_key,
                                                    obtain_params=query)

        stars += starsProvider.getStars()

    return stars


def _split_stars(stars, restr):
    random.shuffle(stars)
    num = None
    if type(restr) == float:
        n = len(stars)
        num = int(n * restr)

    elif type(restr) == int:
        num = restr

    return stars[:num]


def _check_sample_name(star_class):

    if "%" in star_class:
        parts = star_class.split("%")

        if len(parts) == 2:
            name, ratio = parts

            try:
                ratio = float(ratio)
            except ValueError:
                raise Exception("Invalid float number after '%' %s " % ratio)

            return name, ratio
        else:
            raise Exception(
                "There have to be just one '%' special mark in the star class name.\Got %s" % star_class)

    elif ":" in star_class:
        parts = star_class.split(":")

        if len(parts) == 2:
            name, num = parts

            try:
                num = int(num)
            except ValueError:
                raise Exception("Invalid integer after '%' %s " % num)

            return name, num
        else:
            raise Exception(
                "There have to be just one ':' special mark in the star class name.\Got %s" % star_class)

    return star_class, None
