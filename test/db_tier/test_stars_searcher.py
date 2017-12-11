

from lcc.db_tier.connectors.ogleII import OgleII
from lcc.db_tier.stars_provider import StarsProvider


def test_OgleII():
    que2 = {"field": "LMC_SC3", "starid": 5}

    queries = [{"field": "LMC_SC3", "starid": i} for i in range(1, 5)]
    prov = StarsProvider.getProvider("OgleII", queries)
    stars = prov.getStars()


def test_OgleIII():
    que1 = {"ra": 72.798405,
            "dec": -69.00918, "delta": 5, "nearest": True}

    que3 = {"field": "LMC135.5", "starid": 19670}

    client = StarsProvider().getProvider("OgleIII", [que1, que3])
    stars = client.getStars()

    assert len(stars) == 2
    assert len(stars[0].lightCurve.mag) == 370
    assert len(stars[1].lightCurve.mag) == 370
