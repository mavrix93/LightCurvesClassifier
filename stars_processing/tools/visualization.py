from matplotlib import pyplot as plt
import os

from lcc.utils.helpers import checkDepth
import numpy as np


def plotProbabSpace(star_filter, plot_ranges=None, save=False,
                    path=".", file_name="params_space.png", N=100,
                    title="Params space", x_lab="", y_lab=""):
    """
    Plot params space

    Parameters
    ----------
    star_filter : StarsFilter object
        Trained stars filter object

    plot_ranges : tuple, list
        List of ranges. For example: [range(1,10), range(20,50)] - for 2D plot

    save : bool
        If True plot is saved into the file

    title : str
        Title of the plot

    path : str
        Path to the output file location

    file_name : str
        Name of the file

    Returns
    -------
        None
    """
    dim = len(star_filter.searched_coords[0])

    if not plot_ranges:
        plot_ranges = []
        trained_coo = np.array(
            star_filter.searched_coords + star_filter.others_coords).T
        for i in range(dim):
            plot_ranges.append(
                [np.min(trained_coo[i]), np.max(trained_coo[i])])

    if dim == 1:
        if not x_lab and not y_lab:
            x_lab = star_filter.descriptors[0].__class__.__name__
            y_lab = "Probability"
        plot1DProbabSpace(star_filter, plot_ranges, N, x_lab, y_lab, title)
    elif dim == 2:
        if not x_lab and not y_lab:
            x_lab = star_filter.descriptors[0].__class__.__name__
            y_lab = star_filter.descriptors[1].__class__.__name__
        plot2DProbabSpace(star_filter, plot_ranges, N)

    else:
        return

    plt.xlabel(str(x_lab))
    plt.ylabel(str(y_lab))
    plt.title(str(title))

    if not save:
        plt.show()
    else:
        plt.savefig(os.path.join(path, file_name))


def plot2DProbabSpace(star_filter, plot_ranges, N):
    """
    Plot probability space

    Parameters
    ----------
    option : str
        "show"
        "save"
        "return"

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
    if checkDepth(plot_ranges, 1, ifnotraise=False):
        plot_ranges = [plot_ranges, plot_ranges]
    x = np.linspace(plot_ranges[0][0], plot_ranges[0][1], N)
    y = np.linspace(plot_ranges[1][0], plot_ranges[1][1], N)
    X, Y = np.meshgrid(x, y)

    z = np.array(star_filter.evaluateCoordinates(np.c_[X.ravel(), Y.ravel()]))
    Z = z.reshape(X.shape)

    plt.xlim(plot_ranges[0][0], plot_ranges[0][1])
    plt.ylim(plot_ranges[1][0], plot_ranges[1][1])

    plt.pcolor(X, Y, Z)
    plt.colorbar()


def plot1DProbabSpace(star_filter, plot_ranges, N, x_lab, y_lab, title):
    if checkDepth(plot_ranges, 2, ifnotraise=False):
        plot_ranges = plot_ranges[0]
    x = np.linspace(plot_ranges[0], plot_ranges[1])

    plt.plot(x, star_filter.evaluateCoordinates([[y] for y in x]), linewidth=3)

'''def plotHist(title="", labels=[], bins=None, save_path=None,
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
'''
