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

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import inspect
from db_tier.stars_provider import StarsProvider
from conf.package_reader import PackageReader
from conf import settings
from stars_processing.systematic_search.status_resolver import StatusResolver
from stars_processing.filters_tools.params_estim import ParamsEstimation,\
    ComparativeEstimation

from optparse import OptionParser


__all__ = []
__version__ = 0.1
__date__ = '2016-09-23'
__updated__ = '2016-09-25'

def main(argv = None):
    '''Command line options.'''
    
    program_info = """ABOUT
    The program searches for the most optional parameters for given filters
    according to sample of searched and other light curves.
    
    Parameters to try are specified in the file where first row starts with '#'
    and then there are names of parameters which will be tuned. Next rows consist
    of values to tune. All columns are separated by tabulator. 
    
    Filter is loaded by name the filter class in the package specified in settings.
    Light curves are loaded from $light_curves folder by key from STARS_PATH dictionary
    in settings.
    
    In case that file with parameters to try is not found, the user is prompted
    whether wants prepare new file with header according to given filter (all 
    constructor parameters of the filter as names of columns).
    
    EXAMPLE:
        File tuned_params.txt:
            #abbe_lim
            0.2
            0.3
            0.5
            0.8
            0.9
            
        In the example file above one row represents one combination of parameters (per column)
        There is command to execute. Class name is AbbeValueFilter. Desired light
        curves are lcs of quasars and we are training on "contamination sample"
        of ordinary stars and cepheids. These two names of categories represent
        key to the path to the folder of light curves specified in settings file. 
            
        ./tune_filters.py  -i tuned_params.txt -f AbbeValueFilter -s quasars -c stars -c cepheids
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
        parser.add_option( "-o", "--file_name", dest = "file_name",
                           help = "Name of result filter file" )
        parser.add_option( "-f", "--filter", dest = "filt",
                           help = "Name of the filter file in filters folder (see settings file)")
        parser.add_option( "-s", "--searched", dest = "searched" ,action = "append", default = [],
                           help = "Designation of searched light curves folder (in settings)")
        parser.add_option( "-c", "--contamination", dest = "cont" ,action = "append", default = [],
                           help = "Designation of contamination light curve folder (in settings)") 
        parser.add_option( "-d", "--decider", dest = "decider" , default = None,
                           help = "Decider for learning to recognize objects")
        parser.add_option( "-l", "--lightcurves", dest = "comp" ,action = "append", default = [],
                           help = "Light curves which are compared to other stars (in case of comparative filtering)")
        parser.add_option( "-r", "--ratio", dest = "fraction" , default = 1,
                           help = "Specify the fraction of available stars")
        
        # set defaults
        parser.set_defaults( file_name = "my_filter.pickle")
        
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
            
        file_name = os.path.join( settings.FILTERS_PATH, opts.file_name )
           
        try:
            tuned_params = StatusResolver( status_file_path = opts.input ).getQueries()
        except IOError:
            print "File of parameters combinations of filter was not found"
            prepare_new = raw_input( "Do you want to prepare new file? (y/n)\t")
            
            if prepare_new == "y":
                prepareFile(opts.input, filt)
                return 1
            raise
        
        if not tuned_params:
            raise Exception("Empty parameters file")
        # TODO: Add check that tuned_paramters are these params needed to construct filter. 
        
        if opts.filt == "ComparingFilter":
            all_deciders = PackageReader().getClassesDict( "deciders" )
            try:
                decider = all_deciders[opts.decider]
            except KeyError:
                raise Exception("Unknown decider %s\nAvailable deciders: %s" % (opts.decider, all_deciders))
            

            es = ComparativeEstimation(searched = _getStars( opts.searched, float(opts.fraction) ),
                                       others = _getStars( opts.cont, float(opts.fraction) ),
                                       compar_filters = getSubFilters( tuned_params[0] ),
                                       tuned_params = tuned_params,
                                       decider = decider,
                                       comp = _getStars( opts.comp, float(opts.fraction) ))
            
        else:
            es = ParamsEstimation( searched = _getStars( opts.searched, float(opts.fraction) ), 
                                   others = _getStars( opts.cont, float(opts.fraction) ),
                                   filt = filt,
                                   tuned_params = tuned_params,
                                   save_file = file_name)
                
        print "Tuning is about to start. Tuned parameters:", tuned_params
        
        es.fit() 

    except Exception, e:
        raise
        indent = len(program_name) * " "
        sys.stderr.write(program_name + ": " + repr(e) + "\n")
        sys.stderr.write(indent + "  for help use --help")
        return 2
    
def _getStars( path, fraction = 1 ):
    """
    Get stars from folder/s. If path is iterable (case that more folders were
    given, light curves from that all folder will be loaded
    
    Parameters:
    -----------
        path : iterable, str
            Name of the folder of lightcurves from "light_curve" directory (specified
            in settings). Can be also list/tuple.. of these names
            
    Returns:
    --------
        stars : List of Star objects
            Stars from the folder/s
    """
    
    if hasattr( path, "__iter__"):
        stars = []
        for p in path:
            try:
                stars += StarsProvider().getProvider( obtain_method = "FileManager",
                                             path = settings.STARS_PATH[p] ).getStarsWithCurves()
            except KeyError:
                raise Exception("\n\nThere no folder with light curves named %s.\nAvailable light curve folders %s" % (p,settings.STARS_PATH)  )
    else:
        try:
            stars = StarsProvider().getProvider( obtain_method = "FileManager",
                                             path = settings.STARS_PATH[path] ).getStarsWithCurves()   
        except KeyError:
            raise Exception("\n\nThere no folder with light curves named %s.\nAvailable light curve folders %s" % (path,settings.STARS_PATH)  )
    
    if fraction != 1:    
        random.shuffle( stars )
        n = len(stars)
        num = int(n * fraction)
        return stars[:num]
            
    return stars

def getSubFilters(params):
        sub_filters = []
        for subf in PackageReader().getClasses( "sub_filters" ):
            try:
                subf(**params)
                sub_filters.append( subf )
            except TypeError as e:
                print e, subf, params
                pass
        if not sub_filters:
            raise Exception("There are no comparative subfilter which can be constructed from given parameters %s" % params) 
        return sub_filters

# TODO: Check the output of the method
def prepareFile( file_name, filt ):
    """
    In case that file with parameters to try is not found, the user is prompted
    whether wants prepare new file with header according to given filter (all 
    constructor parameters of the filter as names of columns).
    
    Parameters:
    -----------
        file_name : str
            Name (with path from launcher) of the file into which the output is saved
        
        filt : BaseFilter child object
            Unconstructed star filter object
            
    Returns:
    --------
        None
            Output is saved object
            
    """
    with open( file_name, "w" ) as fi:
        args = inspect.getargspec( filt.__init__ ).args[1:]
        
        fi.write("#")
        for arg in args:
            fi.write( "%s\t" % arg )
    print "File was prepared at %s " % file_name

if __name__ == "__main__":    
    sys.exit(main())