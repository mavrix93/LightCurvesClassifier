'''
Created on Oct 28, 2016

@author: martin
'''

from pybrain.tools.shortcuts import buildNetwork
from pybrain.datasets import SupervisedDataSet
from pybrain.supervised.trainers import BackpropTrainer

import numpy as np
from stars_processing.deciders.base_decider import BaseDesider
from conf import deciders_settings

class NeuronDecider(BaseDesider):
    """
    The class is responsible for learning to recognize certain group of objects.
    
    Attributes:
    -----------
        hiden_neurons : int
            Number of hiden neurons.
            
        OUTPUT_NEURONS : int
            Number of output neurons.
            
        input_neuron : int
            Number of input neurons.
        
        X_train : numpy array of array of floats
            Each item of the array contains specific "coordinates" of the train object in array.
            
        X_test : numpy array of array of floats
            Each item of the array contains specific "coordinates" of the test object in array.
            
        y_train : numpy array of ints
            Each item of the array contains a number of the group which the train object belongs. Position in the array
            corresponds to item in X_train.
            
        y_test : numpy array of ints
            Each item of the array contains a number of the group which the test object belongs. Position in the array
            corresponds to item in X_test.
    
    """
    
    OUTPUT_NEURONS = 1
    
    def __init__(self, treshold = None, hiden_neurons = None):
        '''
        Parameters:
        -----------
            hiden_neurons: int
                Number of hiden neurons
                
        Note:
        -----
            Attributes with None values will be updated by setTrainer and train methods
        '''
        if not treshold:
            treshold = deciders_settings.TRESHOLD
        
        if not hiden_neurons:
            hiden_neurons = deciders_settings.HIDDEN_NEURONS
            
        self.hiden_neurons = hiden_neurons
        
        self.input_neuron = None
        self.X = None
        self.y = None
        
        self.treshold = treshold
       
    def learn(self,searched, others):
        '''
        This method loads lists of specific values of searched objects and others. Then the sample will be interactivly devided
        into train and test samples according to user.
        
        Parameters:
        -----------        
            searched : iterable
                List of searched objects values (their "coordinates")
            
            others : iterable
                List of other objects values (their "coordinates")       
        '''
        
        #Resolve number of input neurons
        self.input_neurons = len(searched[0])
        
        #Input is accepted as a numpy array or as a list
        if type(searched) != list:
            try:
                X = searched.tolist()+others.tolist()
            except AttributeError as err:
                raise AttributeError("Wrong input: %s" % err)
        elif type(searched) == list:
            X = np.array( searched + others )
        
        #Note searched objects as 1 and others as 0
        self.y = np.array( [1 for i in range(len(searched))]+[0 for i in range(len(others))] )
        self.X = X
        
        #Prepare button for executing of training
        self.train()
        
        
            
    def getTrainer(self):
        '''
        Returns:
        --------
            Learned net object; Empty SupervisedDataSet which can be loaded by sample of inspected objects
        '''
        
        return self.net, SupervisedDataSet(self.input_neurons,self.OUTPUT_NEURONS)
        
        
    def train(self, b=None, EPS = 1e-5 , MAX_ITER = 1e9):
        print "Training has begun..."
        # Prepare the network
        self.net = buildNetwork(self.input_neurons, self.hiden_neurons, self.OUTPUT_NEURONS)
        
        # Insert train sample into the network    
        ds = SupervisedDataSet(self.input_neurons, self.OUTPUT_NEURONS)
        
        for i, coord in enumerate(self.X):
            ds.addSample(coord, (self.y[i],))

        # Prepare the network trainer and train them
        trainer = BackpropTrainer(self.net, ds)
        trainer.trainUntilConvergence()
        print "Successfully finished"
        
        """err = 1e9
        i = 0
        while err > EPS:
            err = trainer.train()
            
            i += 1            
            if i > MAX_ITER:
                print "Max number of iterations reached"
                break
        
        print "Successfully finished in %i iterations" % i """
        
        # TODO: Evaluate precision
        #self.evaluate(  )
        
             
    def evaluate(self, coords):
        '''
        
        '''
        
        pred = []
        for coord in coords:
            p =  self.net.activate( coord )[0]
            if p < 0:
                p = 0
            elif p > 1:
                p = 1
            pred.append ( p )
        
        return np.array(pred)
                
            


