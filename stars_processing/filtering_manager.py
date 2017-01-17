import numpy as np
import itertools
import warnings


class FilteringManager(object):
    """
    This class is responsible for filtering stars according to given filters
    (their own implementation of filtering)
    """

    SPACE_DENSITY = 10

    def __init__(self, descriptors, deciders):

        self.descriptors = descriptors

        if not isinstance(deciders, (list, tuple)):
            deciders = [deciders]
        self.deciders = deciders

    def filterStars(self, stars):
        '''
        Apply all filters to stars and return stars which passed
        thru all filters

        Returns
        -------
        list of `Star`s
            Stars which passed thru filtering
        '''
        stars_coords = self.assignSpaceCoordinates(stars)

        decisions = []
        for decider in self.deciders:
            decisions.append(decider.filter(stars_coords))

        decisions = np.array(decisions)
        return [star for i, star in enumerate(stars) if False not in decisions[:, i]]

    def learn(self, searched, others):
        searched_coords = self.assignSpaceCoordinates(searched)
        others_coords = self.assignSpaceCoordinates(others)

        self.coords = searched_coords + others_coords

        for decider in self.deciders:
            decider.learn(searched_coords, others_coords)

    def assignSpaceCoordinates(self, stars):
        space_coordinates = []
        for star in stars:
            coords = self._assignSpaceCoordinates(star)
            if coords:
                space_coordinates.append(coords)
            else:
                warnings.warn("Not all space coordinates have been obtained")
        return space_coordinates

    def _assignSpaceCoordinates(self, star):
        space_coordinate = []
        for descriptor in self.descriptors:
            coo = descriptor.getSpaceCoords([star])
            if coo:
                space_coordinate += coo[0]
            else:
                return False
        return space_coordinate

    def getProbabSpace(self, save_path=None, file_name="probab_space.dat"):

        if self.coords:
            all_coords = np.array(self.coords)

            wide_coords = []
            for i in range(len(self.coords[0])):
                start = np.min(all_coords[:, i])
                stop = np.max(all_coords[:, i])
                wide_coords.append(
                    np.linspace(start, stop, self.SPACE_DENSITY))

            coordinates = list(itertools.product(*wide_coords))

            if save_path:
                pass

            return [decider.evaluate(coordinates) for decider in self.deciders]

        """title = self.__class__.__name__ + ": " + \
            self.decider.__class__.__name__ + "_%s" % str(learn_num)

        try:
            self.labels
        except AttributeError:
            self.labels = ["" for _ in self.decider.X]

        try:
            self.plot_save_path
        except AttributeError:
            self.plot_save_path = None

        try:
            img_name = clean_path(self.plot_save_name) + "_%s" % str(learn_num)
            self.decider.plotHist(
                title, self.labels, file_name=img_name,
                save_path=self.plot_save_path)

            if len(self.labels) == 2:
                self.decider.plotProbabSpace(save_path=self.plot_save_path,
                                             file_name=img_name,
                                             x_lab=self.labels[0],
                                             y_lab=self.labels[1],
                                             title=title)
        except Exception as err:
            # TODO: Load from settings file
            # path = settings.TO_THE_DATA_FOLDER
            path = "."
            VERB = 2

            err_log = open(os.path.join(path, "plot_err_occured.log"), "w")
            err_log.write(str(err))
            err_log.close()
            verbose(
                "Error during plotting.. Log file has been saved into data folder", 1, VERB)

        try:
            self.learned = True
        except AttributeError:
            warnings.warn("Could not be able to set self.learned = True")"""

    def getStatistic(self, s_stars, c_stars):
        """
        Parameters
        ----------
        s_stars : list of `Star` objects
            Searched stars

        c_stars : list of `Star` objects
            Contamination stars

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
        searched_stars_coords = self.assignSpaceCoordinates(s_stars)
        contamination_stars_coords = self.assignSpaceCoordinates(c_stars)

        return [decider.getStatistic(searched_stars_coords, contamination_stars_coords) for decider in self.deciders]
