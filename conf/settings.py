import os
from os.path import join
import sys

from db_tier.base_query import StarsCatalogue
from stars_processing.deciders.base_decider import BaseDecider
from stars_processing.utils.base_descriptor import BaseDescriptor,\
    ComparativeSubFilter


# *********    Global variables    **********
# Level of verbosity (higher number means more info)
VERBOSITY = 0

# Delimiter of status files
FILE_DELIM = ";"

JUST_FILTER_OBJECT = True
OBJECT_SUFFIX = "pickle"
CONF_FILE_SEPARATOR = "="

# **********    Folders    *********
# Directory of data and src folders
ROOT_DIR = join(
    os.path.dirname(os.path.realpath(__file__)), os.pardir, os.pardir)

sys.path.append(join(ROOT_DIR, "src"))

# Data folder
TO_THE_DATA_FOLDER = join(ROOT_DIR, "data")

# Folder of light curves
LC_FOLDER = join(TO_THE_DATA_FOLDER, "light_curves")

# Folder of created filter files
FILTERS_PATH = join(TO_THE_DATA_FOLDER, "star_filters")

# Folder of input files
INPUTS_PATH = join(TO_THE_DATA_FOLDER, "inputs")

# Folder of filter tuning outputs
TUNING_LOGS = join(TO_THE_DATA_FOLDER, "tuning_logs")

# Folder of database files
DB_FILE_PATH = join(TO_THE_DATA_FOLDER, "databases")

# ***********    Source packages    *********
# Base directory of source package
BASE_DIR = os.pardir

# Package of filters implementations
FILTERS_IMPL_PATH = join("stars_processing", "filters_impl")


# Package of connectors implementations
DB_CONNECTORS = join("db_tier", "connectors")

# Package of deciders implementations
DECIDERS_PATH = join("stars_processing", "deciders")


# *********    Registration of paths    **********

# Listen folders of implemented classes
IMPLEMENTED_CLASSES = {"filters": (FILTERS_IMPL_PATH, BaseDescriptor),
                       "connectors": (DB_CONNECTORS, StarsCatalogue),
                       "sub_filters": (FILTERS_IMPL_PATH, ComparativeSubFilter),
                       "deciders": (DECIDERS_PATH, BaseDecider)}


# Folders of light curves keys - paths
class _StarsPaths():

    def __init__(self, root_path):
        self.root_path = root_path

    def __getitem__(self, item_key):
        return join(self.root_path, item_key)

STARS_PATH = _StarsPaths(LC_FOLDER)
