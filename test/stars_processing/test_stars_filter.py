import pickle
import os

import numpy as np
from lcc.stars_processing.deciders import LDADec, QDADec

from lcc.entities.star import Star
from lcc.stars_processing.descriptors.abbe_value_descr import AbbeValueDescr
from lcc.stars_processing.stars_filter import StarsFilter


def setup():
    descriptors = [AbbeValueDescr()]
    # deciders = [NeuronDecider(maxEpochs=800)]
    deciders = [LDADec(), QDADec()]
    s_stars = [Star(name="Searched_{}".format(i)) for i in range(100)]
    c_stars = [Star(name="Contam_{}".format(i)) for i in range(100)]
    m_stars = [Star(name="Contam_{}".format(i)) for i in range(100)]

    x = np.linspace(0, 10, 100)
    for st in s_stars:
        st.putLightCurve([x, np.cos(x) - 0.5 + np.random.random_sample(100)])

    for st in c_stars:
        st.putLightCurve([x, np.exp(x*np.random.random_sample(100))])

    filt = StarsFilter(descriptors, deciders)
    return s_stars, c_stars, m_stars, filt


def test_getAllPredictions():
    s_stars, c_stars, m_stars, filt = setup()
    filt.learn(s_stars[:80], c_stars[:80])

    sx = filt.getAllPredictions(s_stars[80:], with_features=True, check_passing=True)
    cx = filt.getAllPredictions(c_stars[80:], with_features=True, check_passing=True)

    assert sx.columns.tolist() == cx.columns.tolist() == ["Abbe value", "LDADec", "QDADec", "passed_LDADec",
                                                          "passed_QDADec", "passed"]
    assert sx["passed"].sum() > cx["passed"].sum()

    # FIXME: Can't handle missing light curves
    # mx = filt.getAllPredictions(m_stars, with_features=True, check_passing=True)


def test_filtering():
    s_stars, c_stars, _, filt = setup()

    filt.learn(s_stars[:80], c_stars[:80])

    ps = filt.evaluateStars(s_stars[80:])
    cs = filt.evaluateStars(c_stars[80:])

    s_coo = filt.getSpaceCoordinates(s_stars)
    c_coo = filt.getSpaceCoordinates(c_stars)

    assert ps.mean() - cs.mean() > ps.std() + cs.std()

    assert c_coo["Abbe value"].mean() - s_coo["Abbe value"].mean() > c_coo["Abbe value"].std() + s_coo[
        "Abbe value"].std()

    ev = filt.getEvaluations(c_stars)

    with open(os.path.join(os.path.dirname(__file__), "../resources/test_filter.pickle"), "wb") as fi:
        pickle.dump(filt, fi)

