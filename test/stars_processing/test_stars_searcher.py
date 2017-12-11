import os
import pickle

import time

from lcc.stars_processing.systematic_search.stars_searcher import StarsSearcher, StarsSearcherRedis



def test_redis():
    with open(os.path.join(os.path.dirname(__file__), "../resources/test_filter.pickle"), "rb") as fi:
        st_filter = pickle.load(fi)
    searcher = StarsSearcherRedis([st_filter], db_connector="OgleII", save_path="/tmp/test_stars")

    queries = [{"field": "LMC_SC3", "starid": i} for i in range(1, 10)]
    searcher.queryStars(queries)

    assert len(searcher.getPassedStars()) > 0

    time.sleep(2)
    assert len(searcher.getStatus()) == len(queries)


def test_sequential():
    with open(os.path.join(os.path.dirname(__file__), "../resources/test_filter.pickle"), "rb") as fi:
        st_filter = pickle.load(fi)
    searcher = StarsSearcher([st_filter], save_path="/tmp", stat_file_path="/tmp/status.txt",
                             db_connector="OgleII", multiproc=False, save_coords=True)

    queries = [{"field": "LMC_SC3", "starid": i} for i in range(1, 10)]
    searcher.queryStars(queries)

    report = searcher.getStatus()
    assert len(searcher.getPassedStars()) > 0
    assert len(report) == len(queries)




