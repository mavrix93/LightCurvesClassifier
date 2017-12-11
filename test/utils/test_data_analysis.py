import numpy as np
from lcc.utils.data_analysis import to_PAA, to_ekvi_PAA, compute_bins, fix_missing


def test_to_PAA():
    for _ in range(100):
        x = np.random.random_sample(np.random.randint(30, 700))

        bins = np.random.randint(5, 30)
        assert len(to_PAA(x, bins)[0]) == bins


def test_to_ekvi_PAA1():
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

        x1 = np.linspace(0, 1, n)
        y = np.random.random_sample(n)

        bins = np.random.randint(5, 30)

        x_ekv1, y_ekv1 = to_ekvi_PAA(x, y,  bins)
        x_ekv2, y_ekv2 = to_ekvi_PAA(x, y, len(x))
        x_ekv3, y_ekv3 = to_ekvi_PAA(x, y, 3 * len(x))
        x_ekv4, y_ekv4 = to_ekvi_PAA(x1, y, len(x1))

        assert len(x_ekv1) == bins
        assert len(x_ekv2) == len(x)
        assert len(x_ekv3) == len(x)
        assert np.nan not in y_ekv1
        assert np.nan not in y_ekv2
        assert np.nan not in y_ekv3
        assert (y_ekv4 == y).all()

        thr = 0.1
        assert abs(y_ekv1.mean() - y.mean()) / (y_ekv1.mean() + y.mean()) < thr
        assert abs(y_ekv2.mean() - y.mean()) / (y_ekv2.mean() + y.mean()) < thr
        assert abs(y_ekv3.mean() - y.mean()) / (y_ekv3.mean() + y.mean()) < thr


def test_compute_bins():
    x1 = [1, 2, 3, 8, 9, 10]
    x2 = [1, 2, 3, 4, 5, 6]

    assert compute_bins(x2, days_per_bin=1.9, set_min=2) == 3
    assert compute_bins(x1, days_per_bin=3, set_min=2) == 3


def test_fix_missing():
    x = np.linspace(0, 10, 20)
    y = x.copy()
    x[:5] = np.linspace(-15, -10, 5)

    xx, yy = to_ekvi_PAA(x, y)
    yy[0] = np.nan
    yy[-1] = np.nan

    res1 = fix_missing(xx, yy, replace_at_borders=False)

    assert len(res1[0]) == len(res1[1])
    assert len(res1[0]) == len(xx) - 2
    assert not np.isnan(res1[0]).any()
    assert not np.isnan(res1[1]).any()

    res2 = fix_missing(xx, yy, replace_at_borders=True)

    assert len(res2[0]) == len(res2[1])
    assert len(res2[0]) == len(xx)
    assert not np.isnan(res2[0]).any()
    assert not np.isnan(res2[1]).any()
    assert res2[1][0] == res2[1][1]
    assert res2[1][-2] == res2[1][-1]

    # assert res1[0] == res2[0]
