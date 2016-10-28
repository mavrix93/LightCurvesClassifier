'''
Created on Sep 11, 2016

@author: Martin Vo

'''
import imp
import os
import importlib
import inspect

from conf import settings

from entities.exceptions import InvalidFilesPath, InvalidFilteringParams


class PackageReader(object):
    """
    Class for managing modules and its classes in a package
    
    Attributes:
    -----------
        MODULE_EXTENSION : iterable
            Accepted extensions of module files.
        
        NAMES : dict
            Keys are identifiers for path to the package where searched classes
            are located and base filter which all package classes needs to inherit
            in order to be accepted. 
            
        EXCLUDE : iterable
            File names (first letters of them) which will be excluded.
    """

    MODULE_EXTENSIONS = ('.py',)
    NAMES = settings.IMPLEMENTED_CLASSES
    EXCLUDE = ('__init__',)

    def getClasses(self, name):
        """
        Get all classes in the package which inherit base classes according 
        to NAMES attribute
        
        Parameters:
        -----------
            name : str
                Key in NAMES dictionary to package location and parent class
                
        Returns:
        --------
            List of all classes in the package which inherit base classes according 
            to NAMES attribute
        """

        package_name, base_class = self.NAMES.get(name, None)

        if not package_name: return None

        contents = self.getPackageContents(package_name)

        searched_classes = []
        for package_module in contents:
            path = os.path.join(package_name, package_module).replace("/", ".")[3:]
            module_classes = self.getModuleClasses(importlib.import_module(path))
            for module_class in module_classes:
                if issubclass(module_class, base_class):
                    searched_classes.append(module_class)
        return searched_classes

    def getClassesDict(self, package_name):
        searched_classes = self.getClasses(package_name)

        classes_dict = {}
        for cls in searched_classes:
            classes_dict[cls.__name__] = cls
        return classes_dict

    def getPackageContents(self, package_name):
        """
        Get all modules in the package
        
        Parameters:
        -----------
            package_name : str
                Name of the target package specified in NAMES attribute
                
        Returns:
        -------
            Set of module names in the package
        """

        _, pathname, _ = imp.find_module(package_name)

        # Use a set because some may be both source and compiled.
        return set([os.path.splitext(module)[0]
                    for module in os.listdir(pathname)
                    if module.endswith(self.MODULE_EXTENSIONS)
                    and not module.startswith(self.EXCLUDE)])

    def getModuleClasses(self, module):
        """
        Parameters:
        -----------
            module : module
                Module object
        
        Returns:
        ------
            List of classes in the module
        """

        def accept(obj):
            return inspect.isclass(obj) and module.__name__ == obj.__module__

        return [class_ for _, class_ in inspect.getmembers(module, accept)]


class ConfigReader():
    """
    The class manage config files
    
    Attributes:
    -----------
        SEPARATOR : str
            Delimiter symbol which every line in conf file separates into key and value
            
        FILTER_NAME_KEY : str
            Designation (key) for name of the filter
    """

    SEPARATOR = settings.CONF_FILE_SEPARATOR
    FILTER_NAME_KEY = "name"

    def __init__(self, separator=None, filter_name_key=None):
        """
        If parameters is not specified the default values will be used (see above)
        
        Parameters:
        -----------
            separator : str
                Delimiter symbol which every line in conf file separates into key and value
                
            filter_name_key : str
                Designation (key) for the name of the filter
        """

        if separator:
            self.SEPARATOR = separator
        if filter_name_key:
            self.FILTER_NAME_KEY = filter_name_key

    def read(self, file_name):
        """
        The method reads config file.
        
        Parameters:
        -----------
            file_name : str
                Path with name of the conf file to load
                
        Returns:
        --------
            name : str
                Name of the filter
                
            filter_params : dict
                Parameters where word on the left of from separator is key
                and the word on the right side is value
        
        """
        name = None

        try:
            conf_file = open(file_name, "r")
        except IOError:
            raise InvalidFilesPath(file_name)

        filter_params = {}
        for line in conf_file:
            line = line.strip()
            key, value = line.split(self.SEPARATOR)
            key = key.strip()
            value = value.strip()

            if key == self.FILTER_NAME_KEY:
                name = value
            else:
                filter_params[key] = value

        if not name:
            raise InvalidFilteringParams("Name of the filter was not specified by %s key" % self.FILTER_NAME_KEY)

        return name, filter_params
