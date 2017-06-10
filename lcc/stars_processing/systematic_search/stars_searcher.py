import collections
import os
import warnings
from warnings import warn
import logging

import pathos.multiprocessing as multiprocessing
import pandas as pd
import time

import sys
from lcc.db_tier.stars_provider import StarsProvider
from lcc.entities.exceptions import QueryInputError, InvalidFilesPath
from lcc.utils.stars import saveStars
import tqdm

logger = logging.getLogger(__name__)


class StarsSearcher:
    """
    The class manages systematic searching in databases. It also can be used
    as base class for other star searchers.

    Attributes
    ----------
    stars_filters : FilteringManager object
        Filter which is prepared filter star objects

    save_path : bool, str
        Path from "run" module to the folder where found
        light curves will be saved

    stat_file_path : str
        Status file name

    save_coords : bool
        Save params space coordinates of inspected stars

    status : pandas.DataFrame
        Status table about results of queries
        
    multiproc : bool, int
        If True task will be distributed into threads by using all cores. If it is number,
        just that number of cores are used
    """

    def __init__(self, stars_filters, save_path=False, stat_file_path=None,
                 obth_method=None, save_coords=None, multiproc=True):
        """
        Parameters
        ----------
        stars_filters : lists
            Stars filters

        save_path : bool, str
            Path from "run" module to the folder where found
            light curves will be saved. If False nothing is saved.

        stat_file_path : str
            Status file name

        obth_method : str
            Name of connector class

        save_coords : bool
            Save params space coordinates of inspected stars
            
        multiproc : bool, int
            If True task will be distributed into threads by using all cores. If it is number,
            just that number of cores are used
        """
        if not obth_method:
            raise QueryInputError(
                "Database for searching need to be specified.")

        self.save_path = save_path
        self.stat_file_path = stat_file_path

        self.obth_method = obth_method

        self.stars_filters = stars_filters

        self.not_uploaded = []
        self.passed_stars = []

        if save_coords:
            self.que_coords = None
        self.save_coords = save_coords

        self.status = pd.DataFrame()

        self.multiproc = multiproc
        self.overview = []
        self.stars = []

    def filterStar(self, star, *args, **kwargs):
        """
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
        """
        for star_filt in self.stars_filters:
            result = star_filt.filterStars([star])
            if not result:
                break

        if not self.stars_filters or len(result) == 1:
            self.matchOccured(star)
            return True
        else:
            return False

    def matchOccured(self, star, *args, **kwargs):
        """
        What to do with star which passed thru filtering

        Parameters
        ----------
        star : `Star` instance
            Star object which will be saved as fits

        Returns
        -------
            None
        """
        if self.save_path:
            saveStars([star], self.save_path)[0]
        self.passed_stars.append(star)

    def failProcedure(self, query, err=""):
        """
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
        """
        warnings.warn("Error occurred during filtering: %s" % err)

    def statusFile(self, query, status, delimiter="\t"):
        """
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
        """
        data = [query.pop("name")] + query.values() + status.values()
        columns = ["name"] + query.keys() + status.keys()

        this_status = pd.DataFrame(
            [data], columns=columns, index=[len(self.status)])
        self.status = self.status.append(this_status)

        if self.stat_file_path:
            if not os.path.isfile(self.stat_file_path):
                self.status.to_csv(self.stat_file_path, index=False)
            else:
                self.status.to_csv(self.stat_file_path, index=False, mode='a', header=False)                

    def queryStars(self, queries):
        """
        Query db according to list of queries. Stars passed thru filter
        are managed by `matchOccured` method.

        Parameters
        ----------
        queries : list, iterable
            List of dictionaries of queries for certain db

        Returns
        -------
            None
        """
        if self.multiproc:
            if self.multiproc is True:
                n_cpu = multiprocessing.cpu_count()
            else:
                n_cpu = self.multiproc

            pool = multiprocessing.Pool(n_cpu)

            result = pool.map_async(self.queryStar, queries)
            pool.close()  # No more work
            n = len(queries)
            while True:
                if result.ready():
                    break
                sys.stderr.write('\rProcessed stars: {0} / {1}'.format(n - result._number_left,  n))

                time.sleep(0.6)
            result = result.get()
            sys.stderr.write('\rAll {0} stars have been processed'.format(n))
            # result = pool.map(self.queryStar, queries)
        else:
            result = [self.queryStar(q) for q in queries]

        passed_num = 0
        not_found = 0
        stars_n = 0
        stars = []
        overview = []
        for res_stars, status in result:
            if res_stars:
                stars += res_stars
                stars_n += len(res_stars)
            else:
                not_found += 1
            if status.get("passed"):
                passed_num += 1
            overview.append(status)

        print "\n************\t\tQuery is done\t\t************"
        print "Query results:\nThere are %i stars passed thru filtering from %s." % (passed_num, stars_n)
        if not_found:
            print "There are %i unsatisfied queries" % not_found
        if self.not_uploaded:
            print "\t%i stars have not been uploaded into local db, because they are already there." % len(self.not_uploaded)

        self.overview = pd.DataFrame(overview)
        self.stars = stars

    def queryStar(self, query):
        status = collections.OrderedDict(
            (("found", False), ("lc", False), ("passed", False)))
        try:
            provider = StarsProvider().getProvider(self.obth_method, query)
            if hasattr(provider, "multiproc"):
                provider.multiproc = False

            stars = provider.getStars()

        except QueryInputError:
            raise
        except (KeyboardInterrupt, SystemExit):
            raise

        except Exception as e:
            warn(str(e))
            warn("Couldn't download any star for query %s" % query )
            stars = []

        # TODO: status attribute is rewrited and just status of the last star is noted
        for one_star in stars:
            status["found"] = True
            contain_lc = True

            try:
                one_star.lightCurve.time
            except AttributeError:
                contain_lc = False

            if contain_lc:

                # TODO
                if self.save_coords and self.stars_filters:
                    spc = self.stars_filters[
                        0].getSpaceCoordinates([one_star]).values
                    if len(spc):
                        self._saveCoords([one_star.name] + spc[0].tolist())

                # Try to apply filters to the star
                try:
                    passed = self.filterStar(one_star, query)
                    status["lc"] = True
                    status["passed"] = passed

                except (KeyboardInterrupt, SystemExit):
                    raise
                except IOError as err:
                    raise InvalidFilesPath(err)
                except Exception as err:
                    self.failProcedure(query, err)
                    warn(
                        "Something went wrong during filtering:\n\t%s" % err)
            else:
                status["lc"] = False
                status["passed"] = False

            query["name"] = one_star.name
            self.statusFile(query, status)
        if not stars:
            query["name"] = ""
            self.statusFile(query, status)

        return stars, status

    def _saveCoords(self, query):
        if self.stars_filters:
            star_filter = self.stars_filters[0]

            labels = []
            for desc in star_filter.descriptors:
                if hasattr(desc.LABEL, "__iter__"):
                    labels += desc.LABEL
                else:
                    labels.append(desc.LABEL)

            header = ["star_name"] + labels

            this_df = pd.DataFrame([query], columns=header)
            if not isinstance(self.que_coords, pd.DataFrame):
                self.que_coords = this_df
            self.que_coords = self.que_coords.append(this_df)

            self.que_coords.to_csv(
                os.path.join(self.save_path, "..", "space_coordinates.csv"), index=False, sep=";")
        else:
            warnings.warn(
                "There are no filters, so space coordinates cannot be obtained.\n")
