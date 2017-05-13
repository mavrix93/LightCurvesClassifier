'''
There are functions for processing data series
'''

from __future__ import division

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


def to_ekvi_PAA(x, y, bins=None, days_per_bin=None):
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

    bins : int
        Dimension of result data

    days_per_bin : float
        This value can be used for calculating bins

    Returns
    -------
    list
        Reduced `x` data

    list
        Reduced `y` data
    """

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

    n_x = len(x)
    n_y = len(y)
    if not n_x == n_y:
        raise Exception("X and Y have no same length (%i and %i" % (n_x, n_y))

    # Check if sorted times
    sorting = np.argsort(x)
    x = x[sorting]
    y = y[sorting]
    n = len(x)
    x_beg = x.min()
    x_end = x.max()
    x_width = x_end - x_beg
    frame_len = x_width / bins
    x_aprox = []
    y_aprox = []
    i = 0
    frame_num = 1
    x_frame_sum = 0
    y_frame_sum = 0
    items_in_this_frame = 0
    for i in range(n):
        y_frame_sum += y[i]
        x_frame_sum += x[i]
        items_in_this_frame += 1
        if (x[i] >= x_beg + frame_len * frame_num):
            val_y = y_frame_sum / items_in_this_frame
            val_x = x_frame_sum / items_in_this_frame

            if val_x and val_y:
                y_aprox.append(val_y)
                x_aprox.append(val_x)
            x_frame_sum = 0
            y_frame_sum = 0
            items_in_this_frame = 0
            frame_num += 1
    return np.array(x_aprox), np.array(y_aprox)


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

# TODO: Check n==1


def abbe(x, n):
    '''
    Calculation of Abbe value

    Parameters
    ----------
    x : numpy.array
        Input data serie

    n : int
        Dimension of original data (before dimension reduction)

    Returns
    -------
    float
        Abbe value
    '''

    sum1 = ((x[1:] - x[:-1])**2).sum()
    sum2 = ((x - x.mean())**2).sum()
    return n / (2 * (n - 1.0)) * sum1 / sum2


def variogram(x, y, bins=None, log_opt=True):
    '''
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
    '''
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
    '''
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
    '''
    if not bins_num:
        warnings.warn(
            "Number of bins of histogram was not specified. Setting default value.")
        bins_num = 10

    # Fix light curve length in case of non-equidistant time steps
    # between observations
    x = to_ekvi_PAA(xx, yy, bins=len(xx))[1]
    # Center values to zero
    if centred:
        x = x - x.mean()

    bins = np.linspace(x.min(), x.max(), bins_num)

    hist, _ = np.histogram(x, bins=bins)

    # Norm histogram (number of point up or below the mean value)
    if normed:
        hist = normalize(hist)
    return hist, bins


def sort_pairs(x, y, rev=False):
    '''Sort two numpy arrays according to the first'''

    x = np.array(x)
    y = np.array(y)

    indx = x.argsort()
    xx = x[indx]
    yy = y[indx]

    if rev:
        return xx[::-1], yy[::-1]

    return xx, yy


def compute_bins(x_time, days_per_bin, set_min=5):
    '''
    Compute number of bins for given time series according to given ratio
    of number of days per one bin

    Parameters
    ----------
    x_time : numpy.array, list
        List of times

    days_per_bin : float
        Transformation rate for dimension reduction

    set_min
    '''

    BORDER_AREA = 5

    if (type(x_time) == list):
        x_time = np.array(x_time)

    n = len(x_time)
    if (n < BORDER_AREA * 5):
        BORDER_AREA = 1

    time_range = x_time[-BORDER_AREA:].mean() - x_time[:BORDER_AREA].mean()
    num_bins = int(round(time_range / float(days_per_bin)))

    if (set_min and num_bins < set_min):
        warnings.warn(
            "Too low number of bins for given ratio. Setting bin number to minimal default value.")
        num_bins = 5

    return num_bins


def computePrecision(true_pos, false_pos):
    if true_pos + false_pos > 0:
        return true_pos / (true_pos + false_pos)
    return 0
