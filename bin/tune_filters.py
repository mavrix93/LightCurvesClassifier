#!/usr/bin/env python
# encoding: utf-8

'''
@author:     Martin Vo

@copyright:  All rights reserved.

@contact:    mavrix@seznam.cz
'''

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db_tier.stars_provider import StarsProvider
from conf.package_reader import PackageReader
from conf import settings
from stars_processing.systematic_search.status_resolver import StatusResolver
from conf.params_estim import ParamsEstimation

from optparse import OptionParser


__all__ = []
__version__ = 0.1
__date__ = '2016-09-23'
__updated__ = '2016-09-23'

def main(argv = None):
    '''Command line options.'''
    
    program_info = """ABOUT
    The program is searching for the most optional parameters for given filters
    according to sample of searched and other light curves.
    
    Parameters to try are specified in the file where first row starts with '#'
    and then there are names of parameters which will be tuned. Next rows consist
    of values to tune. All columns are separated by tabulator. 
    
    Filter is loaded by name the filter class in the package specified in settings.
    Light curves are loaded from light_curves folder by key from STARS_PATH dictionary
    in settings.
    
    EXAMPLE:
        File tuned_params.txt:
            #abbe_lim
            0.2
            0.3
            0.5
            0.8
            0.9
            
        In the example file above is used as "all combinations" file and filter
        class name is AbbeValueFilter. Desired light curves are lcs of quasars
        and we are training on "contamination sample" of ordinary stars and cepheids. 
            
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
        
        # set defaults
        parser.set_defaults( file_name = "my_filter.pickle")
        
        # process options
        opts, args = parser.parse_args(argv)
        
        if not len(argv):
            print program_info, "\n"          
            print "Run with '-h' in order to show params help\n"
            return False
        
        #-------    Core    ------  
       
        tuned_params = StatusResolver( status_file_path = opts.input ).getQueries()
        
        print "Tuning is about to start. Tuned parameters:", tuned_params
        es = ParamsEstimation( searched = _getStars( opts.searched ), 
                               others = _getStars( opts.cont ),
                               filt = PackageReader().getClassesDict("filters")[opts.filt],
                               tuned_params = tuned_params,
                               save_file = os.path.join( settings.FILTERS_PATH, opts.file_name ))
        es.fit() 

    except Exception, e:
        raise
        indent = len(program_name) * " "
        sys.stderr.write(program_name + ": " + repr(e) + "\n")
        sys.stderr.write(indent + "  for help use --help")
        return 2
    
def _getStars( path ):
    if hasattr( path, "__iter__"):
        stars = []
        for p in path:
            stars += StarsProvider().getProvider( obtain_method = "FileManager",
                                         path = settings.STARS_PATH[p] ).getStarsWithCurves()
    else:
        stars = StarsProvider().getProvider( obtain_method = "FileManager",
                                         path = settings.STARS_PATH[path] ).getStarsWithCurves()   
    return stars


if __name__ == "__main__":    
    sys.exit(main())