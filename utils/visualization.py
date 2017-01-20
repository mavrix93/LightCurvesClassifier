import os

from matplotlib import pyplot as plt
import numpy as np


def plotProbabSpace(x, y, star_filter,
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
    X, Y = np.meshgrid(x, y)

    z = np.array(star_filter.evaluateCoordinates(np.c_[X.ravel(), Y.ravel()]))
    Z = z.reshape(X.shape)

    plt.pcolor(X, Y, Z)
    plt.legend()
    plt.colorbar()

    if x_lab and y_lab:
        plt.xlabel(str(x_lab))
        plt.ylabel(str(y_lab))
    if title:
        plt.title(str(title))

    if not save_path:
        plt.show()
    else:
        plt.savefig(os.path.join(save_path, file_name))


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
