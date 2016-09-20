from os.path import join

#TODO: Upgrade this module and make script for constructing these folders strcuture

#Level of verbosity (higher number means more info)
VERBOSITY = 0

#TODO: Add absolut path!
BASE_DIR = "../"

FILTERS_IMPL_PATH = join(BASE_DIR, "stars_processing", "filters_impl")
DB_CONNECTORS = join(BASE_DIR, "db_tier", "connectors")

TO_THE_DATA_FOLDER = "../../data"                              #Path to the data folder
LC_FOLDER = "light_curves"                                     #Name of folder of light curves

FILTERS_PATH = join( TO_THE_DATA_FOLDER, "star_filters" )       #Path to the folder of prepared filters
FILTERS_OBJ_PATH = join( FILTERS_PATH, "objects")               #Path to the folder of filter objects

OGLE_QSO_PATH = join(TO_THE_DATA_FOLDER, LC_FOLDER, "quasars")      #Path to OGLE qso light curves
EYER_QSO_PATH = join(TO_THE_DATA_FOLDER, LC_FOLDER, "qso_eyer")     #Path to Eyer qso light curves
MQS_QSO_PATH = join(TO_THE_DATA_FOLDER, LC_FOLDER, "mqs_quasars")   #Path to qso light curves from MQS db
BE_STARS_PATH = join(TO_THE_DATA_FOLDER, LC_FOLDER, "be_eyer")      #Path to Eyer Be-Stars light curves"
DPV_PATH = join(TO_THE_DATA_FOLDER, LC_FOLDER, "dpv")               #Path to stars with double period light curves
LPV_PATH = join(TO_THE_DATA_FOLDER, LC_FOLDER, "lpv")               #Path to long periodic stars light curves
RRLYR_PATH = join(TO_THE_DATA_FOLDER, LC_FOLDER, "rr_lyr")          #Path to RR Lyrae light curves
CEP_PATH = join(TO_THE_DATA_FOLDER, LC_FOLDER, "cepheids")          #Path to Cepheids light curves  
STARS_PATH = join(TO_THE_DATA_FOLDER, LC_FOLDER, "some_stars")      #Path to the light curves of nonvariable stars  
