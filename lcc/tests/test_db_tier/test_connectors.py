import warnings

import numpy as np

from lcc.db_tier.stars_provider import StarsProvider
from lcc.entities.star import Star


def check_lc(stars, n=None):
    if n is None:
        n = len(stars)

    assert n == len([1 for st in stars if st.lightCurve])


def test_Macho():
    RESULTS_NUM = 1
    queries = [{"Field": 1, "Tile": 3441, "Seqn": 25}]
    client = StarsProvider().getProvider("Macho", queries)
    stars = client.getStars()
    assert len(stars) == RESULTS_NUM
    assert isinstance(stars[0], Star)
    check_lc(stars)


def test_Kepler():
    RESULTS_NUM = 4

    queries = [{"ra": 297.8399, "dec": 46.57427, "delta": 10, "nearest": True},
               {"kic_num": 9787239},
               {"kic_jkcolor": (0.3, 0.4), "max_records": 2}]

    client = StarsProvider().getProvider("Kepler", queries)
    stars = client.getStars()
    assert not np.isnan(stars[1].lightCurve.getHistogram()[1]).any()
    assert stars and len(stars) == RESULTS_NUM
    check_lc(stars, 1)


def test_CorotFaint():
    queries = [{"Corot": "102706554"},
               {"ra": 100.94235, "dec": -00.89651, "delta": 10}]
    client = StarsProvider().getProvider("CorotFaint", queries)
    stars = client.getStars(max_bins=1000)
    assert len(stars) > 0
    assert isinstance(stars[0], Star)
    check_lc(stars)


def test_CorotBright():
    RESULTS_NUM = 2

    queries = [{"ra": 102.707, "dec": -0.54089, "delta": 10},
               {"CoRot": 116}]
    client = StarsProvider().getProvider("CorotBright", queries)

    stars = client.getStars(max_bins=100)
    assert len(stars) == RESULTS_NUM
    assert isinstance(stars[0], Star)
    check_lc(stars, 4)


def test_OgleII():
    queries = [{"starid": 2, "field_num": 1, "target": "lmc"},
               {"ra": 5.545575 * 15, "dec": -70.55272, "delta": 3}]
    client = StarsProvider().getProvider("OgleII",  queries)
    stars = client.getStars()

    assert len(stars) == 3
    assert isinstance(stars[0], Star)

    check_lc(stars, 3)


def test_OgleIII():
    que1 = {"ra": 72.798405,
            "dec": -69.00918, "delta": 5, "nearest": True}
    que3 = {"field": "LMC135.5", "starid": 19670}
    client = StarsProvider().getProvider("OgleIII",  [que1, que3])
    stars = client.getStars()

    assert len(stars) == 2
    assert isinstance(stars[0], Star)
    check_lc(stars)


def test_Asas():
    queries = [{"ASAS": "000030-3937.5"},
               {"ra": 10.08, "dec": -39.625, "delta": 20},
               {"ra": 0.1251, "dec": -39.6250, "delta": 10}]
    client = StarsProvider().getProvider("Asas", queries)
    stars = client.getStars()

    assert len(stars) > 0
    assert isinstance(stars[0], Star)
    check_lc(stars)
