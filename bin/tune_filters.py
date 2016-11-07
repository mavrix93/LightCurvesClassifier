#!/usr/bin/env python
# encoding: utf-8

'''
@author:     Martin Vo

@copyright:  All rights reserved.

@contact:    mavrix@seznam.cz
'''

import sys
import os
import random
import warnings
from optparse import OptionParser


sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db_tier.connectors.local_db_client import LocalDbClient
from db_tier.stars_provider import StarsProvider
from conf.package_reader import PackageReader
from conf import settings
from stars_processing.systematic_search.status_resolver import StatusResolver
from stars_processing.filters_tools.params_estim import DeciderEstimation
from entities.exceptions import QueryInputError


__all__ = []
__version__ = 0.3
__date__ = '2016-09-23'
__updated__ = '2016-11-03'

def main(argv = None):
    '''Command line options.'''
    
    program_info = """ABOUT
    The program searches for the most optional parameters for given filters
    according to sample of searched and other train light curves.
    
    Parameters to try are specified in the file where first row starts with '#'
    and then there are names of parameters which will be tuned. Next rows consist
    of values to tune. All columns are separated by ';' (can be change in settings). 
    
    Filter is loaded by name of the filter class in the filter package specified in settings
    (by default data/star_filters).
    Light curves are loaded from light_curves folder (by default data/light_curves)
    by the key from STARS_PATH dictionary specified in settings.
    
    EXAMPLE 1:
        File tuned_params.txt:
            #abbe_lim
            0.2
            0.3
            0.5
            0.8
            0.9
            
        ./tune_filters.py  -i tuned_params.txt -f AbbeValueFilter -s quasars:30 -c stars%0.5 -c cepheids -o MyAbbeFilter
            
        In the example file above one row represents one combination of parameters (per column).
        Class name is AbbeValueFilter. Desired light curves are quasars and they 
        are trained on a "contamination sample" of ordinary stars and cepheids.
        These two names of categories represent key to the path to
        the folder of light curves specified in settings file. 
        
        There can be two special marks after of the light curves group: ':' 
        and '%'. Value after ':' specifies number of light curves to load and
        '%' specifies percentage number of light curves to load. In case 
        of name without any of these special marks all samples will be taken.
            
    EXAMPLE 2:
        File in/tuned_params_histvario.txt:
            #hist_days_per_bin;vario_days_per_bin;vario_alphabet_size;hist_alphabet_size      
            97;9;17;7
            80;8;16;7
        
        ../bin/tune_filters.py  -i in/tuned_params_histvario.txt -f ComparingFilter -s quasars:9 -c cepheids:7 -d GaussianNBDec -o MyCompFilter
        
        In the second example above there is a special case of tuning for ComparingFilter.
        It means that one more parameter needs to be specified - decider ('-d'),
        which estimates probability of membership of inspected object to
        the searched group. Available options will be shown in case of not
        specifying this option. 
        
        Searched sample is split into two samples: First is assigned as comparing
        stars (filter parameter) and second as train sample.
        
        Comparing subfilters are created on base of parameters to tune. All subfilters
        (all classes in filter package which inherit ComparativeSubFilter) which
        would be able to be created from parameters in params file, will be loaded. 
        
        """
    
    program_name = os.path.basename(sys.argv[0])
    program_version = "v0.1"
    program_build_date = "%s" % __updated__

    
    program_version_string = '%%prog %s (%s)' % (program_version, program_build_date)
    program_longdesc = "Run script without paramas to get info about the program."  
    program_license = "Copyright 2016 Martin Vo"


    if argv is None:
        argv = sys.argv[1:]
    try:
        # setup option parser
        parser = OptionParser( version = program_version_string,
                               epilog = program_longdesc,
                               description = program_license)
        parser.add_option( "-i", "--input", dest = "input",
                           help = "Path to the query file" )
        parser.add_option( "-o", "--file_name", dest = "file_name", default = "my_filter.pickle",
                           help = "Name of result filter file" )
        parser.add_option( "-f", "--filter", dest = "filt",
                           help = "Name of the filter file in filters folder (see settings file)")
        parser.add_option( "-s", "--searched", dest = "searched" ,action = "append", default = [],
                           help = "Designation of searched light curves folder (in settings)")
        parser.add_option( "-c", "--contamination", dest = "cont" ,action = "append", default = [],
                           help = "Designation of contamination light curve folder (in settings)") 
        parser.add_option( "-d", "--decider", dest = "decider" , default = None,
                           help = "Decider for learning to recognize objects")
        parser.add_option( "-l", "--log", dest = "log",  default = ".",
                           help = "Path to the folder where info about tuning and plot will be saved")
     
        
        # process options
        opts, args = parser.parse_args(argv)
        
        if not len(argv):
            print program_info, "\n"          
            print "Run with '-h' in order to show params help\n"
            return False
        
        #-------    Core    ------  
       
        try:
            filt = PackageReader().getClassesDict("filters")[opts.filt]
        except KeyError:
            raise Exception("There are no filter %s.\nAvailable filters: %s" % (opts.filt, PackageReader().getClassesDict("filters")))
        
        if opts.input.startswith("HERE:"):
            inp = opts.input[5:] 
        else:
            inp = os.path.join( settings.INPUTS_PATH, opts.input )
           
        try:
            tuned_params = StatusResolver( status_file_path = inp ).getQueries()
        except IOError:
            raise Exception("File of parameters combinations was not found")
        
        if not tuned_params:
            raise Exception("Empty parameters file")
        # TODO: Add check that tuned_paramters are these params needed to construct filter. 
        
        if opts.log.startswith("HERE:"):
            log_path = opts.log[5:]
        else:
            log_path = os.path.join( settings.TUNING_LOGS, opts.log ) 
        
        # TODO: Every filter will be learnable
        # if isinstance( filt,  Learnable ):
        all_deciders = PackageReader().getClassesDict( "deciders" )
        try:
            decider = all_deciders[opts.decider]()
        except KeyError:
            raise Exception("Unknown decider %s\nAvailable deciders: %s" % (opts.decider, all_deciders))
        
            
        addit_params = {}
        searched = _getStars( opts.searched )
        
        if opts.filt == "ComparingFilter":
            # TODO: Cust split
            split_n = len(searched) / 2 
            addit_params["compar_stars"] = searched[split_n: ]
            searched = searched[: split_n ]
            addit_params["compar_filters"] = getSubFilters( tuned_params[0] )
            
        elif opts.filt == "ColorIndexFilter":
            # Nothing needed?
            pass
        
        es = DeciderEstimation(searched = searched,
                               others = _getStars( opts.cont ),
                               tuned_params = tuned_params,
                               decider = decider,
                               star_filter = filt,
                               log_path = log_path,
                               plot_save_path = log_path,
                               plot_save_name = opts.file_name,
                               save_filter_name =  opts.file_name, **addit_params  )
            
    
        print "Tuning is about to start. There are %i combinations to try" % len(tuned_params)
        
        es.fit() 
        
        print "It is done.\nLog file and plots have been saved into %s " % opts.log

    except Exception, e:
        indent = len(program_name) * " "
        sys.stderr.write(program_name + ": " + repr(e) + "\n")
        sys.stderr.write(indent + "  for help use --help")
        return 2

def _getStars( queries ):
    LOC_QUERY_KEY = "QUERY:"
    
    stars = []  
    for query in queries:
        query = query.strip()
        
        if query.startswith( LOC_QUERY_KEY ):
            stars += _getStarsFromLocalDb( query[len(LOC_QUERY_KEY):])       
        else:
            stars += _getStarsFromFolder( query )
    
    if not stars:
        raise QueryInputError("There no stars. Your query: %s" % query)        
    
    return stars

    
def _getStarsFromFolder( single_path ):
    """
    Get stars from folder/s. If path is iterable (case that more folders were
    given, light curves from that all folder will be loaded
    
    Parameters:
    -----------
        single_path : str
            Name of the folder of lightcurves from "light_curve" directory (specified
            in settings). 
            
    Returns:
    --------
        stars : List of Star objects
            Stars from the folder
    """
    
             
    p, restr = check_sample_name( single_path )
    try:
        st = StarsProvider().getProvider( obtain_method = "FileManager",
                                     path = settings.STARS_PATH[p] ).getStarsWithCurves()
        stars = split_stars(st, restr)
                                     
    except KeyError: 
        raise Exception("\n\nThere no folder with light curves named %s.\nAvailable light curve folders %s" % (p,settings.STARS_PATH)  )
    
    if not stars: 
        raise Exception("There are no stars in path with given restriction %s " % single_path)
  
    random.shuffle( stars )
    return stars

def _getStarsFromLocalDb( query ):
    """
    This method parsing the query text in order to return desired stars
    
    Parameters:
    -----------
        query : str
            
            
            
            
               
    Example:
    --------
        _getStarsFromLocalDb("QUERY:milliquas:query_file.txt") --> [Star objects]
        
        query_file.txt:
            #dec;r_mag
            <-50;>20
            
            
    
    """

    try:
        db_key, query_file = query.split(":") 
    except:
        QueryInputError("Key for resolving stars source was not recognized:\n%s" % query)
        
    db_path = settings.DATABASES.get( db_key , None)
    
    if not db_path:
        QueryInputError("Db key was not resolved: %s\nParsed from: %s" % (db_key, query))
        

    queries = StatusResolver( os.path.join( settings.INPUTS_PATH, query_file )).getQueries()
    
    searcher = LocalDbClient( queries, db_key)
    
    return searcher.getStarsWithCurves()
     
def split_stars(stars, restr):       
    random.shuffle( stars )        
    num = None
    if type(restr) == float:  
        n = len(stars)      
        num = int(n * restr)
        
    elif type(restr) == int:  
        num = restr  
        
    return stars[:num]
      

def getSubFilters(params):
        sub_filters = []
        for subf in PackageReader().getClasses( "sub_filters" ):
            try:
                subf(**params)
                sub_filters.append( subf )
            except TypeError as e:
                pass
        if not sub_filters:
            raise Exception("There are no filter which can be constructed from given parameters %s" % params) 
        return sub_filters

def check_sample_name( star_class ):
    
    if "%" in star_class:
        parts = star_class.split("%")
        
        if len(parts) == 2:
            name, ratio = parts
            
            try:
                ratio = float(ratio)
            except ValueError:
                raise Exception("Invalid float number after '%' %s " % ratio)
            
            return name, ratio
        else:
            raise Exception("There have to be just one '%' special mark in the star class name.\Got %s" % star_class)
    
    elif ":" in star_class:
        parts = star_class.split(":")
        
        if len(parts) == 2:
            name, num = parts
            
            try:
                num = int(num)
            except ValueError:
                raise Exception("Invalid integer after '%' %s " % num)
            
            return name, num
        else:
            raise Exception("There have to be just one ':' special mark in the star class name.\Got %s" % star_class)
    
    return star_class, None
        

if __name__ == "__main__":        
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    sys.exit(main())