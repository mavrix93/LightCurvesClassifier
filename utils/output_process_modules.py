'''
Created on Feb 5, 2016

@author: Martin Vo

'''
import pickle
from entities.exceptions import InvalidFilesPath, InvalidFile
import os
        

def saveIntoFile(obj,path,fileName="saved_object",folder_name=None):
    '''This  method serialize object (save it into file)''' 

    path_with_name = "%s/%s" % (path, fileName)
    if folder_name:
        os.makedirs(path_with_name+folder_name)
        path_with_name = "%s/%s/%s" % (path, folder_name,fileName)
    try:
        with open(path_with_name,'wb') as output:
            pickle.dump(obj, output, pickle.HIGHEST_PROTOCOL)
        print "Object has been saved into %s/%s" % (path,fileName)
    except IOError:
        raise InvalidFilesPath
    
def loadFromFile(path,fileName):    
    ''' Open object from file '''
    
    pathWithName = "%s/%s" % (path, fileName)
    try:
        with open(pathWithName,'rb') as inputToLoad:
            loaded_object =pickle.load(inputToLoad)
        return loaded_object 
    except IOError:
        raise InvalidFilesPath
    except ImportError:
        raise InvalidFile("Structure of project has been changed since saving this object")
        
        
       




        


