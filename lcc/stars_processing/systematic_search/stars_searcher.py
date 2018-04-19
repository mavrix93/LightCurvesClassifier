import os
import tempfile
import time
import warnings
from abc import ABC

import pandas as pd
import redis
from rq import Queue

from lcc.db_tier.connectors import FileManager
from lcc.db_tier.stars_provider import StarsProvider
from lcc.entities.exceptions import QueryInputError
from lcc.utils.helpers import random_string
from lcc.utils.stars import saveStars


class BaseStarsSearcher(ABC):

    def filterStar(self, star):
        """
        This method filter given star.
        In case of match method "matchOccured" will be performed

        Parameters
        ----------
        star : `Star` instance
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

    def matchOccured(self, star):
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
        print("Saving star to", self.save_path)
        if self.save_path:
            saveStars([star], self.save_path)

    def queryStar(self, query):
        stars = StarsProvider.getProvider(self.db_connector, query).getStars()
        status = {"found": [], "lc": [], "passed": [], "star_name": []}
        passed_info = None
        if stars:
            stars_with_lc = []

            for star in stars:
                status["star_name"].append(star.name)
                status["found"].append(True)
                if star.lightCurve and len(star.lightCurve.mag):
                    status["lc"].append(True)
                    stars_with_lc.append(star)
                else:
                    status["lc"].append(False)

            # TODO: Support just one filter
            # for star_filter in self.stars_filters:
            if self.stars_filters:
                passed_info = self.stars_filters[0].getAllPredictions(stars_with_lc, with_features=self.save_coords,
                                                                      check_passing=True)

            counter = 0
            for i in range(len(stars)):
                print("passed_info is none", passed_info is None)
                if passed_info is None and status["lc"][i]:
                    status["passed"].append(True)
                    self.matchOccured(stars[i])

                elif status["lc"][i]:
                    p = passed_info["passed"].values[counter]
                    status["passed"].append(p)
                    counter += 1
                    if p:
                        self.matchOccured(stars[i])
                else:
                    status["passed"].append(False)

        else:
            status["found"].append(False)
            status["lc"].append(False)
            status["passed"].append(False)
            status["star_name"].append("Noname")
        self.uploadStatus(status, passed_info)

    def getPassedStars(self):
        return FileManager({"path": self.save_path}).getStars()


class StarsSearcher(BaseStarsSearcher):
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

    def __init__(self, stars_filters, save_path=None, stat_file_path=None,
                 db_connector=None, save_coords=False, multiproc=False):
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

        db_connector : str
            Name of connector class

        save_coords : bool
            Save params space coordinates of inspected stars
            
        multiproc : bool, int
            If True task will be distributed into threads by using all cores. If it is number,
            just that number of cores are used
        """
        if not db_connector:
            raise QueryInputError(
                "Database for searching need to be specified.")

        save_path = save_path or os.path.join(tempfile.gettempdir(), "lcc", "stars")
        stat_file_path = stat_file_path or os.path.join(tempfile.gettempdir(), "lcc", "status_file.csv")

        self.save_path = save_path
        self.stat_file_path = stat_file_path
        self.db_connector = db_connector
        self.stars_filters = stars_filters

        if multiproc:
            warnings.warn("Multiprocessing not supported in current version")
            multiproc = False

        self.multiproc = multiproc
        self.save_coords = save_coords

        if os.path.exists(stat_file_path):
            warnings.warn("Removing existing status file {}".format(stat_file_path))
            os.remove(stat_file_path)

    def uploadStatus(self, status, passed_info):
        """
        This method generates status file for overall query in certain db.
        Every queried star will be noted.

        Parameters
        ----------
        status : dict
            Information whether queried star was found, filtered
            and passed thru filtering

        passed_info:

        Returns
        -------
            None
        """

        status_df = pd.DataFrame(status)
        if passed_info is not None:
            status_df = pd.merge(status_df, passed_info)
        status_df = status_df.sort_index(axis=1)

        if self.stat_file_path:
            if not os.path.isfile(self.stat_file_path):
                status_df.to_csv(self.stat_file_path, index=False)
            else:
                status_df.to_csv(self.stat_file_path, index=False, mode='a', header=False)

    def getStatus(self):
        return pd.read_csv(self.stat_file_path)

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
        [self.queryStar(query) for query in queries]

    # TODO: Remove
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


connection = redis.Redis(host=os.environ.get("LCC_REDIS_HOST", "localhost"),
                         port=os.environ.get("LCC_REDIS_PORT", 6379))
queue = Queue(name=os.environ.get("LCC_QUEUE_NAME", "lcc"), connection=connection)


class StarsSearcherRedis(BaseStarsSearcher):

    def __init__(self, stars_filters, db_connector, save_path=None, job_name=None, save_coords=False):

        self.stars_filters = stars_filters
        self.db_connector = db_connector
        self.save_coords = save_coords
        self.job_name = job_name or "job_" + random_string(32)
        self.save_path = save_path or os.path.join(tempfile.gettempdir(), "lcc", "stars")

    def queryStars(self, queries):
        print("lets go")
        # [self.queryStar(query) for query in queries]
        for i, query in enumerate(queries):
            queue.enqueue(self.queryStar, query=query)

    def uploadStatus(self, status, passed_info):
        if passed_info is not None:
            passed_info = passed_info.to_dict("list")
        counter = -1
        for i in range(len(status["star_name"])):
            # assert status["passed"][i] == passed_info["passed"][counter]

            for key in status.keys():
                connection.lpush(self._get_label(key), status[key][i])

            if passed_info is not None:
                if status["passed"][i]:
                    counter += 1
                    for key in passed_info.keys():
                        if key != "passed":
                            connection.lpush(self._get_label(key), passed_info[key][counter])

                else:
                    for key in passed_info.keys():
                        if key != "passed":
                            connection.lpush(self._get_label(key), None)

    def getPassedStars(self, wait=True, timeout=None, verbose=True):
        self._wait_to_done(wait=wait, timeout=timeout, verbose=verbose)
        return super(StarsSearcherRedis, self).getPassedStars()

    def getStatus(self, wait=True, timeout=None, verbose=True):
        self._wait_to_done(wait=wait, timeout=timeout, verbose=verbose)
        data = {}
        for key in self._get_all_keys():
            data[self._parse_column_name(key)] = [x.decode("utf-8") for x in
                                                  connection.lrange(key, 0, connection.llen(key))]

        return pd.DataFrame(data)

    def _get_all_keys(self):
        prefix = "lcc:{}".format(self.job_name)
        return [key.decode("utf-8") for key in connection.keys("{}*".format(prefix))]

    def _parse_column_name(self, key):
        return key[len("lcc:{}".format(self.job_name)) + 1:]

    def _get_label(self, key):
        return "lcc:{}:{}".format(self.job_name, key)

    def _remaining_jobs(self):
        return len(queue.job_ids)

    def _wait_to_done(self, wait=True, timeout=None, verbose=True):
        if wait:
            waited_s = 0
            while True:
                n_remaining = self._remaining_jobs()
                if verbose:
                    print("Remaining jobs: {}".format(n_remaining))

                if n_remaining == 0:
                    return True

                if timeout and waited_s > timeout:
                    raise TimeoutError("Waiting took {} s, but still {} jobs remaining".format(waited_s, n_remaining))

                time.sleep(1)
                waited_s += 1
