import imp
import importlib
import inspect
import os

from lcc.conf import settings


class PackageReader(object):
    """
    Class for managing modules and its classes in a package

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
    NAMES = settings.IMPLEMENTED_CLASSES
    EXCLUDE = ('lcc',)

    def getClasses(self, name):
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
        package_name, base_class = self.NAMES.get(name, None)

        if not package_name:
            return None

        contents = self.getPackageContents(package_name)

        searched_classes = []
        for package_module in contents:
            path = os.path.join(
                package_name, package_module).replace("/", ".")
            module_classes = self.getModuleClasses(
                importlib.import_module(path))
            for module_class in module_classes:
                if issubclass(module_class, base_class):
                    searched_classes.append(module_class)
        return searched_classes

    def getClassesDict(self, package_name):
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
        searched_classes = self.getClasses(package_name)

        classes_dict = {}
        for cls in searched_classes:
            classes_dict[cls.__name__] = cls
        return classes_dict

    def getPackageContents(self, package_name):
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
                    if module.endswith(self.MODULE_EXTENSIONS) and
                    not module.startswith(self.EXCLUDE)])

    def getModuleClasses(self, module):
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
