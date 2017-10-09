import numpy as np
from lcc.utils.data_analysis import to_PAA, to_ekvi_PAA, compute_bins


def test_to_PAA():
    for _ in range(100):
        x = np.random.random_sample(np.random.randint(30, 700))

        bins = np.random.randint(5, 30)
        assert len(to_PAA(x, bins)[0]) == bins


def test_to_ekvi_PAA():
    n = 100
    x = np.linspace(0, 1, n)
    y = np.random.random_sample(n)

    bins = np.random.randint(5, 30)

    x_ekv1, y_ekv1 = to_ekvi_PAA(x, y,  bins)
    x_ekv2, y_ekv2 = to_ekvi_PAA(x, y, len(x))
    x_ekv3, y_ekv3 = to_ekvi_PAA(x, y, 3 * len(x))

    assert len(x_ekv1) == bins
    assert len(x_ekv2) == len(x)
    assert len(x_ekv3) == len(x)
    assert np.nan not in y_ekv1
    assert np.nan not in y_ekv2
    assert np.nan not in y_ekv3
    assert (y_ekv3 == y).all()
    assert (y_ekv2 == y).all()

    for _ in range(100):
        n = np.random.randint(30, 700)
        x = np.random.random_sample(n)
        y = np.random.random_sample(n)

        bins = np.random.randint(5, 30)

        x_ekv1, y_ekv1 = to_ekvi_PAA(x, y,  bins)
        x_ekv2, y_ekv2 = to_ekvi_PAA(x, y, len(x))
        x_ekv3, y_ekv3 = to_ekvi_PAA(x, y, 3 * len(x))

        assert len(x_ekv1) == bins
        assert len(x_ekv2) == len(x)
        assert len(x_ekv3) == len(x)
        assert np.nan not in y_ekv1
        assert np.nan not in y_ekv2
        assert np.nan not in y_ekv3
        assert (y_ekv3 == y).all()
        assert (y_ekv2 == y).all()


def test_compute_bins():
    x1 = [1, 2, 3, 8, 9, 10]
    x2 = [1, 2, 3, 4, 5, 6]

    assert compute_bins(x2, days_per_bin=2, set_min=2) == 3
    assert compute_bins(x1, days_per_bin=3, set_min=2) == 3

