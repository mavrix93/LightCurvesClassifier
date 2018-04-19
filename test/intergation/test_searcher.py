import time
import numpy as np


from lcc.entities.star import Star
from lcc.stars_processing.deciders import LDADec, QDADec, GradBoostDec
from lcc.stars_processing.descriptors import AbbeValueDescr
from lcc.stars_processing.stars_filter import StarsFilter
from lcc.stars_processing.systematic_search.stars_searcher import StarsSearcherRedis
from lcc.stars_processing.systematic_search.worker import run_workers


def test():
    descriptors = [AbbeValueDescr()]
    # deciders = [NeuronDecider(maxEpochs=800)]
    deciders = [LDADec(), QDADec(), GradBoostDec()]
    s_stars = [Star(name="Searched_{}".format(i)) for i in range(100)]
    c_stars = [Star(name="Contam_{}".format(i)) for i in range(100)]

    x = np.linspace(0, 10, 100)
    for st in s_stars:
        st.putLightCurve([x, np.cos(x) - 0.5 + np.random.random_sample(100)])

    for st in c_stars:
        st.putLightCurve([x, np.exp(x*np.random.random_sample(100))])

    filt = StarsFilter(descriptors, deciders)
    filt.learn(s_stars, c_stars)

    searcher = StarsSearcherRedis([filt], db_connector="OgleII", save_path="/tmp/test_stars")

    queries = [{"field": "LMC_SC3", "starid": i} for i in range(1, 10)]
    searcher.queryStars(queries)

    run_workers(n_workers=1)

    assert len(searcher.getPassedStars()) > 0

    time.sleep(2)
    assert len(searcher.getStatus()) == len(queries)