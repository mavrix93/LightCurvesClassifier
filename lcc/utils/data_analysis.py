"""
There are functions for processing data series
"""



import logging
import math
import warnings

import numpy as np


def to_PAA(x, bins):
    """
    Function performs Piecewise Aggregate Approximation on data set, reducing
    the dimension of the dataset x to w discrete levels. returns the reduced
    dimension data set, as well as the indicies corresponding to the original
    data for each reduced dimension

    Parameters
    ----------
    x : list, array, iterable
        1D serie of values

    bins : int
        Dimension of reduced data

    Returns
    -------
    numpy.array
        Approximated data serie

    list
        Indices
    """

    n = len(x)
    stepFloat = n / float(bins)
    step = int(math.ceil(stepFloat))
    frameStart = 0
    approximation = []
    indices = []
    i = 0
    while frameStart <= n - step:
        thisFrame = np.array(x[frameStart:int(frameStart + step)])
        approximation.append(np.mean(thisFrame))
        indices.append((frameStart, int(frameStart + step)))
        i += 1
        frameStart = int(i * stepFloat)
    return np.array(approximation), indices


def to_ekvi_PAA(x, y, bins=None, days_per_bin=None, max_bins=None,
                fix_nans=True, mean_time=True):
    """
    This method perform PAA (see above) on y data set, but it will consider
    different time steps between values (in x data set) and return corrected
    data set.

    Parameters
    ----------
    x : list, numpy.array, iterable
        Times which is treated as template for transformation `y` values

    y : list, numpy.array, iterable
        List of values

    bins : int, float
        Dimension of result data, also can be percentage number (0, 1)

    days_per_bin : float
        This value can be used for calculating bins

    Returns
    -------
    list
        Reduced `x` data

    list
        Reduced `y` data
    """
    if not bins:
        bins = 1

    if 0 < bins <= 1:
        bins = int(len(x) * bins)

    if isinstance(x, list):
        x = np.array(x)
        y = np.array(y)

    if not days_per_bin:
        if not bins:
            bins = len(x)

    else:
        bins = (x[-1] - x[0]) / days_per_bin

        if bins > len(x):
            bins = len(x)

    if not len(x) == len(y):
        raise Exception("X and Y have no same length (%i and %i" % (len(x), len(y)))

    if bins > len(x):
        warnings.warn("Bin number can't be higher then sample size. Setting to sample size")
        bins = len(x)

    if max_bins and bins > max_bins * len(x):
        warnings.warn("Bin number is higher max_bins. Setting to max size")
        bins = int(len(x) * max_bins)

    xmax = x.max()
    xmin = x.min()
    half_step = (xmax - xmin) / bins / 2.
    x_aprox = []
    y_aprox = []
    borders = np.linspace(xmin - half_step, xmax + half_step, bins + 1).tolist()
    for i in range(len(borders) - 1):
        indx = (x >= borders[i]) & (x < borders[i + 1])
        if indx.any():
            if mean_time:
                x_aprox.append(x[indx].mean())
            else:
                x_aprox.append((borders[i + 1] + borders[i]) / 2)
            y_aprox.append(y[indx].mean())
        else:
            x_aprox.append((borders[i + 1] + borders[i]) / 2)
            y_aprox.append(np.nan)

    x, y = np.array(x_aprox), np.array(y_aprox)
    # assert not np.isnan(y_aprox).any()
    if fix_nans:
        x, y = fix_missing(x, y)

    assert len(x_aprox) == bins
    assert len(y_aprox) == bins

    return x, y


def normalize(x, eps=1e-6):
    """
    Function will normalize an array (give it a mean of 0, and a
    standard deviation of 1) unless it's standard deviation is below
    epsilon, in which case it returns an array of zeros the length
    of the original array.

    Parameters
    ----------
    x : numpy.array, list, iterable
        Input data serie

    Returns
    -------
    numpy.arrray
        Normalized data serie
    """

    X = np.asanyarray(x)
    if X.std() < eps:
        return [0 for _ in X]
    return (X - X.mean()) / X.std()


def abbe(x, n, dropna=True):
    """
    Calculation of Abbe value

    Parameters
    ----------
    x : numpy.array
        Input data series

    n : int
        Dimension of original data (before dimension reduction)

    dropna : bool
        Drop all nans in x

    Returns
    -------
    float
        Abbe value
    """

    if dropna:
        x = x[~np.isnan(x)]

    sum1 = ((x[1:] - x[:-1])**2).sum()
    sum2 = ((x - x.mean())**2).sum()
    return n / (2 * (n - 1.0)) * sum1 / sum2


def variogram(x, y, bins=None, log_opt=True):
    """
    Variogram of function shows variability of function in various time steps

    Parameters
    ----------
    x : list, numpy.array, iterable
        Time values

    y : list, numpy.array
        Measured values

    bins : int
        Number of values in a variogram

    log_opt : bool
        Option if variogram values return in logarithm values

    Returns
    -------
    tuple
        Variogram as two numpy arrays
    """
    if not bins:
        bins = 20

    x = to_PAA(x, bins)[0]
    y = to_PAA(y, bins)[0]
    sort_opt = True
    n = len(x)
    vario_x = []
    vario_y = []
    for i in range(n):
        for j in range(n):
            if i != j and not np.isnan(x[i]) and not np.isnan(y[i]):
                x_val = abs(x[i] - x[j])
                y_val = (y[i] - y[j])**2

                if not np.isnan(x_val) and not np.isnan(y_val):
                    vario_x.append(x_val)
                    vario_y.append(y_val)
    vario_x, vario_y = np.array(vario_x), np.array(vario_y)

    if sort_opt:
        vario_x, vario_y = sort_pairs(vario_x, vario_y)
    vario_x = to_PAA(vario_x, bins)[0]
    vario_y = to_PAA(vario_y, bins)[0]

    if log_opt:
        vario_x, vario_y = np.log10(vario_x), np.log10(vario_y)
    return vario_x, vario_y


def histogram(xx, yy, bins_num=None, centred=True, normed=True):
    """
    Parameters
    ----------
    xx : numpy.array
        Input x data

    yy : numpy.array
        Input y data

    bins_num : int
        Number of values in histogram

    centred : bool
        If True values will be shifted (mean value into the zero)

    normed : bool
        If True values will be normed (according to standard deviation)

    Returns
    -------
    numpy.array
        Number of values in particular ranges

    numpy.array
        Ranges
    """
    if not bins_num:
        warnings.warn(
            "Number of bins of histogram was not specified. Setting default value.")
        bins_num = 10

    # Fix light curve length in case of non-equidistant time steps
    # between observations
    x = to_ekvi_PAA(xx, yy, bins=len(xx))[1]
    # Center values to zero
    if centred:
        x = x - np.nanmean(x)

    bef = len(x)
    x = x[~np.isnan(x)]
    # logging.info("Deleted nans for hist: {}/{}".format(bef - len(x), bef))

    bins = np.linspace(x.min(), x.max(), bins_num)

    hist, _ = np.histogram(x, bins=bins)

    # Norm histogram (number of point up or below the mean value)
    if normed:
        hist = normalize(hist)
    return hist, bins


def sort_pairs(x, y, rev=False):
    """Sort two numpy arrays according to the first"""

    x = np.array(x)
    y = np.array(y)

    indx = x.argsort()
    xx = x[indx]
    yy = y[indx]

    if rev:
        return xx[::-1], yy[::-1]

    return xx, yy


def compute_bins(x_time, days_per_bin, set_min=5):
    """
    Compute number of bins for given time series according to given ratio
    of number of days per one bin

    Parameters
    ----------
    x_time : numpy.array, list
        List of times

    days_per_bin : float
        Transformation rate for dimension reduction

    set_min
    """
    if isinstance(x_time, list):
        x_time = np.array(x_time)

    time_range = x_time.max() - x_time.min()
    num_bins = int(round(time_range / float(days_per_bin)))

    if set_min and num_bins < set_min:
        warnings.warn(
            "Too low number of bins for given ratio. Setting bin number to minimal default value.")
        num_bins = set_min

    return num_bins


def computePrecision(true_pos, false_pos):
    if true_pos + false_pos > 0:
        return true_pos / (true_pos + false_pos)
    return 0


# TODO: Distribute to multiple functions
def fix_missing(x, y, max_iter=1000, replace_at_borders=True):
    x, y = x.copy(), y.copy()
    n_to = len(x)
    start_from = 0
    deleted_n = 0
    first = 0
    for cc in range(max_iter):
        if n_to == start_from:
            break

        else:
            substitute_pos = None
            for ii in range(start_from, n_to):
                i = ii - deleted_n
                if substitute_pos is None:
                    if np.isnan(y[i]):
                        if i == first:
                            if replace_at_borders:
                                replace_with = None
                                for sent_i in range(i, n_to):
                                    if not np.isnan(y[sent_i]):
                                        replace_with = y[sent_i]
                                        break
                                if replace_with is not None:
                                    y[first:sent_i] = replace_with


                            else:
                                x = np.delete(x, i)
                                y = np.delete(y, i)
                                first = i
                                deleted_n += 1
                        else:
                            substitute_pos = i
                    else:
                        start_from = i + 1

                elif not np.isnan(y[i]):

                    time_to_left = x[substitute_pos] - x[substitute_pos - 1]
                    time_to_right = x[i] - x[substitute_pos]

                    w_left = time_to_left / (time_to_left + time_to_right)
                    w_right = time_to_right / (time_to_left + time_to_right)

                    y[substitute_pos] = w_left * y[substitute_pos - 1] + w_right * y[i]

                    start_from = substitute_pos + 1
                    substitute_pos = None
                    break

            if substitute_pos:
                if not replace_at_borders:
                    x = x[:substitute_pos]
                    y = y[:substitute_pos]
                else:
                    y[substitute_pos:] = y[substitute_pos - 1]
                break
    return x, y


def _missing_n(x):
    return np.isnan(x).sum() / len(x)
