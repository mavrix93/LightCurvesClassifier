from lcc.stars_processing.utilities.base_decider import BaseDecider
from lcc.entities.exceptions import QueryInputError


class CustomDecider(BaseDecider):
    '''
    This decider allows to specify ranges of coordinates got from descriptors.
    So there is no need to run `learn` method. Anyway it is implemented
    to be consistent with other deciders. Also it checks if `boundaries`
    and given coordinates match.

    Attributes
    ----------
    boundaries : list, iterable
        List of tuples of two values - lower and higher border value

    treshold : float
        Treshold value for evaluating
    '''

    def __init__(self, boundaries):
        '''
        Parameters
        ----------
        boundaries : list, iterable
            List of tuples of two values - lower and higher border value.
            If one of these value is None there is no lower/upper limit.

            Example
            -------
                [(1,10), (5,None), (None,8)]

                First coordinate means "something between 1 and 10, the second
                means greater then 5 and the last one means something lower
                then 8
        '''
        if [x for x in boundaries if len(x) != 2]:
            raise QueryInputError(
                "List of boundaries have to be consist of tuples of two values")
        self.boundaries = boundaries
        self.treshold = 0.5

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
        self._checkDimensions(star_coords)

        probabilities = []
        for one_star in star_coords:
            passed = not False in [self._evaluateOne(
                one_star[i], self.boundaries[i]) for i in range(len(self.boundaries))]
            if passed:
                probabilities.append(1)
            else:
                probabilities.append(0)
        return probabilities

    def _evaluateOne(self, coo, coo_ranges):
        lower = coo_ranges[0]
        higher = coo_ranges[1]
        coo = float(coo)
        if lower and higher:
            return coo > lower and coo < higher
        elif lower:
            return coo > lower
        elif higher:
            return coo < higher
        return True

    def learn(self, right_coords=[], wrong_coords=[]):
        """
        No need to learn this decider. Anyway it is implemented
        to be consistent with other deciders. Also it checks if `boundaries`
        and given coordinates match.

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
        if len(right_coords) and len(wrong_coords):
            self._checkDimensions(right_coords)
            self._checkDimensions(wrong_coords)

    def _checkDimensions(self, coords):
        expected_dim = len(self.boundaries)
        dim = len(coords[0])
        if expected_dim != dim:
            raise QueryInputError("Dimension of the decider boundaries (dim: %i) and given coordinates (dim: %i) dont match.\nGot: %s" % (
                expected_dim, dim, coords))
