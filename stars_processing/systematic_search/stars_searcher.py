'''
Created on Apr 26, 2016

@author: Martin Vo
'''

from utils.helpers import verbose, progressbar, create_folder, cut_path
from stars_processing.filtering_manager import FilteringManager
from conf.settings import VERBOSITY, TO_THE_DATA_FOLDER, LC_FOLDER
from warnings import warn

from entities.exceptions import QueryInputError, InvalidFilesPath
from db_tier.stars_provider import StarsProvider
import os
import warnings
from db_tier.local_stars_db.stars_mapper import StarsMapper
from conf import settings
import collections

# TODO: Think more about propriety of location of this class
# TODO: Make this class general for every db manager


class StarsSearcher():
    '''
    Common class for every systematic db search class 
    '''
    
    DEF_SAVE_PATH = TO_THE_DATA_FOLDER + LC_FOLDER
    DEF_SAVE_LIM = 50
    DEF_UNFOUND_LIM = 150
   

    def __init__(self,filters_list, SAVE_PATH = None, SAVE_LIM = None, UNFOUND_LIM = None, OBTH_METHOD = None, db_key = "local"):
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
            raise QueryInputError("Database for searching need to be specified.")
             
        self.filteringManager = FilteringManager()        
        
        #Load all filters from given list
        for filt in filters_list:
            self.filteringManager.loadFilter(filt)
        
        if SAVE_PATH.startswith("HERE:"):
            SAVE_PATH = SAVE_PATH[5:]
        else:
            SAVE_PATH = os.path.join( settings.LC_FOLDER , SAVE_PATH) 
        if os.path.isdir(SAVE_PATH):
            self.save_path = SAVE_PATH
        else:
            SAVE_PATH = os.path.join( settings.LC_FOLDER , SAVE_PATH)
            try:                
                create_folder( SAVE_PATH )
                self.save_path = SAVE_PATH
                warnings.warn("Output folder %s was created because it has not existed.\n" % (SAVE_PATH))
            except:
                warnings.warn("Invalid save path. Current folder was set")
                self.save_path = "."
            
        self.OBTH_METHOD = OBTH_METHOD
        self.SAVE_LIM = SAVE_LIM      
        self.UNFOUND_LIM = UNFOUND_LIM
        
        self.db_key = db_key
        
        filt_name = ""
        for filt in filters_list:
            filt_name += "_" + filt.__class__.__name__
        self.filt_name = filt_name
        
        self.not_uploaded = []
            
        
        
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
            self.matchOccur(result[0],query)
            return True
        elif len(result) > 1:
            warn("There are more then one star meeting query parameters!")
        return False
        
    #NOTE: Default behavior. It can be overridden.
    def matchOccur(self, star, query = None):
        '''
        What to do with star which passed thru filtering
        
        @param star: Star object which will be saved as light curve
        @param query: Optional query informations. 
        '''
        
        verbose(star,2, VERBOSITY)
        
        lc_path = star.saveStar(self.save_path)
        
        mapper = StarsMapper( self.db_key )
        if not mapper.uploadStar(star, cut_path(lc_path, "light_curves")):
            self.not_uploaded.append(star)
    
    #NOTE: Default behavior. It can be overwritten.    
    def failProcedure(self,query,err = None):
        '''
        What to do if a fail occurs
        
        @param query: Query informations
        @param err: Error message
        '''
        warnings.warn( "Error occurred during filtering: %s" % err)
     
    #NOTE: Default behavior. It can be overwritten.    
    def statusFile(self,query,status):
        '''
        This method generate status file for overall query in certain db.
        Every queried star will be noted.
        
        @param dict query: Query informations
        @param dict status: Information whether queried star was found, filtered and passed thru filtering        
        '''
        
        file_name = os.path.join( self.save_path, "%s%s.txt" % (self.OBTH_METHOD, self.filt_name ) )
        try:
            empty_file = os.stat(file_name).st_size == 0
        except OSError:
            empty_file = True
        
        with open(file_name, "a") as status_file:
            if empty_file:
                status_file.write("#")
                for i, key in enumerate(query):
                    delim = settings.FILE_DELIM                        
                    status_file.write(str(key)+ delim)
                for i, key in enumerate(status):
                    if i >= len(status)-1:
                        delim = ""
                    else:
                        delim = settings.FILE_DELIM                    
                    
                    status_file.write(str(key)+delim)
                status_file.write("\n")
                
            for i, key in enumerate(query):
                delim = settings.FILE_DELIM       
                        
                status_file.write(str(query[key])+ delim)
            for i, key in enumerate(status):
                if i >= len(status)-1:
                    delim = ""
                else:
                    delim = settings.FILE_DELIM   
                    
                status_file.write(str(status[key])+ delim)
            status_file.write("\n")
   
    def queryStars(self,queries):
        '''
        Query db according to list of queries
        
        @param queries: List of dictionaries of queries for certain db 
        '''
        
        stars_num = 0
        passed_num = 0
        
        all_unfound = 0
        unfound_counter = 0
        for query in progressbar(queries, "Query: "):            
            status = collections.OrderedDict( (("found", False), ("filtered", False), ("passed", False)) )
            try:
                stars = StarsProvider().getProvider(obtain_method = self.OBTH_METHOD, **query).getStarsWithCurves()
                
            except QueryInputError:
                raise
            except:
                raise
                warn("Couldn't download the light curve")
                stars = []
                      
            #Check if searched star was found
            result_len = len(stars)
            if result_len == 0:
                unfound_counter += 1
                all_unfound += 1
                if unfound_counter > self.UNFOUND_LIM:
                    warn("Max number of unsatisfied queries reached: %i" % self.UNFOUND_LIM)
                    break

            else:    
                unfound_counter = 0   
                for one_star in stars: 
                    status["found"] = True
                    
                    
                    contain_lc = True
                    try:
                        stars[0].lightCurve.time
                    except AttributeError:
                        contain_lc = False
                    
                    
                    if contain_lc:
                        #Try to apply filters to the star
                        try:
                            # TODO: Case of multiple stars, not just one as assumed
                            passed = self.filterStar(one_star,query)
                            status["filtered"] = True
                            status["passed"] = passed
                            stars_num += 1
                            if passed: passed_num += 1
                            
                        except IOError as err:
                            raise InvalidFilesPath(err)
                        except Exception as err:
                            self.failProcedure(query,err)
                            warn("Something went wrong during filtering")
                    query["name"] = one_star.getName()
                    self.statusFile(query, status)
        
        print "\n************\t\tQuery is done\t\t************"    
        print "Query results:\nThere are %i stars passed thru filtering from %s." % (passed_num, stars_num)
        if all_unfound: print "There are %i stars which was not found" % all_unfound
        if self.not_uploaded:
            print "\t%i stars have not been uploaded into local db, because they are already there." % len(self.not_uploaded)

       

        