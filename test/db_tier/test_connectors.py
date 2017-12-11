import os

import numpy as np

from lcc.db_tier.connectors import OgleII
from lcc.db_tier.stars_provider import StarsProvider
from lcc.entities.star import Star
from lcc.utils.stars import saveStars


def check_lc(stars, n=None):
    if n is None:
        n = len(stars)

    assert n == len([1 for st in stars if st.lightCurve and len(st.lightCurve.mag)])


def test_FileManager():
    save_stars_path = "/tmp/test_FileManage/"
    path = os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "lcc_web", "sample_data", "sample1")
    stars = StarsProvider.getProvider("FileManager", {"path": path}).getStars()
    assert len(stars) > 0
    assert stars[0].lightCurve

    saveStars(stars, path=save_stars_path)

    stars_loaded = StarsProvider.getProvider("FileManager", {"path": save_stars_path}).getStars()

    assert stars == stars_loaded


def test_Macho():
    RESULTS_NUM = 1
    queries = [{"Field": 1, "Tile": 3441, "Seqn": 25}]
    client = StarsProvider().getProvider("Macho", queries)
    stars = client.getStars()
    assert len(stars) == RESULTS_NUM
    assert isinstance(stars[0], Star)
    check_lc(stars)
    assert len(stars) == 1
    assert len(stars[0].light_curves) == 2
    assert len(stars[0].light_curves[0].mag) == 1188
    assert len(stars[0].light_curves[1].mag) == 676


def test_Kepler():
    RESULTS_NUM = 4

    queries = [{"ra": 297.8399, "dec": 46.57427, "delta": 10, "nearest": True},
               {"kic_num": 9787239},
               {"kic_jkcolor": (0.3, 0.4), "max_records": 2}]

    client = StarsProvider().getProvider("Kepler", queries)
    stars = client.getStars()
    assert not np.isnan(stars[1].lightCurve.getHistogram()[1]).any()
    assert stars and len(stars) == RESULTS_NUM
    assert stars[1].name == "KIC_9787239"
    assert len(stars[1].lightCurve.time) == 1624


def test_CorotFaint():
    queries = [{"Corot": "102706554"},
               {"ra": 100.94235, "dec": -00.89651, "delta": 10}]
    client = StarsProvider().getProvider("CorotFaint", queries)
    stars = client.getStars(max_bins=1000)
    assert len(stars) > 0
    assert isinstance(stars[0], Star)
    check_lc(stars)


def test_CorotBright():
    RESULTS_NUM = 4

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
    # client = StarsProvider().getProvider("OgleII",  queries)
    client = OgleII(queries)
    client.multiproc = False
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


def skip_test_Asas():
    queries = [{"ASAS": "000030-3937.5"},
               {"ra": 10.08, "dec": -39.625, "delta": 20},
               {"ra": 0.1251, "dec": -39.6250, "delta": 10}]
    client = StarsProvider().getProvider("Asas", queries)
    stars = client.getStars()

    assert len(stars) > 0
    assert isinstance(stars[0], Star)
    check_lc(stars)
