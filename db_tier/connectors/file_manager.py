'''
Created on Jan 27, 2016

@author: Martin Vo
'''

import os
import glob

from db_tier.base_query import LightCurvesDb
from utils.commons import  args_type,\
    mandatory_args
from utils.output_process_modules import loadFromFile
from utils.helpers import verbose
from conf.settings import VERBOSITY

# Throws:
from entities.exceptions import InvalidFilesPath, InvalidFile
from entities.star import Star
from entities.light_curve import LightCurve


class FileManager(LightCurvesDb):
    '''This class is responsible for managing light curve files
    
    Attributes:
    -----------
        path : str
            Path to the folder of light curves files or light curves pickle file
            
        star_class : str
            Name of the loaded star-like type (e.g. Cepheids)
            
        suffix : str
            Suffix of light curve files in the folder (specified in path attribute)
        
        files_limit : int
            Number of files which will be loaded
            
        db_ident : str
            Name of the database to which the file name will be assigned (without suffix).
            
            EXAMPLE:
                For the file "my_macho_star.dat" and given db_ident as "macho"
                makes Star object: 
                
                star.ident["macho"] --> my_macho_star
                
        files_to_load : iterable of str
            List of file names which should be loaded from the given folder.
            If it is not specified all files will be loaded
            
        object_file_name : str
            Name of the pickle file which contains list of star objects
    
    
    '''
    
    DEFAULT_SUFFIX = "dat"
    DEFAULT_STARCLASS = "star"
    
    # Query possibilities (combination of necessary values)       
    # Check types of given parameters 
    @mandatory_args(("path",))
    @args_type(path = str,
               object_file_name = str,
               suffix = str,
               star_class = str,
               files_limit = int,
               db_ident = str)
    def __init__(self,obtain_params):
        '''
        Parameters:
        -----------
        obtain_params : dict
            Query dictionary (see class Attributes doc above)
        '''

        self.path = obtain_params["path"]
        self.star_class = obtain_params.get( "star_class", self.DEFAULT_STARCLASS )
        self.suffix = obtain_params.get( "suffix", self.DEFAULT_SUFFIX )         
        self.files_limit = obtain_params.get("files_limit", None )
        self.db_ident = obtain_params.get( "db_ident", None)
        self.files_to_load = obtain_params.get( "files_to_load", None)        
        self.object_file_name = obtain_params.get( "object_file_name", None )        

  
    def getStarsWithCurves(self):
        '''Common method for all stars provider
        
        If there are object_file_name in query dictionary, the object file
        of list of stars is loaded. In other case files from given path of
        the folder is loaded into star objects.
    
        Attributes:
        -----------
            star_class : str
                Type of object star objects
        
        Return:
        --------
            stars : list of Star objects
                Star objects with light curves
        '''
        
        if self.object_file_name:
            return self._load_stars_object()     
        return self._load_stars_from_folder()   
        
    def _load_stars_from_folder(self):  
        '''Load all files with a certain suffix as light curves'''  
        
        #Check whether the path ends with "/" sign, if not add  
        if not (self.path.endswith("/")):
            self.path = self.path +"/"
        
        #Get all light curve files (all files which end with certain suffix    
        starsList = glob.glob("%s*%s" %(self.path,self.suffix))
        numberOfFiles= len(starsList)
        if (numberOfFiles == 0):            
            raise InvalidFilesPath("There are no stars in %s with suffix %s" %(self.path,self.suffix))
        
        verbose("Number of stars in given directory is %i" % numberOfFiles,3,VERBOSITY)
        
        if (numberOfFiles < self.files_limit):
            self.files_limit = None
        if (self.files_limit == None):
            verbose("Loading all stars",3,VERBOSITY)
        else:
            verbose("Loading just %i of %i\n\n" % (self.files_limit,numberOfFiles),3,VERBOSITY)
            numberOfFiles = self.files_limit
        
        stars = []
        counter = 1
        #Load every light curve and put it into star object
        for singleFile in starsList[:numberOfFiles]:
            if self.files_to_load and os.path.basename(singleFile) not in self.files_to_load:
                break

            verbose("Loading stars %i/%i" % (counter,numberOfFiles),2, VERBOSITY)
            lc = LightCurve(singleFile)
            
            #Check if light curve is not empty
            if (len(lc.mag)>=1):
                db_ident = self.parseFileName(singleFile)
                
                if self.db_ident:
                    ident = { self.db_ident : { "name" : db_ident }}
                else:
                    ident = {}
                    
                star = Star(ident=ident)
                star.starClass = self.star_class
                
                star.putLightCurve(lc)
                stars.append(star)
            counter +=1
        return stars  


    def _load_stars_object(self):
        '''Load object file of list of stars''' 
        
        stars = loadFromFile(os.path.join(self.path, self.object_file_name))
        
        if (len(stars) == 0): raise InvalidFile("There are no stars in object file")        
        if (stars[0].__class__.__name__  != "Star"): raise InvalidFile("It is not list of stars")
        
        return stars 
    

    @staticmethod
    def parseFileName(file_path):  
        '''Return cleaned name of the star without path and suffix'''      
        end = None
        if file_path.rfind(".") != -1:
            end = file_path.rfind(".")
        return file_path[file_path.rfind("/")+1:end]
