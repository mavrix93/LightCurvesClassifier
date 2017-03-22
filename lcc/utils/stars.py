'''
There are common functions for list of star objects (evaluation, plotting...)
'''

import os
import random
import string
import warnings

from lcc.db_tier.connectors.file_manager import FileManager
import matplotlib.pyplot as plt
import numpy as np


def saveStars(stars, path=".", clobber=True):
    """
    Save Star objects into fits files

    Parameters
    -----------
    stars : list, iterable
        Star objects to be saved

    path : str
        Relative path to the file where fits are stored

    clobber : bool
        Files are overwritten if True

    Returns
    -------
    list
        List of names of star files
    """
    N = 7
    file_names = []
    for star in stars:
        file_name = star.name
        if not file_name:
            file_name = ''.join(
                random.choice(string.ascii_uppercase + string.digits) for _ in range(N))
        FileManager.writeToFITS(
            os.path.join(path, file_name + ".fits"), star, clobber)

        file_names.append(file_name)

    return file_names


def get_stars_dict(stars):
    """
    Transform list of stars into dictionary where keys are their names

    Parameters
    ----------
    stars : list, iterable
        Star objects

    Return
    ------
    dict
        Stars dictionary
    """
    x = {}
    for st in stars:
        try:
            x[st.name] = st
        except:
            pass
    return x


# TODO: Need to be upgraded
def plotStarsPicture(stars, option="show", hist_bins=10, vario_bins=10,
                     center=True, save_loc=None, num_plots=None, abbe_bins=20):
    '''
    This function plot three graphs for all stars: Light curve, histogram
    and variogram. Additionally Abbe value will be displayed.

    Parameters
    ----------
    stars : list of `Star`s
        List of star objects to be plot

    option : str
        Option whether plots will be saved or just showed

    hist_bins : int
        Dimension of histogram

    vario_bins : int
        Dimension of variogram

    center : bool
        Centering of histogram

    save_loc : str, NoneType
        Location where images will be saved

    num_plots : int, NoneType
        Number of plots

    abbe_bins : int
        Dimension of reduced light curve for calculating Abbe value
    '''

    OPTIONS = ["show", "save"]
    if not (option in OPTIONS):
        raise Exception("Invalid plot option")

    for num, star in enumerate(stars[:num_plots]):

        num_rows = len(star.light_curves)
        fig = plt.figure(figsize=(20, 6))
        for row_num, lc in enumerate(star.light_curves):
            xlabel = lc.meta.get("xlabel", "JD")
            xlabel_unit = lc.meta.get("xlabel_unit", "days")
            ylabel = lc.meta.get("ylabel", "Magnitude")
            ylabel_unit = lc.meta.get("ylabel_unit", "mag")
            color = lc.meta.get("color", "")
            invert_axis = lc.meta.get("invert_yaxis", True)
            ax1 = fig.add_subplot(31 + num_rows * 100 + 3 * row_num)
            ax1.set_xlabel("({ylabel} + {mean} ) {ylabel_unit}".format(mean=lc.mag.mean(),
                                                                       ylabel=ylabel,
                                                                       ylabel_unit=ylabel_unit))
            ax1.set_ylabel("Normalized counts")

            hist, indices = lc.getHistogram(bins=hist_bins)
            ax1.set_title("Abbe index: %.2f" %
                          lc.getAbbe(bins=abbe_bins), loc="left")

            width = 1 * (indices[1] - indices[0])
            center = (indices[:-1] + indices[1:]) / 2
            ax1.bar(center, hist, align='center', width=width)

            ax2 = fig.add_subplot(33 + num_rows * 100 + 3 * row_num)
            if invert_axis:
                ax2.set_ylim(np.max(lc.mag), np.min(lc.mag))
            ax2.set_xlabel("%s [%s]" % (xlabel, xlabel_unit))
            ax2.set_ylabel("%s [%s]" % (ylabel, ylabel_unit))
            ax2.errorbar(lc.time, lc.mag, yerr=lc.err, fmt='o')

            if vario_bins:
                ax3 = fig.add_subplot(32 + num_rows * 100 + 3 * row_num)
                if not star.starClass:
                    star.starClass = "unlabeled"
                if color:
                    color = " %s - band" % color
                ax3.set_title(
                    "Star: {0} ({1}) {2}".format(star.name, lc.meta.get("origin", ""), color))
                ax3.set_xlabel("log {value} [{unit}])".format(
                    value=xlabel, unit=xlabel_unit))
                ax3.set_ylabel("log (I_i - I_j)^2")
                x_v, y_v = lc.getVariogram(bins=vario_bins)
                ax3.plot(x_v, y_v, "--")

        if option == "save":
            if not save_loc:
                save_loc = ""
            else:
                if not os.path.exists(save_loc):
                    os.makedirs(save_loc)

            plt.tight_layout()
            fig.savefig(save_loc + "/" + star.name + ".png")
        else:
            try:
                plt.tight_layout()
                plt.show()
            except ValueError:
                warnings.warn(
                    "There no light curves to plot for %s" % star.name)

        plt.close()
