
src.conf package
****************


Submodules
==========


src.conf.deciders_settings module
=================================

**src.conf.deciders_settings.PRECISION(true_pos, false_pos, true_neg,
false_neg)**


src.conf.filter_loader module
=============================

**class src.conf.filter_loader.FilterLoader(file_name,
pickle_object=False)**

   Bases: ``object``

   This class is responsible for reconstructing filter objects from
   files

   ``FILTER_PATH``

      *str* -- Path to the folder of filter conf files

   ``FILTERS_KEY``

      *str* -- Identifier for filters in PackageReader

   ``file_name``

      *str* -- Name of the configuration file

   ``available_filters``

      *list* -- List of available filters

   ``FILTERS_KEY = 'filters'``

   ``FILTER_PATH = '/home/martin/worksp ... ./../data/star_filters'``

   **getFilter()**

      Get stars filter object

      :Returns:
         Constructed filter object

      :Return type:
         BaseFilter instance


src.conf.package_reader module
==============================

**class src.conf.package_reader.PackageReader**

   Bases: ``object``

   Class for managing modules and its classes in a package

   ``MODULE_EXTENSION``

      *iterable* -- Accepted extensions of module files.

   ``NAMES``

      *dict* -- Keys are identifiers for path to the package where
      searched classes are located and base filter which all package
      classes needs to inherit in order to be accepted.

   ``EXCLUDE``

      *iterable* -- File names (first letters of them) which will be
      excluded.

   ``EXCLUDE = ('__init__',)``

   ``MODULE_EXTENSIONS = ('.py',)``

   ``NAMES = {'sub_filters': ('.. ... e_filter.BaseFilter'>)}``

   **getClasses(name)**

      Get all classes in the package which inherit base classes
      according to *NAME* attribute

      :Parameters:
         **name** (*str*) -- Key in *NAME* dictionary to package
         location and parent class

      :Returns:
         List of all classes in the package which inherit base classes
         according to *NAME* attribute

      :Return type:
         list

   **getClassesDict(package_name)**

      Get dictionary of all classes in the package which inherit base
      classes according to *NAME* attribute

      :Parameters:
         **package_name** (*str*) -- Key in *NAME* dictionary to
         package location and parent class

      :Returns:
         Dictionary of all classes in the package which inherit base
         classes according to *NAME* attribute

      :Return type:
         dict

   **getModuleClasses(module)**

      :Parameters:
         **module** (*module*) -- Module object

      :Returns:
         List of classes in the module

      :Return type:
         list

   **getPackageContents(package_name)**

      Get all modules in the package

      :Parameters:
         **package_name** (*str*) -- Name of the target package
         specified in *NAMES* attribute

      :Returns:
         Set of module names in the package

      :Return type:
         set


src.conf.settings module
========================


Module contents
===============
