'''
Created on Jan 7, 2016

@author: Martin Vo
'''
import matplotlib.pyplot as plt
import numpy as np
from utils.data_analysis import compute_bins
from utils.data_analysis import histogram, variogram, to_ekvi_PAA,\
    abbe


class LightCurve:

    DEFAULT_META = {"xlabel": "HJD",
                    "xlabel_unit": "days",
                    "ylabel": "Magnitudes",
                    "ylabel_unit": "mag",
                    "color": "N/A"
                    }

    def __init__(self, param, meta={}):
        '''
        Parameters:
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

        if (type(param) is list or type(param) is tuple):
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

            self.time = param[0]
            self.mag = param[1]
            self.err = param[2]
        else:
            raise Exception(
                "Wrong object parameters\nLightCurve object is not created")

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

    def getHistogram(self, bins=None, centred=True, normed=True):
        '''
        Distribution of magnitudes of light curve

        Parameters:
        -----------
            bins : int
                Number of values in histogram

            centred : bool
                If True values will be shifted (mean value into the zero)

            normed : bool
                If True values will be normed (according to standard deviation)

        Returns:
        --------
            Tuple of counts and bins (ranges) or None if
            there are no light curve
        '''
        return histogram(self.time, self.mag, bins, centred, normed)

    def getVariogram(self, bins=10, days_per_bin=None, log_opt=True):
        '''
        Variogram is function which shows variability of time series
        in different time lags

        Parameters:
        -----------
            bins : int
                Number of bins for result variogram

        Returns:
        --------f
            Tuple of two numpy arrays
                -time lags and magnitude slope for the certain lag
        '''
        if days_per_bin and not bins:
            bins = compute_bins(self.time, days_per_bin)

        return variogram(self.time, self.mag, bins=bins, log_opt=log_opt)

    def getAbbe(self, bins=None):
        '''
        Compute Abbe value of the light curve

        Parameters:
        -----------
            bins : int
                Percentage number of bins from original dimension

        Returns:
        --------
            Abbe value of the light curve
        '''
        if not bins:
            bins = len(self.lightCurve.time)

        x = to_ekvi_PAA(self.time, self.mag, bins)[1]
        return abbe(x, len(x))
