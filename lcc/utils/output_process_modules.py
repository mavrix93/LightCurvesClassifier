import os
import pickle

from lcc.entities.exceptions import InvalidFilesPath, InvalidFile


def saveIntoFile(obj, path=".", file_name="saved_object.pickle",
                 folder_name=None):
    '''
    This  method serialize object (save it into file)

    obj : object
        Object to serialize

    path : str
        Path to the folder

    file_name : str
        Name of result file

    folder_name : str
        Name of folder

    Returns
    -------
        None
    '''

    path_with_name = "%s/%s" % (path, file_name)
    if folder_name:
        os.makedirs(path_with_name + folder_name)
        path_with_name = "%s/%s/%s" % (path, folder_name, file_name)
    try:
        with open(path_with_name, 'wb') as output:
            pickle.dump(obj, output, pickle.HIGHEST_PROTOCOL)
        print "Object has been saved into %s/%s" % (path, file_name)
    except IOError:
        raise InvalidFilesPath("Path: %s\tfile name: %s" % (path, file_name))


def loadFromFile(file_name="saved_object.pickle"):
    '''
    Open object from file

    Parameters
    ----------
    file_name : str
        Name of the serialized file

    Returns
    -------
    object
        Loaded object
    '''

    try:
        with open(file_name, 'rb') as inputToLoad:
            loaded_object = pickle.load(inputToLoad)
        return loaded_object
    except IOError:
        raise InvalidFilesPath
    except ImportError as e:
        raise InvalidFile(
            "Structure of project has been changed since saving this object: %s" % str(e))
    except TypeError:
        return pickle.load(file_name)
