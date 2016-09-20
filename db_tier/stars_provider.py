'''
Created on Feb 29, 2016

@author: Martin Vo
'''

#TODO: Make a config file for db provider key - module name, in order to 
#import these classes

from db_tier.connectors.file_manager import FileManager
from db_tier.connectors.ogle_client import OgleII

class StarsProvider(object):
    '''
    Star provider can return one of stars data client to obtain data thru common
    method "getStarsWithCurves". There are class attribute to link stars providers
    with key word. 
    Also thru initializing of a stars providers query validity will be performed
    '''
    
    STARS_PROVIDERS = {"file":FileManager,"ogle":OgleII}

   
    def getProvider(self,obtain_method = "",**kwargs):
        '''
        @param obtain_method: Query dictionary
        @param obtain_params:  Key word for query method
        @return: Unified stars provider object
        
        In case of no kwargs provider object will be returned
        '''
        if not obtain_method in self.STARS_PROVIDERS:
            raise AttributeError("Unresolved stars provider\nAvaible stars providers: %s"%self.STARS_PROVIDERS)
        
        if ("obtain_params" in kwargs): kwargs = kwargs["obtain_params"]
        provider = self.STARS_PROVIDERS[obtain_method]
        
        if len(kwargs) == 0:
            return provider
        return provider(kwargs)
    
    

        
        

    