import collections
import os
from warnings import warn
import warnings

from lcc.db_tier.stars_provider import StarsProvider
from lcc.entities.exceptions import QueryInputError, InvalidFilesPath
from lcc.utils.helpers import progressbar
from lcc.utils.stars import saveStars


class StarsSearcher():
    '''
    The class manages systematic searching in databases. It also can be used
    as base class for other star searchers.

    Attributes
    ----------
    stars_filter : FilteringManager object
        Filter which is prepared filter star objects

    save_path : str
        Path from "run" module to the folder where found
        light curves will be saved

    stat_file_path : str
        Status file name

    save_lim : int
        Number of searched objects after which status file is saved

    obth_method : str
        Name of connector class
    '''

    DEF_save_lim = 50
    DEF_unfound_lim = 150

    def __init__(self, stars_filters, save_path=None, stat_file_path=None,
                 save_lim=None, unfound_lim=None, obth_method=None):
        '''
        Parameters
        ----------
        stars_filters : lists
            Stars filters

        save_path : str
            Path from "run" module to the folder where found
            light curves will be saved

        stat_file_path : str
            Status file name

        save_lim : int
            Number of searched objects after which status file is saved

        obth_method : str
            Name of connector class
        '''

        # Default values warning and setting
        if not save_path:
            save_path = self.DEF_save_path
            warn("Path to the save folder was not specified.\nSetting default path: %s" % (
                save_path))
        if not save_lim:
            save_lim = self.DEF_save_lim

        if not unfound_lim:
            unfound_lim = self.DEF_unfound_lim

        if not obth_method:
            raise QueryInputError(
                "Database for searching need to be specified.")

        self.save_path = save_path
        self.stat_file_path = stat_file_path

        self.obth_method = obth_method
        self.save_lim = save_lim
        self.unfound_lim = unfound_lim

        self.stars_filters = stars_filters

        self.not_uploaded = []
        self.passed_stars = []

    def filterStar(self, star, *args, **kwargs):
        '''
        This method filter given star.
        In case of match method "matchOccured" will be performed

        Parameters
        ----------
        stars : `Star` instance
            Star to filter

        Returns
        -------
        bool
            If star passed thru filtering
        '''

        if self.stars_filters:
            for star_filt in self.stars_filters:
                result = star_filt.filterStars([star])
                if not result:
                    break

            if len(result) == 1:
                self.matchOccured(star)
                return True
            return False
        return True

    def matchOccured(self, star, *args, **kwargs):
        '''
        What to do with star which passed thru filtering

        Parameters
        ----------
        star : `Star` instance
            Star object which will be saved as fits

        Returns
        -------
            None
        '''
        saveStars([star], self.save_path)[0]
        self.passed_stars.append(star)

    def failProcedure(self, query, err=""):
        '''
        What to do if a fail occurs

        Parameters
        ----------
        query : optional
            Query informations

        err : str
            Error message

        Returns
        -------
            None
        '''
        raise
        warnings.warn("Error occurred during filtering: %s" % err)

    def statusFile(self, query, status, delimiter="\t"):
        '''
        This method generates status file for overall query in certain db.
        Every queried star will be noted.

        Parameters
        ----------
        query : dict
            Query informations

        status : dict
            Information whether queried star was found, filtered
            and passed thru filtering

        Returns
        -------
            None
        '''
        if not self.stat_file_path:
            return False
        try:
            empty_file = os.stat(self.stat_file_path).st_size == 0
        except OSError:
            empty_file = True

        with open(self.stat_file_path, "a") as status_file:
            if empty_file:
                status_file.write("#")
                for i, key in enumerate(query):
                    delim = delimiter
                    status_file.write(str(key) + delim)
                for i, key in enumerate(status):
                    if i >= len(status) - 1:
                        delim = ""
                    else:
                        delim = delimiter

                    status_file.write(str(key) + delim)
                status_file.write("\n")

            for i, key in enumerate(query):
                delim = delimiter

                status_file.write(str(query[key]) + delim)
            for i, key in enumerate(status):
                if i >= len(status) - 1:
                    delim = ""
                else:
                    delim = delimiter

                status_file.write(str(status[key]) + delim)
            status_file.write("\n")

    def queryStars(self, queries):
        '''
        Query db according to list of queries. Stars passed thru filter
        are managed by `matchOccured` method.

        Parameters
        ----------
        queries : list, iterable
            List of dictionaries of queries for certain db

        Returns
        -------
            None
        '''

        stars_num = 0
        passed_num = 0

        all_unfound = 0
        unfound_counter = 0
        for query in progressbar(queries, "Query: "):
            status = collections.OrderedDict(
                (("found", False), ("filtered", False), ("passed", False)))
            try:

                stars = StarsProvider().getProvider(
                    obtain_method=self.obth_method, **query).getStarsWithCurves()
            except QueryInputError:
                raise
            except:
                warn("Couldn't download any light curve")
                stars = []

            # Check if the searched star was found
            result_len = len(stars)
            if result_len == 0:
                unfound_counter += 1
                all_unfound += 1
                if unfound_counter > self.unfound_lim:
                    warn("Max number of unsatisfied queries reached: %i" %
                         self.unfound_lim)
                    break

            else:
                unfound_counter = 0
                for one_star in stars:
                    status["found"] = True

                    contain_lc = True
                    try:
                        stars[0].lightCurve.time
                    except AttributeError:
                        contain_lc = False

                    if contain_lc:
                        # Try to apply filters to the star
                        try:
                            passed = self.filterStar(one_star, query)
                            status["filtered"] = True
                            status["passed"] = passed
                            stars_num += 1
                            if passed:
                                passed_num += 1

                        except IOError as err:
                            raise InvalidFilesPath(err)
                        except Exception as err:
                            self.failProcedure(query, err)
                            warn(
                                "Something went wrong during filtering:\n\t%s" % err)
                    query["name"] = one_star.name
                    self.statusFile(query, status)

        print "\n************\t\tQuery is done\t\t************"
        print "Query results:\nThere are %i stars passed thru filtering from %s." % (passed_num, stars_num)
        if all_unfound:
            print "There are %i stars which was not found" % all_unfound
        if self.not_uploaded:
            print "\t%i stars have not been uploaded into local db, because they are already there." % len(self.not_uploaded)
