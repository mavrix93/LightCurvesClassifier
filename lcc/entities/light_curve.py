from lcc.entities.exceptions import StarAttributeError
from lcc.utils.data_analysis import compute_bins
from lcc.utils.data_analysis import histogram, variogram, to_ekvi_PAA,\
    abbe
import matplotlib.pyplot as plt
import numpy as np


class LightCurve(object):
    """
    Attributes
    ----------
    meta : dict
        Optional metadata of the light curve. Recommended are
        these keys:

            xlabel - name of the first array

            xlabel_unit - unit of the first array

            ylabel - name of the second array

            ylabel_unit - unit of the second array

            color - filter name of the light curve

            origin - db name

            invert_yaxis - True/False if y axis is inverted
    BAD_VALUES : iterable
        List of banned values in light curve
    """

    DEFAULT_META = {"xlabel": "HJD",
                    "xlabel_unit": "days",
                    "ylabel": "Magnitudes",
                    "ylabel_unit": "mag",
                    "color": "N/A"
                    }

    BAD_VALUES = (np.NaN, None, "", "-99", "-99.0")

    def __init__(self, param, meta={}):
        '''
        Parameters
        -----------
        param : list, array, string
            Light curve data or path to the file of light curve.

               Option I:
                    List (numpy array) of 3 lists(time, mag, err)

                Option II:
                    List (numpy array) of N lists (time, mag  and err)
                    one per obs
        meta : dict
            Optional metadata of the light curve. Recommended are
            these keys:

                xlabel - name of the first array

                xlabel_unit - unit of the first array

                ylabel - name of the second array

                ylabel_unit - unit of the second array

                color - filter name of the light curve

                origin - db name

                invert_yaxis - True/False if y axis is inverted
        '''

        if isinstance(param, (list, tuple)):
            param = np.array(param)

        if isinstance(param, np.ndarray):
            # Transpose if there are list of tuples (time, mag,err)
            if (len(param) > 3):
                param = param.transpose()

            param[0] = np.array(param[0])
            param[1] = np.array(param[1])

            if (len(param) == 2):
                param = np.concatenate([param, [np.zeros(len(param[0]))]])
            else:
                param[2] = np.array(param[2])

            self.time, self.mag, self.err = self._cleanLC(param[0],
                                                          param[1], param[2])
        else:
            raise Exception(
                "Wrong object parameters\nLightCurve object is not created")

        if not (len(self.time) == len(self.mag) == len(self.err)):
            raise StarAttributeError("""Invalid light curve. Size of time, mag
            and err lists have to be the some. Got %i, %i, %i""" %
                                     (len(self.time), len(self.mag),  len(self.err)))
        # Set default meta values
        for key in self.DEFAULT_META:
            if not meta.get(key):
                meta[key] = self.DEFAULT_META[key]

        self.meta = meta

    def __str__(self):
        txt = "Time\tMag\tErr\n"
        txt += "-" * (len(txt) + 6) + "\n"
        for i in range(0, len(self.time)):
            txt += "%.02f\t%.02f\t%.02f\n" % (
                self.time[i], self.mag[i], self.err[i])

        return txt

    def plotLC(self):
        '''Plot light curve'''
        plt.errorbar(self.time, self.mag, self.err, fmt='o', ecolor='r')
        plt.show()

    def getMeanMag(self):
        '''Get mean value of magnitudes'''
        return np.mean(self.mag)

    def getStdMag(self):
        '''Get standard deviation of magnitudes'''
        return np.std(self.mag)

    def getHistogram(self, bins=10, centred=True, normed=True):
        '''
        Distribution of magnitudes of light curve

        Parameters
        -----------
        bins : int
            Number of values in histogram

        centred : bool
            If True values will be shifted (mean value into the zero)

        normed : bool
            If True values will be normed (according to standard deviation)

        Returns
        --------
        tuple/None
            Tuple of counts and bins (ranges) or None if
            there are no light curve
        '''
        return histogram(self.time, self.mag, bins, centred, normed)

    def getVariogram(self, bins=10, days_per_bin=None, log_opt=True):
        '''
        Variogram is function which shows variability of time series
        in different time lags

        Parameters
        -----------
        bins : int
            Number of bins for result variogram

        Returns
        --------
        tuple of two numpy arrays
            Time lags and magnitude slope for the certain lag
        '''
        if days_per_bin and not bins:
            bins = compute_bins(self.time, days_per_bin)

        return variogram(self.time, self.mag, bins=bins, log_opt=log_opt)

    def getAbbe(self, bins=None):
        '''
        Compute Abbe value of the light curve

        Parameters
        -----------
        bins : int
            Number of bins from original dimension

        Returns
        --------
        float
            Abbe value of the light curve
        '''
        if bins:
            x = to_ekvi_PAA(self.time, self.mag, bins)[1]
        else:
            x = self.mag
        return abbe(x, len(self.time))

    def _cleanLC(self, time, mag, err):
        cl_time, cl_mag, cl_err = [], [], []
        for t, m, e in zip(time, mag, err):
            if not (t in self.BAD_VALUES or m in self.BAD_VALUES or
                    e in self.BAD_VALUES):
                cl_time.append(round(t, 5))
                cl_mag.append(round(m, 3))
                cl_err.append(round(e, 3))
        return np.array(cl_time), np.array(cl_mag), np.array(cl_err)
