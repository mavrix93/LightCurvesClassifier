from lcc.stars_processing.systematic_search.stars_searcher import StarsSearcher
import pickle
import os


def test():
    with open(os.path.join(os.path.dirname(__file__), "../resources/test_filter.pickle"), "rb") as fi:
        st_filter = pickle.load(fi)
    searcher = StarsSearcher([st_filter], save_path="/tmp", stat_file_path="/tmp/status.txt",
                             obth_method="OgleII", multiproc=False)

    queries = [{"field": "LMC_SC3", "starid": i} for i in range(1, 10)]
    searcher.queryStars(queries)

    assert len(searcher.stars) == len(queries)

