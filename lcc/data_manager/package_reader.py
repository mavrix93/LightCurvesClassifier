import imp
import importlib
import inspect
import os
import sys

from lcc.db_tier.base_query import StarsCatalogue
from lcc.stars_processing.utilities.base_decider import BaseDecider
from lcc.stars_processing.utilities.base_descriptor import BaseDescriptor


class PackageReader(object):
    """
    Class for managing modules and its classes in the package

    Attributes
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
    EXCLUDE = tuple()
    NAMES = {"descriptors": (["lcc/stars_processing/descriptors"], BaseDescriptor),
             "connectors": (["lcc/db_tier/connectors"], StarsCatalogue),
             "deciders": (["lcc/stars_processing/deciders"], BaseDecider),
             "unsup_deciders": (["lcc/stars_processing/deciders/unsupervised"], BaseDecider)}

    @classmethod
    def getClasses(cls, name):
        """
        Get all classes in the package which inherit base classes according
        to `NAME` attribute

        Parameters
        -----------
        name : str
            Key in `NAME` dictionary to package location and parent class

        Returns
        --------
        list
            List of all classes in the package which inherit base classes
            according to `NAME` attribute
        """
        package_name_list, base_class = cls.NAMES.get(name, [None, None])

        if base_class is None and package_name_list is None:
            raise ImportError("Group {} doesn't exist".format(name))

        searched_classes = []
        for package_name in package_name_list:
            if not package_name:
                return None

            contents = cls.getPackageContents(package_name)

            for package_module in contents:
                path = os.path.join(
                    package_name, package_module).replace("/", ".")
                try:
                    module_classes = cls.getModuleClasses(
                        importlib.import_module(path))
                    for module_class in module_classes:
                        if issubclass(module_class, base_class):
                            searched_classes.append(module_class)
                except:
                    pass
        return searched_classes

    @classmethod
    def getClassesDict(cls, package_name):
        """
        Get dictionary of all classes in the package which inherit base classes
        according to `NAME` attribute

        Parameters
        -----------
        package_name : str
            Key in `NAME` dictionary to package location and parent class

        Returns
        --------
        dict
            Dictionary of all classes in the package which inherit base classes
            according to `NAME` attribute
        """
        searched_classes = cls.getClasses(package_name)

        classes_dict = {}
        for cls in searched_classes:
            classes_dict[cls.__name__] = cls
        return classes_dict

    @classmethod
    def getPackageContents(cls, package_name):
        """
        Get all modules in the package

        Parameters
        -----------
        package_name : str
            Name of the target package specified in `NAMES` attribute

        Returns
        -------
        set
            Set of module names in the package
        """
        _, pathname, _ = imp.find_module(package_name)

        # Use a set because some may be both source and compiled.
        return set([os.path.splitext(module)[0]
                    for module in os.listdir(pathname)
                    if module.endswith(cls.MODULE_EXTENSIONS) and
                    not module.startswith(cls.EXCLUDE)])

    @classmethod
    def getModuleClasses(cls, module):
        """
        Parameters
        -----------
        module : module
            Module object

        Returns
        -------
        list
            List of classes in the module
        """

        def accept(obj):
            return inspect.isclass(obj) and module.__name__ == obj.__module__

        return [class_ for _, class_ in inspect.getmembers(module, accept)]

    @classmethod
    def appendModules(cls, group_key, path):
        group = cls.NAMES.get(group_key)

        path_list = path.split("/")
        if len(path_list) == 1:
            path_list = ["."] + path_list

        upper_folder = os.path.join(*path_list[:-1])
        folder_name = path_list[-1]

        if path.startswith("/"):
            upper_folder = "/" + upper_folder

        if not os.path.exists(os.path.join(upper_folder, "__init__.py")):
            os.mknod(os.path.join(upper_folder, "__init__.py"))

        if not os.path.exists(os.path.join(path, "__init__.py")):
            os.mknod(os.path.join(path, "__init__.py"))

        if group is None:
            raise ImportError("Group {} doesn't exist".format(group_key))

        sys.path.insert(0, upper_folder)
        group[0].append(folder_name)
