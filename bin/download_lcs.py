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

from conf import settings
from conf.filter_loader import FilterLoader
from stars_processing.systematic_search.status_resolver import StatusResolver
from stars_processing.systematic_search.stars_searcher import StarsSearcher
from db_tier.stars_provider import StarsProvider

from optparse import OptionParser


__all__ = []
__version__ = 0.1
__date__ = '2016-09-05'
__updated__ = '2016-09-23'




def main(argv = None):
    '''Command line options.'''
    
    program_info = """ABOUT
    The program downloads light curves from astronomical databases
    which pass thru given filters.
    The database is specified via database identifier. Query is done
    thru query file where first row starts with "#" will be considered
    as db keys for values in certain columns.


WITHOUT FILTERING
    EXAMPLE:
        For Ogle query file (columns separated by tab) named query.txt:
            #starid field_num       target
            1       1       lmc
            12      1       lmc
        
        
        ./download_lcs.py -i query.txt -o out/ -d "OgleII"
    
        The light curves and status file will be saved into "out" folder.
        
    WITH FILTERING
        Filters can be specified by filter file name in filters folder (see settings).
        There are two types of filter files:
    
        1. Config file
            Regular text file with key and value separated by delimiter
            specified in settings (by default '=').
            Keys have to be name of parameters needed to construct the filter
            object and moreover there need to be specified key 'name'
            which value if name of the filter class in the package of filters
            implementation (see settings).
            
        2. Object file
            Serialized (by pickle) file of dictionary with two keys:
                "filter": Filter class (unconstructed filter object)
                "params": Parameters as dictionary (similar as config file)
            It is not intended to create this file manually, but automatically
            by parameters estimators (which find the best parameters).
            However it is possible to create the file manually.
            
    The file type is resolved by suffix of the file. The object extension
    is specified in settings (by default "pickle"). In other cases the file
    is considered as config file. 
    
    It is possible to insert more then one filter by adding another values
    after '-f' as is shown in example below.
    
    EXAMPLE:
        A command for executing searching light curves in OGLE database
        with filtering:
        
        ./download_lcs.py -i query.txt -o out/ -d "OgleII" -f abbe_filter.conf -f vario_slope.pickel
        """
    
    program_name = os.path.basename(sys.argv[0])
    program_version = "v0.2"
    program_build_date = "%s" % __updated__

    
    program_version_string = '%%prog %s (%s)' % (program_version, program_build_date)
    program_longdesc = "Run script without params to get info about the program and list of available databases"  
    program_license = "Copyright 2016 Martin Vo"


    if argv is None:
        argv = sys.argv[1:]
    try:
        # setup option parser
        parser = OptionParser( version = program_version_string,
                               epilog = program_longdesc,
                               description = program_license)
        parser.add_option( "-o", "--output", dest = "output",
                           help = "Path to the directory for output files from data/light_curves", type = str )
        parser.add_option( "-i", "--input", dest = "input",
                           help = "Path to the query file" )
        parser.add_option( "-d", "--database", dest = "db",
                           help = "Searched database" )
        parser.add_option( "-f", "--filters", dest = "filt", action = "append", default = [],
                           help = "Name of the filter file in filters folder (see settings file)")

        
        # set defaults
        parser.set_defaults( output = "." )
        
        # process options
        opts, args = parser.parse_args(argv)
        
        if not len(argv):
            print program_info, "\n"
            print available_databases()            
            print "Run with '-h' in order to show params help\n"
            return False
        
        if opts.db not in StarsProvider().STARS_PROVIDERS:
            print "Error: " + "Unresolved database %s \n" % opts.db
            print available_databases()            
            return False
        
        #-------    Core    ------
        
        UNFOUND_LIM = 2        
     
        resolver = StatusResolver( status_file_path = opts.input )
        queries = resolver.getQueries()
        
        star_filters = _load_filters( opts.filt )
        
        print sum_txt( opts.db, opts.input,len( resolver.status_queries ), [filt.__class__.__name__ for filt in star_filters] , opts.output )
        
        searcher = StarsSearcher( star_filters,
                                  SAVE_PATH = opts.output,
                                  SAVE_LIM = 1,
                                  OBTH_METHOD = opts.db,
                                  UNFOUND_LIM = UNFOUND_LIM)
        searcher.queryStars( queries )
        
        print "Download is done. Results and status file were saved into %s folder in %s"% (opts.output, settings.LC_FOLDER)

    except Exception, e:
        indent = len(program_name) * " "
        sys.stderr.write(program_name + ": " + repr(e) + "\n")
        sys.stderr.write(indent + "  for help use --help")
        return 2

def available_databases():
    '''Find all available databases'''
    
    providers = StarsProvider().STARS_PROVIDERS
    
    txt =  "Available databases:\n\n"
    for key, value in providers.iteritems():
        txt += "%s\n" % (key)
    return  txt

def sum_txt(db, input, num_queries, star_filters, out):
    '''Get info text before querying'''
    
    sumup_txt = '''
    \n\nDownloading from %s database is about to start..
The query file from %s was loaded properly and there were found %i queries.
Filters which will be applied: %s
The result light curves will be saved into %s
    \n\n''' % (db, input, num_queries, ", ".join(star_filters), out)
    return sumup_txt

def _load_filters( filt_input ):
    SET_TYPES = ( list, tuple )
    
    # In case of single filter
    if not type(filt_input) in SET_TYPES:
        filt_input = [ filt_input ]
           
    star_filters = []    
    for filter_path in filt_input:        
        if filter_path.split( "." )[-1] == settings.OBJECT_SUFFIX:
            object_file = True
        else:
            object_file = False
            
        star_filters.append( FilterLoader( filter_path , object_file ).getFilter() )
      
    return star_filters






if __name__ == "__main__":    
    sys.exit(main())