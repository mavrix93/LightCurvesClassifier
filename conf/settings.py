import os
from os.path import join
from stars_processing.filters_tools.base_filter import BaseFilter,\
    ComparativeSubFilter
from db_tier.base_query import LightCurvesDb
from stars_processing.deciders.base_decider import BaseDesider

#TODO: Upgrade this module and make script for constructing these folders structure


#Level of verbosity (higher number means more info)
VERBOSITY = 0

OBJECT_SUFFIX = "pickle"
CONF_FILE_SEPARATOR = "="

FILE_DELIM = ";"

# TODO
ROOT_DIR = join( os.path.dirname(os.path.realpath(__file__)) , os.pardir, os.pardir )
BASE_DIR = ".."

FILTERS_IMPL_PATH = join( BASE_DIR, "stars_processing", "filters_impl" )
DB_CONNECTORS = join( BASE_DIR, "db_tier", "connectors" )
DECIDERS_PATH = join( BASE_DIR, "stars_processing", "deciders")

TO_THE_DATA_FOLDER = join( ROOT_DIR, "data" )               #Path to the data folder
LC_FOLDER = join( TO_THE_DATA_FOLDER, "light_curves" )                                    #Name of folder of light curves

FILTERS_PATH = join( TO_THE_DATA_FOLDER, "star_filters" )       #Path to the folder of prepared filters
INPUTS_PATH = join( TO_THE_DATA_FOLDER, "inputs" )
TUNING_LOGS = join( TO_THE_DATA_FOLDER, "tuning_logs" )
#
IMPLEMENTED_CLASSES = { "filters" : ( FILTERS_IMPL_PATH, BaseFilter ),
                        "connectors" : ( DB_CONNECTORS, LightCurvesDb ),
                        "sub_filters" : (FILTERS_IMPL_PATH, ComparativeSubFilter),
                        "deciders" : (DECIDERS_PATH, BaseDesider) }

STARS_PATH = {"stars" : join( LC_FOLDER, "some_stars" ),
              "quasars" : join( LC_FOLDER, "quasars" ),
              "eyer_quasars" : join( LC_FOLDER, "qso_eyer" ),
              "mqs_quasars" : join( LC_FOLDER, "mqs_quasars" ),
              "be_eyer" : join( LC_FOLDER, "be_eyer" ),
              "dpv" : join( LC_FOLDER, "dpv" ),
              "lpv" : join( LC_FOLDER, "lpv" ),
              "rr_lyr" : join( LC_FOLDER, "rr_lyr" ),
              "cepheids" : join( LC_FOLDER, "cepheids" ),
              }

DB_FILE_PATH = join( TO_THE_DATA_FOLDER, "databases")

DATABASES = {"local" : join(DB_FILE_PATH, "local.db"),
             "milliquas" : join( DB_FILE_PATH, "milliquas.db"),
             "ogleII" : join( DB_FILE_PATH, "ogleII.db")}
