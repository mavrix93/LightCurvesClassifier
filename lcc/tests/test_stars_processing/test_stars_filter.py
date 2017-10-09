import numpy as np

from lcc.entities.star import Star
from lcc.stars_processing.deciders.neuron_decider import NeuronDecider
from lcc.stars_processing.descriptors.abbe_value_descr import AbbeValueDescr
from lcc.stars_processing.stars_filter import StarsFilter


def test_filtering():

    descriptors = [AbbeValueDescr()]
    deciders = [NeuronDecider(maxEpochs=800)]
    s_stars = [Star(name="Searched_{}".format(i)) for i in range(100)]
    c_stars = [Star(name="Contam_{}".format(i)) for i in range(100)]

    x = np.linspace(0, 10, 100)
    for st in s_stars:
        st.putLightCurve([x, np.cos(x) - 0.5 + np.random.random_sample(100)])

    for st in c_stars:
        st.putLightCurve([x, np.exp(x*np.random.random_sample(100))])

    filt = StarsFilter(descriptors, deciders)
    filt.learn(s_stars[:80], c_stars[:80])

    ps = filt.evaluateStars(s_stars[80:])
    cs = filt.evaluateStars(c_stars[80:])

    s_coo = filt.getSpaceCoordinates(s_stars)
    c_coo = filt.getSpaceCoordinates(c_stars)

    assert ps.mean() - cs.mean() > ps.std() + cs.std()

    assert c_coo["Abbe value"].mean() - s_coo["Abbe value"].mean() > c_coo["Abbe value"].std() + s_coo[
        "Abbe value"].std()

