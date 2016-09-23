'''
Created on Feb 29, 2016

@author: Martin Vo
'''

from conf.package_reader import PackageReader

class StarsProvider(object):
    '''
    Star provider can return one of stars data client to obtain data thru common
    method "getStarsWithCurves". There are class attribute to link stars providers
    with key word. 
    Also thru initializing of a stars providers query validity will be performed
    '''
    
    def __init__(self):
        self.STARS_PROVIDERS = self._mapProviders(PackageReader().getClasses( "connectors" ))
   
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
    
    def _mapProviders( self, available_providers ):
        providers = {}
        
        for provider in available_providers:
            providers[ provider.__name__ ] = provider
            
        return providers
    
    

        
        

    