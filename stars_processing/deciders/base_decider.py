from __future__ import division

import abc
import collections
from matplotlib import pyplot as plt
import os
import warnings

from conf import deciders_settings
import numpy as np
from utils.helpers import checkDepth


class BaseDecider(object):
    """
    A decider class works with "coordinates" (specification) of objects. It can
    learn identify inspected group of objects according to "coordinates" of 
    searched objects and other objects.

    All decider classes have to inherit this abstract class. That means that they
    need to implement several methods: "learn" and "evaluate". Also all of them
    have to have "treshold" attribute. To be explained read comments below.

    Attributes
    -----------
    treshold : float
        Probability (1.0  means 100 %) level. All objects with probability of
        membership to the group higher then the treshold are considered
        as members.
    """

    __metaclass__ = abc.ABCMeta

    def __init__(self, treshold=0.5):
        """
        Parameters
        -----------
        treshold : float
            Probability (1.0  means 100 %) level. All objects with probability
            of membership to the group higher then the treshold are considered
            as members
        """

        self.treshold = treshold

    def learn(self, right_coords, wrong_coords):
        """
        After executing this method the decider object is capable to recognize
        objects according their "coordinates" via "filter" method.

        Parameters
        -----------
        right_coords : list
            "Coordinates" of searched objects

        wrong_coords : list
            "Coordinates" of other objects

        Returns
        -------
        NoneType
            None
        """
        raise NotImplementedError

    def evaluate(self, star_coords):
        """
        Parameters
        -----------
        star_coords : list
            Coordinates of inspected star got from sub-filters

        Returns
        --------
        list of lists
            Probability that inspected star belongs to the searched
            group of objects
        """
        raise NotImplementedError

    def evaluateList(self, stars_coords):
        """
        Parameters
        ----------
        stars_coords : list
            Coordinates of inspected stars (e.g. obtained from sub-filters)

        Returns
        -------
        list
            Probabilities that inspected stars belongs to the searched
            group of objects
        """
        return np.array([self.evaluate(coords) for coords in stars_coords])

    def getBestCoord(self, stars_coords):
        """
        Parameters
        ----------
        stars_coords : list
            Coordinates of inspected stars got from sub-filters

        Returns
        -------
        list
            Coordinates with highest probability of membership to the
            searched group (one list of coordinates)
        """
        checkDepth(stars_coords, 2)
        if not len(stars_coords):
            warnings.warn(" There are no stars coordinates to inspect")
            return None

        best_coo = None
        best_prob = 0
        for coords in stars_coords:
            prob = self.evaluate([coords])[0]
            if prob >= best_prob:
                best_coo = coords
                best_prob = prob

        # TODO:
        assert best_coo is not None

        return best_coo

    def filter(self, stars_coords):
        """
        Parameters
        ----------
        stars_coords : list
            Coordinates of inspected stars

        Returns
        -------
        List of True/False whether coordinates belong to the searched group of objects
        """
        checkDepth(stars_coords, 2)
        return [self.evaluate([coo]) >= self.treshold for coo in stars_coords]

    # TODO: Reduce number of digits in output
    def getStatistic(self, right_coords, wrong_coords):
        """
        Parameters
        ----------
        right_coords : list
            Parameter-space coordinates of searched objects

        wrong_coords : list
            Parameter-space coordinates of other objects

        Returns
        -------
        statistic information : dict

            precision (float)
                True positive / (true positive + false positive)

            true_positive_rate (float)
                Proportion of positives that are correctly identified as such

            true_negative_rate :(float)
                Proportion of negatives that are correctly identified as such

            false_positive_rate (float)
                Proportion of positives that are incorrectly identified
                as negatives

            false_negative_rate (float)
                Proportion of negatives that are incorrectly identified
                as positives
        """
        checkDepth(right_coords, 2)
        checkDepth(wrong_coords, 2)

        right_num = len(right_coords)
        wrong_num = len(wrong_coords)

        true_pos = sum(
            [1 for guess in self.filter(right_coords) if guess == True])
        false_neg = right_num - true_pos

        true_neg = sum(
            [1 for guess in self.filter(wrong_coords) if guess == False])
        false_pos = wrong_num - true_neg

        precision = round(
            deciders_settings.PRECISION(true_pos, false_pos, true_neg, false_neg), 3)

        stat = (("precision", precision),
                ("true_positive_rate", round(true_pos / right_num, 3)),
                ("true_negative_rate", round(true_neg / wrong_num, 3)),
                ("false_positive_rate", round(false_pos / right_num, 3)),
                ("false_negative_rate", round(false_neg / wrong_num, 3)))

        return collections.OrderedDict(stat)

        """return {"precision" : precision,
                "true_positive_rate" : true_pos / (false_neg + true_pos) ,
                "true_negative_rate" : true_neg / (false_pos + true_neg),
                "false_positive_rate" : false_pos / (false_pos + true_neg),
                "false_negative_rate" : false_neg / (false_neg + true_pos)}"""

    def plotProbabSpace(self, xlim=None, ylim=None, OFFSET=0.4,
                        save_path=None, x_lab="", y_lab="", title="",
                        file_name="plot.png"):
        """
        Plot probability space

        Parameters
        ----------
        xlim : tuple
            Tuple of min and max value for x-axis

        ylim : tuple
            Tuple of min and max value for y-axis

        OFFSET : float
            Percentage value of overflowing boundaries set by xlim and ylim

        save_path : str, NoneType
            Path to the folder where plots are saved if not None, else
            plots are showed immediately

        x_lab : str
            Label for x-axis

        y_lab : str
            Label for y-axis

        title : str
            Title for the plot

        file_name : str
            Name of the plot file

        Returns
        -------
        None
        """
        try:
            plt.clf()
            try:
                if xlim is None or ylim is None:
                    x_min, x_max = np.min(self.X[:, 0]), np.max(self.X[:, 0])
                    y_min, y_max = np.min(self.X[:, 1]), np.max(self.X[:, 1])

                    x_offset = (x_max - x_min) * OFFSET
                    y_offset = (y_max - y_min) * OFFSET

                    xlim = (x_min - x_offset, x_max + x_offset)
                    ylim = (y_min - y_offset, y_max + y_offset)

                searched = self.X[self.y == 1]
                others = self.X[self.y == 0]
                plt.plot(searched[:, 0], searched[
                         :, 1], "bo", label="Searched objects",
                         markeredgecolor='red', markeredgewidth=0.5)
                plt.plot(others[:, 0], others[
                         :, 1], "ro", label="Others", markeredgecolor='blue',
                         markeredgewidth=0.5)

            except:
                xlim = (0, 50)
                ylim = (0, 50)
                print "Can't plot coordinates of training objects. Decider has to have X and y attribute."

            xx, yy = np.meshgrid(np.linspace(xlim[0], xlim[1], 100),
                                 np.linspace(ylim[0], ylim[1], 100))

            try:
                Z = self.evaluate(np.c_[xx.ravel(), yy.ravel()])
            except ValueError:
                raise
                Z = self.evaluateList(np.c_[xx.ravel(), yy.ravel()])

            Z = Z.reshape(xx.shape)

            plt.pcolor(xx, yy, Z)
            plt.legend()
            plt.colorbar()
            plt.xlim(*xlim)
            plt.ylim(*ylim)

            if x_lab and y_lab:
                plt.xlabel(str(x_lab))
                plt.ylabel(str(y_lab))
            if title:
                plt.title(str(title))

            if not save_path:
                plt.show()
            else:
                plt.savefig(os.path.join(save_path, file_name))

        except Exception, e:
            warnings.warn("Could not plot, because: %s" % e)

    def plotHist(self, title="", labels=[], bins=None, save_path=None,
                 file_name="hist.png"):
        """
        Plot histogram

        Parameters
        ----------
        title : str
            Title for the plot

        labels : list, tuple of str
            Labels for axis

        save_path : str, NoneType
            Path to the folder where plots are saved if not None, else
            plots are showed immediately

        bins : int, NoneType
            Number of bins for histogram

        file_name : str
            Name of the plot file

        Returns
        -------
        None
        """
        if self.X.any():
            if not bins:
                bins = 1 + 3.32 * np.log10(len(self.X))

            for i in range(len(self.X[0])):

                if len(labels) > i:
                    lab = labels[i].lower()
                else:
                    lab = ""

                plt.clf()
                plt.hist(self.X[self.y == 1][:, i], normed=True, bins=bins,
                         histtype='bar', color="crimson",
                         label="Searched objects")
                plt.hist(
                    self.X[self.y == 0][:, i], normed=True, bins=bins,
                    label="Others")
                plt.title(title)

                plt.xlabel(str(lab))

                plt.legend()
                if save_path:
                    plt.savefig(os.path.join(
                        save_path, file_name + "_hist_%s_%i.png" % (lab.replace(" ", "_"), i)))
                else:
                    plt.show()
        else:
            warnings.warn("No data to plot histogram")
