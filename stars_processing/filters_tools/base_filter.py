'''
Created on May 18, 2016

@author: Martin Vo
'''

import abc
from utils.commons import returns,accepts

class BaseFilter(object):
    __metaclass__ = abc.ABCMeta
    '''
    Base class for all filters. It is something like interface (check whether
    subclasses have certain methods
    '''
    
    @accepts(list)
    @returns(list)
    def applyFilter(self,stars):
        raise NotImplementedError

    #TODO: Check whether these lists contains object of Star class type
