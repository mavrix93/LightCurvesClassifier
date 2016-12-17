'''
Created on Dec 8, 2016

@author: Martin Vo
'''

import numpy as np
from matplotlib import pyplot as plt

from stars_processing.deciders.base_decider import BaseDecider

class UnsupervisedBase( BaseDecider ):
    '''
    classdocs
    '''
    def __init__(self,  classifier, params, treshold = 0.5,**kwargs):
        super( UnsupervisedBase, self).__init__( **kwargs )
        self.classifier = classifier( **params)


    def learn(self, coords ):
        self.X = np.array(coords)
        self.classifier.fit( coords )
        
    def evaluate(self, star_coords):
        return self.classifier.predict( star_coords )
    
    def plotProbabSpace(self):
        h = .02
         
        x_min, x_max = self.X[:, 0].min() - 1, self.X[:, 0].max() + 1
        y_min, y_max = self.X[:, 1].min() - 1, self.X[:, 1].max() + 1
        xx, yy = np.meshgrid(np.arange(x_min, x_max, h), np.arange(y_min, y_max, h))
        
        # Obtain labels for each point in mesh. Use last trained model.
        Z = self.classifier.predict(np.c_[xx.ravel(), yy.ravel()])
        
        # Put the result into a color plot
        Z = Z.reshape(xx.shape)
        plt.figure(1)
        plt.clf()
        plt.imshow(Z, interpolation='nearest',
                   extent=(xx.min(), xx.max(), yy.min(), yy.max()),
                   cmap=plt.cm.Paired,
                   aspect='auto', origin='lower')
        
        plt.plot(self.X[:, 0], self.X[:, 1], 'k.', markersize=2)
        # Plot the centroids as a white X
        centroids = self.classifier.cluster_centers_
        plt.scatter(centroids[:, 0], centroids[:, 1],
                    marker='x', s=169, linewidths=3,
                    color='w', zorder=10)
        plt.title('')
        plt.xlim(x_min, x_max)
        plt.ylim(y_min, y_max)
        plt.xticks(())
        plt.yticks(())
        plt.show()
        