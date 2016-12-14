import os
from os.path import join
from stars_processing.filters_tools.base_filter import BaseFilter,\
    ComparativeSubFilter
from db_tier.base_query import StarsCatalogue
from stars_processing.deciders.base_decider import BaseDecider


#*********    Global variables    **********
# Level of verbosity (higher number means more info)
VERBOSITY = 0

# Delimiter of status files
FILE_DELIM = ";"

JUST_FILTER_OBJECT = True
OBJECT_SUFFIX = "pickle"
CONF_FILE_SEPARATOR = "="

#**********    Folders    *********
# Directory of data and src folders
ROOT_DIR = join( os.path.dirname(os.path.realpath(__file__)) , os.pardir, os.pardir )

# Data folder
TO_THE_DATA_FOLDER = join( ROOT_DIR, "data" )          

# Folder of light curves   
LC_FOLDER = join( TO_THE_DATA_FOLDER, "light_curves" )                     

# Folder of created filter files
FILTERS_PATH = join( TO_THE_DATA_FOLDER, "star_filters" )      

# Folder of input files
INPUTS_PATH = join( TO_THE_DATA_FOLDER, "inputs" )

# Folder of filter tuning outputs
TUNING_LOGS = join( TO_THE_DATA_FOLDER, "tuning_logs" )

# Folder of database files
DB_FILE_PATH = join( TO_THE_DATA_FOLDER, "databases")

#***********    Source packages    *********
# Base directory of source package
BASE_DIR = join( os.pardir  )

# Package of filters implementations
FILTERS_IMPL_PATH = join( BASE_DIR, "stars_processing", "filters_impl" )

# Package of connectors implementations
DB_CONNECTORS = join( BASE_DIR, "db_tier", "connectors" )

# Package of deciders implementations
DECIDERS_PATH = join( BASE_DIR, "stars_processing", "deciders")



#*********    Registration of paths    **********
# Folders of light curves keys - paths
STARS_PATH = {"stars" : join( LC_FOLDER, "some_stars" ),
              "quasars" : join( LC_FOLDER, "quasars" ),
              "eyer_quasars" : join( LC_FOLDER, "qso_eyer" ),
              "mqs_quasars" : join( LC_FOLDER, "mqs_quasars" ),
              "be_eyer" : join( LC_FOLDER, "be_eyer" ),
              "dpv" : join( LC_FOLDER, "dpv" ),
              "lpv" : join( LC_FOLDER, "lpv" ),
              "rr_lyr" : join( LC_FOLDER, "rr_lyr" ),
              "cepheids" : join( LC_FOLDER, "cepheids" ),
              "crossmatch" : join( LC_FOLDER, "crossmatch" )
              }

# Folders of local database files
DATABASES = {"local" : join(DB_FILE_PATH, "local.db"),
             "milliquas" : join( DB_FILE_PATH, "milliquas.db"),
             "ogleII" : join( DB_FILE_PATH, "ogleII.db"),
             "og_milli_crossmatch" : join( DB_FILE_PATH, "og_milli_crossmatch.db")}

# Listen folders of implemented classes
IMPLEMENTED_CLASSES = { "filters" : ( FILTERS_IMPL_PATH, BaseFilter ),
                        "connectors" : ( DB_CONNECTORS, StarsCatalogue ),
                        "sub_filters" : (FILTERS_IMPL_PATH, ComparativeSubFilter),
                        "deciders" : (DECIDERS_PATH, BaseDecider) }
