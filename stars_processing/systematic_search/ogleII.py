'''
Created on Jul 18, 2016

@author: Martin Vo
'''

from stars_processing.systematic_search.searcher import AbstractSearch
from utils.helpers import verbose, create_folder
from conf.glo import VERBOSITY

class OgleSystematicSearch(AbstractSearch):
    '''
    This is systematic search and filtering class for OGLEII. 
    '''
    
    OBT_METHOD = "ogle"

    def __init__(self, filters_list, SAVE_PATH = None, SAVE_LIM = None, UNFOUND_LIM = None):
        '''
        @param filters_list: List of filter type objects
        @param SAVE_PATH: Path from "run" module to the folder where found light curves will be saved
        @param SAVE_LIM: Number of searched objects after which status file will be saved
        @param UNFOUND_LIM: Number of unsuccessful query to interrupt searching  
        '''
        
        AbstractSearch.__init__(self, filters_list, SAVE_PATH, SAVE_LIM, UNFOUND_LIM,OBTH_METHOD = self.OBT_METHOD)
        

    def matchOccur(self, star, query):
        '''
        What to do with star in case of passing thru filtering
        
        @param star: Star type object
        @param query: Dictionary of query for this object
        '''
        
        verbose(star,2, VERBOSITY)
        path = "%s%s_%s" % (self.save_path, query["target"],query["field_num"])
        create_folder(path)
        star.saveStar(path)
        
    
        
        


        