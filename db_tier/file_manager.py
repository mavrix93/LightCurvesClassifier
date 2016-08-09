'''
Created on Jan 27, 2016

@author: Martin Vo
'''

from entities.star import Star
from entities.light_curve import LightCurve
import glob
import warnings
from utils.commons import  args_type,\
    default_values, mandatory_args
from base_query import LightCurvesDb
from utils.output_process_modules import loadFromFile
from entities.exceptions import InvalidFilesPath, InvalidFile
from utils.helpers import verbose
from conf.glo import VERBOSITY

class FileManager(LightCurvesDb):
    '''This class is responsible for managing data in files'''
    

    #Query possibilities (combination of necessary values)       
    #Check types of given parameters 
    #Set default values if they are not specified
    @mandatory_args(("path",))
    @default_values(suffix="dat",star_class="star",files_limit=None, db_ident = "ogle")
    @args_type(path=str,object_file_name=str,suffix=str,star_class=str,files_limit=int, db_ident=str)
    def __init__(self,obtain_params):
        '''
        @param obtain_params: Query dictionary
        '''

        #This decides whether load star curves from file or object of stars
        if ("object_file_name" in obtain_params):
            self.object_file_name = obtain_params["object_file_name"]
        else: self.object_file_name = None
        
 
        self.starClass = obtain_params["star_class"]
        self.files_limit = obtain_params["files_limit"]
        self.suffix = obtain_params["suffix"]   
        self.path = obtain_params["path"]
        self.db_ident = obtain_params["db_ident"]
  
    def getStarsWithCurves(self):
        '''Common method for all stars provider
        
        If there are inserted object_file_name in query dictionary, object file
        of list of stars is loaded. In other case files from given path of
        the folder is loaded into star objects.
    
        @param  starClass:    Type of object star object 
        @return: stars:      List of stars with light curves
        '''
        if (self.object_file_name != None):
            return self._load_stars_object()
     
        return self._load_stars_from_folder()
         
        
        
    def _load_stars_from_folder(self):  
        '''
        Load all files with certain suffix as light curves
        
        @return: Stars with light curves
        '''  
        
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
            verbose("Loading stars %i/%i" % (counter,numberOfFiles),2, VERBOSITY)
            lc = LightCurve(singleFile)
            
            #Check if light curve is not empty
            if (len(lc.mag)>=1):
                db_ident = self.parseFileName(singleFile)
                star = Star(ident={self.db_ident:{"name":db_ident}})
                star.starClass = self.starClass
                
                star.putLightCurve(lc)
                stars.append(star)
            counter +=1
        return stars  


    def _load_stars_object(self):
        '''
        Load object file of list of stars
        
        @return: Stars with light curves
        ''' 
        
        stars = loadFromFile(self.path, self.object_file_name)
        
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


            
    


            

           
            