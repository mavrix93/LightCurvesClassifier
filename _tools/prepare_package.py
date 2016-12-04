'''
Created on Nov 11, 2016

@author: martin
'''
from utils.helpers import create_folder
from conf.settings import TO_THE_DATA_FOLDER, LC_FOLDER, FILTERS_PATH,\
    TUNING_LOGS, DB_FILE_PATH, INPUTS_PATH
import os
from conf import settings
from distutils.dir_util import copy_tree



def create_data_structure( examples = False ):
    """
    
    """
    
    to_create = [TO_THE_DATA_FOLDER, LC_FOLDER, FILTERS_PATH, INPUTS_PATH, TUNING_LOGS, DB_FILE_PATH]
    
    for fold in to_create:
        if create_folder( fold ):
            print "Created: ", fold
            
    if examples:
        for fold in to_create[1:-1]:
            pa = os.path.join(fold, "examples")
            if create_folder( pa ):
                print "Example folder created: ", pa
        move_example_data()
        make_examples()
    
def make_examples( ):
    os.system( os.path.join( settings.BASE_DIR, 'bin/prepare_query.py -o examples/query_folders.txt -p path -r "lpv;dpv" -p files_limit -r 10'))
    os.system( os.path.join( settings.BASE_DIR,"bin/prepare_query.py -o examples/tuning_abbe_filter.txt  -p bins -r 10:150:10 "))
    os.system( os.path.join( settings.BASE_DIR,"""bin/prepare_query.py -o examples/tuning_color_index2.txt -p colors -r '["b_mag - r_mag"]' """))
    os.system( os.path.join( settings.BASE_DIR,"""bin/prepare_query.py -o examples/tuning_color_index.txt -p colors -r '["v_mag-i_mag","b_mag-v_mag"];["v_mag","i_mag"]' """))
    os.system( os.path.join( settings.BASE_DIR,"""bin/prepare_query.py -o examples/tuning_histvario_filter.txt -p hist_days_per_bin -r "97;80" -p vario_days_per_bin -r 9 -p vario_alphabet_size -r 16 -p hist_alphabet_size -r 7 """))
    os.system( os.path.join( settings.BASE_DIR,"""bin/prepare_query.py -o examples/query_ogle.txt -p starid -r 1:10 -p target -r lmc -p field_num -r 1"""))
    
    os.system( os.path.join( settings.BASE_DIR, """bin/make_filter.py  -i examples/tuning_abbe_filter.txt -f AbbeValueFilter -s quasars -c stars -d GaussianNBDec -o examples/AbbeValue_quasar.filter -l examples/AbbeValue_quasar"""))
    # os.system( os.path.join( settings.BASE_DIR, """bin/make_filter.py  -i examples/tuning_color_index2.txt -f ColorIndexFilter -s LOCAL:milliquas:examples/query_localdb.txt -c LOCAL:milliquas:examples/query_localdb2.txt -d GaussianNBDec -o examples/ColorIndex_quasars.filter -l examples/ColorIndex_quasars_filter"""))
    os.system( os.path.join( settings.BASE_DIR, """bin/make_filter.py  -i examples/tuning_histvario_filter.txt -f ComparingFilter -s quasars:20 -c cepheids:5 -c stars:15 -d GaussianNBDec -o examples/HistVario_quasars.filter -l examples/HistVario_quasars"""))
    os.system( os.path.join( settings.BASE_DIR, """bin/make_filter.py  -i examples/tuning_histvario_filter.txt -f ComparingFilter -s QUERY:OgleII:examples/query_ogle.txt -c cepheids:5 -d GaussianNBDec -o examples/HistVario.filter -l examples/HistVario_random"""))
    
    
    os.system( os.path.join( settings.BASE_DIR, """bin/filter_stars.py -d FileManager -i examples/query_folders.txt -f examples/AbbeValue_quasar.filter -o examples"""))
    os.system( os.path.join( settings.BASE_DIR, """bin/filter_stars.py -i examples/query_ogle.txt -o examples/ -d "OgleII" -f examples/HistVario_quasars.filter"""))
    os.system( os.path.join( settings.BASE_DIR, '''bin/filter_stars.py -i examples/query_ogle.txt -o examples/ -d "OgleII"'''))

    
def move_example_data( loc = None ):
    root = settings.ROOT_DIR
    if not loc:
        loc = os.path.join( root, "src", "examples", "examples_data")
        
    copy_tree( os.path.join( loc, "light_curves"), os.path.join( settings.TO_THE_DATA_FOLDER, "light_curves") )
    #copy_tree( os.path.join( loc, "databases"), os.path.join( settings.TO_THE_DATA_FOLDER, "databases") )
    
    
