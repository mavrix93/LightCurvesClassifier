import logging

import numpy as np
from keras.layers import Dense
from keras.models import Sequential

from lcc.entities.exceptions import QueryInputError
from lcc.stars_processing.utilities.base_decider import BaseDecider


class NeuronDecider(BaseDecider):
    """
    The class is responsible for learning to recognize certain group of objects by using NN.
    So far there just one architecture available:
        Three layered Feed Forward Network with Backpropagation Trainer:
            Input layer - LinearLayer
            Hidden layer - SigmoidLayer
            Output layer - SoftmaxLayer
        

    Attributes
    -----------
    hiden_neurons : int
        Number of hiden neurons.

    OUTPUT_NEURONS : int
        Number of output neurons.

    input_neurons : int
        Number of input neurons.

    X_train : numpy array of array of floats
        Each item of the array contains specific "coordinates" of the train
        object in array.

    X_test : numpy array of array of floats
        Each item of the array contains specific "coordinates" of the test
        object in array.

    y_train : numpy array of ints
        Each item of the array contains a number of the group which the train
        object belongs. Position in the array
        corresponds to item in X_train.

    y_test : numpy array of ints
        Each item of the array contains a number of the group which the test
        object belongs. Position in the array
        corresponds to item in X_test.

    continueEpochs : int
        Number of epochs to continue for testing after convergence

    maxEpochs : int
        Maximum number of epochs for training
    """

    OUTPUT_NEURONS = 1

    def __init__(self, threshold=0.5, hidden_neurons=2, maxEpochs=1000):
        """
        Parameters
        -----------
        hidden_neurons: int
            Number of hidden neurons

        maxEpochs : int
            Maximum number of epochs for training

        Note
        -----
        Attributes with None values will be updated by setTrainer
        and train methods
        """

        self.hiden_neurons = hidden_neurons

        self.threshold = threshold
        self.maxEpochs = maxEpochs

        self.history = None
        self.model = None

    def learn(self, searched, others):
        """
        This method loads lists of specific values of searched objects and
        others. Then the sample will be  divided into train and
        test samples according to user.

        Parameters
        -----------
        searched : iterable
            List of searched objects values (their "coordinates")

        others : iterable
            List of other objects values (their "coordinates")

        Returns
        -------
        NoneType
            None
        """
        if not len(searched) or not len(others):
            raise QueryInputError("Decider can't be learned on an empty sample")

        # Input is accepted as a numpy array or as a list
        if isinstance(searched, np.ndarray):
            try:
                searched = searched.tolist()
                others = others.tolist()

            except AttributeError as err:
                raise AttributeError("Wrong coordinates input: %s" % err)
        elif not isinstance(searched, list):
            raise AttributeError("Input type ({}) not supported".format(type(searched)))

        X = np.array(searched + others)

        # Note searched objects as 1 and others as 0
        y = np.array(
            [1 for i in range(len(searched))] + [0 for i in range(len(others))])

        dim = X.shape[1]

        model = Sequential()
        model.add(Dense(self.hiden_neurons, input_dim=dim, activation="relu"))
        model.add(Dense(1, activation="sigmoid"))
        # Compile model
        model.compile(loss="binary_crossentropy", optimizer="adam", metrics=["accuracy"])

        # Fit the model
        self.history = model.fit(X, y, epochs=150, batch_size=10)

        self.model = model

        logging.info("Training of NN successfully finished")

    def fit(self, *args, **kwargs):
        return self.learn(*args, **kwargs)

    def evaluate(self, coords):
        """
        Find if inspected parameter-space coordinates belongs to searched
        object

        Parameter
        ---------
        coords : list of lists
            Parameter-space coordinates of inspected objects

        Returns
        ------
        numpy.array
            Probabilities of membership to searched group objects
        """
        return self.model.predict_proba(coords)[:,0]
