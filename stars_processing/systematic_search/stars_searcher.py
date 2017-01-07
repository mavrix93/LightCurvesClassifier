import collections
import os
from warnings import warn
import warnings

from conf import settings
from conf.settings import VERBOSITY, TO_THE_DATA_FOLDER, LC_FOLDER
from db_tier.stars_provider import StarsProvider
from entities.exceptions import QueryInputError, InvalidFilesPath
from stars_processing.filtering_manager import FilteringManager
from utils.helpers import verbose, progressbar, create_folder
from utils.stars import saveStars


# TODO: Think more about propriety of location of this class
# TODO: Make this class general for every db manager
class StarsSearcher():
    '''
    The class manages systematic searching in databases. It also can be used
    as base class for other star searchers.

    Attributes
    ----------
    filters_list : list, iterable
        List of star filters

    save_path : str
        Path from "run" module to the folder where found
        light curves will be saved

    save_lim : int
        Number of searched objects after which status file is saved

    obth_method : str
        Name of connector class
    '''

    DEF_save_path = TO_THE_DATA_FOLDER + LC_FOLDER
    DEF_save_lim = 50
    DEF_unfound_lim = 150

    def __init__(self, filters_list, save_path=None, save_lim=None,
                 unfound_lim=None, obth_method=None, *args, **kwargs):
        '''
        Parameters
        ----------
        filters_list : list, iterable
            List of star filters

        save_path : str
            Path from "run" module to the folder where found
            light curves will be saved

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
            warn(
                "Save limit was not specified.\nSetting default value: %i" % save_lim)
        if not unfound_lim:
            unfound_lim = self.DEF_unfound_lim
            warn(
                "Max number of failed queries in order to end searching need to be specified.\nSetting default value: %i" % unfound_lim)
        if not obth_method:
            raise QueryInputError(
                "Database for searching need to be specified.")

        self.filteringManager = FilteringManager()

        # Load all filters from given list
        for filt in filters_list:
            self.filteringManager.loadFilter(filt)

        if save_path.startswith("HERE:"):
            save_path = save_path[5:]
        else:
            save_path = os.path.join(settings.LC_FOLDER, save_path)
        if os.path.isdir(save_path):
            self.save_path = save_path
        else:
            save_path = os.path.join(settings.LC_FOLDER, save_path)
            try:
                create_folder(save_path)
                self.save_path = save_path
                warnings.warn(
                    "Output folder %s was created because it has not existed.\n" % (save_path))
            except:
                warnings.warn("Invalid save path. Current folder was set")
                self.save_path = "."

        self.obth_method = obth_method
        self.save_lim = save_lim
        self.unfound_lim = unfound_lim

        filt_name = ""
        for filt in filters_list:
            filt_name += "_" + filt.__class__.__name__
        self.filt_name = filt_name

        self.not_uploaded = []

    def filterStar(self, star, *args, **kwargs):
        '''
        This method filter given star in list.
        In case of match method "matchOccur" will be performed

        Parameters
        ----------
        stars : `Star` instance
            Star to filter

        Returns
        -------
        bool
            If star passed thru filtering
        '''

        self.filteringManager.stars = [star]

        # Get stars passed thru filtering
        result = self.filteringManager.performFiltering()

        if len(result) == 1:
            self.matchOccur(result[0])
            return True
        elif len(result) > 1:
            raise Exception(
                "One star has entered to filtering phase, but more then have passed ?!?!")
        return False

    # NOTE: Default behavior. It can be overridden.
    def matchOccur(self, star, *args, **kwargs):
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
        verbose(star, 2, VERBOSITY)
        saveStars([star], self.save_path)[0]

    # NOTE: Default behavior. It can be overwritten.
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
        warnings.warn("Error occurred during filtering: %s" % err)

    # NOTE: Default behavior. It can be overwritten.
    def statusFile(self, query, status):
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

        file_name = os.path.join(
            self.save_path, "%s%s.txt" % (self.obth_method, self.filt_name))
        try:
            empty_file = os.stat(file_name).st_size == 0
        except OSError:
            empty_file = True

        with open(file_name, "a") as status_file:
            if empty_file:
                status_file.write("#")
                for i, key in enumerate(query):
                    delim = settings.FILE_DELIM
                    status_file.write(str(key) + delim)
                for i, key in enumerate(status):
                    if i >= len(status) - 1:
                        delim = ""
                    else:
                        delim = settings.FILE_DELIM

                    status_file.write(str(key) + delim)
                status_file.write("\n")

            for i, key in enumerate(query):
                delim = settings.FILE_DELIM

                status_file.write(str(query[key]) + delim)
            for i, key in enumerate(status):
                if i >= len(status) - 1:
                    delim = ""
                else:
                    delim = settings.FILE_DELIM

                status_file.write(str(status[key]) + delim)
            status_file.write("\n")

    def queryStars(self, queries):
        '''
        Query db according to list of queries. Stars passed thru filter
        are managed by `matchOccur` method.

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
                raise
                warn("Couldn't download any light curve")
                stars = []

            # Check if searched star was found
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
                            # TODO: Case of multiple stars, not just one as
                            # assumed
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
                            warn("Something went wrong during filtering")
                    query["name"] = one_star.name
                    self.statusFile(query, status)

        print "\n************\t\tQuery is done\t\t************"
        print "Query results:\nThere are %i stars passed thru filtering from %s." % (passed_num, stars_num)
        if all_unfound:
            print "There are %i stars which was not found" % all_unfound
        if self.not_uploaded:
            print "\t%i stars have not been uploaded into local db, because they are already there." % len(self.not_uploaded)
