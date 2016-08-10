'''
Created on Apr 26, 2016

@author: Martin Vo
'''

from utils.helpers import verbose, check_path
from stars_processing.filtering_manager import FilteringManager
from conf.glo import VERBOSITY, TO_THE_DATA_FOLDER, LC_FOLDER
from warnings import warn

import abc
from entities.exceptions import QueryInputError, InvalidFilesPath
from db_tier.stars_provider import StarsProvider
import os

#TODO: Think more about propriety of location of this class
#TODO: Make this class general for every db manager



class StarsSearcher():
    '''
    Common class for every systematic db search class 
    '''
    
    DEF_SAVE_PATH = TO_THE_DATA_FOLDER + LC_FOLDER
    DEF_SAVE_LIM = 50
    DEF_UNFOUND_LIM = 150
   

    def __init__(self,filters_list, SAVE_PATH = None ,SAVE_LIM = None, UNFOUND_LIM = None, OBTH_METHOD = None):
        '''
        @param filters_list: List of filter type objects
        @param SAVE_PATH: Path from "run" module to the folder where found light curves will be saved
        @param SAVE_LIM: Number of searched objects after which status file will be saved
        '''
        
        
        #Default values warning and setting
        if SAVE_PATH == None:
            SAVE_PATH = self.DEF_SAVE_PATH
            warn("Path to the save folder was not specified.\nSetting default path: %s" % (SAVE_PATH))
        if SAVE_LIM == None:
            SAVE_LIM = self.DEF_SAVE_LIM
            warn("Save limit was not specified.\nSetting default value: %i" % SAVE_LIM)
        if UNFOUND_LIM == None:
            UNFOUND_LIM = self.DEF_UNFOUND_LIM
            warn("Max number of failed queries in order to end searching need to be specified.\nSetting default value: %i" % UNFOUND_LIM)
        if OBTH_METHOD == None:
            raise QueryInputError("Database for searching need to be specified in a class which inherits this abstract class")
             
        self.filteringManager = FilteringManager()        
        
        #Load all filters from given list
        for filt in filters_list:
            self.filteringManager.loadFilter(filt)
        
        self.save_path = SAVE_PATH
        self.OBTH_METHOD = OBTH_METHOD
        self.SAVE_LIM = SAVE_LIM      
        self.UNFOUND_LIM = UNFOUND_LIM
        
        
    def filterStar(self,star, query):
        '''
        This method filter given star in list.
        In case of match method "matchOccur" will be performed
        
        @param stars: List of 1 star type object
        ''' 
        
        self.filteringManager.stars = [star]
        
        #Get stars passed thru filtering    
        result = self.filteringManager.performFiltering()
        
        if len(result) == 1:
            verbose("Match!", 2, VERBOSITY)
            self.matchOccur(result[0],query)
            return True
        elif len(result) > 1:
            warn("There are more then one star meeting query parameters!")
        return False
        
    #NOTE: Default behavior. It can be overridden.
    def matchOccur(self,star,query = None):
        '''
        What to do with star which passed thru filtering
        
        @param star: Star object which will be saved as light curve
        @param query: Optional query informations. 
        '''
        
        verbose(star,2, VERBOSITY)
        star.saveStar(self.save_path)
    
    #NOTE: Default behavior. It can be overwritten.    
    def failProcedure(self,query,err = None):
        '''
        What to do if a fail occurs
        
        @param query: Query informations
        @param err: Error message
        '''
           
        print "Error occurred during filtering:",err
     
    #NOTE: Default behavior. It can be overwritten.    
    def statusFile(self,query,status):
        '''
        This method generate status file for overall query in certain db.
        Every queried star will be noted.
        
        @param dict query: Query informations
        @param dict status: Information whether queried star was found, filtered and passed thru filtering        
        '''
        file_name = self.save_path+"%s_db.txt" % self.OBTH_METHOD
        try:
            empty_file = os.stat(file_name).st_size == 0
        except OSError:
            empty_file = True
        
        file_name = check_path(file_name)
        with open(file_name, "a") as status_file:
            if empty_file:
                status_file.write("#")
                for key in query:
                    status_file.write(str(key)+"\t")
                for key in status:
                    status_file.write(str(key)+"\t")
                status_file.write("\n")
                
            for key in query:
                status_file.write(str(query[key])+"\t")
            for key in status:
                status_file.write(str(status[key])+"\t")
            status_file.write("\n")
   
    def queryStars(self,queries):
        '''
        Query db according to list of queries
        
        @param queries: List of dictionaries of queries for certain db 
        '''
        
        unfound_counter = 0
        for query in queries:            
            status = {"found": False, "filtered":False, "passed":False}
            try:
                stars = StarsProvider().getProvider(obtain_method = self.OBTH_METHOD, **query).getStarsWithCurves()
            except QueryInputError:
                raise
            except:
                warn("Couldn't download the light curve")
                stars = []
                      
            #Check if searched star was found
            result_len = len(stars)
            if result_len == 0:
                warn("No stars were found: %s\n." %(query))
                unfound_counter += 1
                if unfound_counter > self.UNFOUND_LIM:
                    warn("Max number of unsatisfied queries reached: %i" % self.UNFOUND_LIM)
                    break

            else:          
                status["found"] = True
                unfound_counter = 0
                
                contain_lc = True
                try:
                    stars[0].lightCurve.time
                except AttributeError:
                    contain_lc = False
                    
                if contain_lc:
                    #Try to apply filters to the star
                    try:
                        passed = self.filterStar(stars[0],query)
                        status["filtered"] = True
                        status["passed"] = passed
                    except IOError as err:
                        raise InvalidFilesPath(err)
                    except Exception as err:
                        self.failProcedure(query,err)
                        warn("Something went wrong during filtering")
            self.statusFile(query, status)

       

        