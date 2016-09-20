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

from conf.filter_loader import FilterLoader
from stars_processing.systematic_search.status_resolver import StatusResolver
from stars_processing.systematic_search.stars_searcher import StarsSearcher
from db_tier.stars_provider import StarsProvider

from optparse import OptionParser


__all__ = []
__version__ = 0.1
__date__ = '2016-09-05'
__updated__ = '2016-09-05'




def main(argv=None):
    '''Command line options.'''
    
    program_info = """ABOUT
    This program downloads light curves from astronomical databases.
    The database is specified via database identifier. Query is done
    thru query file where first row starts with "#" will be considered
    as db keys for values in certain columns.

EXAMPLE:
    For Ogle query file named query.txt:
        #starid field_num       target
        1       1       lmc
        12      1       lmc
    
    
    ./download_lcs.py -i query.txt -o out/ -d "ogle"

    The light curves and status file will be saved into "out" folder."""
    
    program_name = os.path.basename(sys.argv[0])
    program_version = "v0.1"
    program_build_date = "%s" % __updated__

    
    program_version_string = '%%prog %s (%s)' % (program_version, program_build_date)
    program_longdesc = "Run script without paramas to get info about the program and list of available databases"  
    program_license = "Copyright 2016 Martin Vo"


    if argv is None:
        argv = sys.argv[1:]
    try:
        # setup option parser
        parser = OptionParser(version=program_version_string, epilog=program_longdesc, description=program_license)
        parser.add_option( "-o","--output", dest = "output",
                           help="Path to the directory for output files", type=str )
        parser.add_option( "-i", "--input", dest = "input",
                           help="Path to the query file" )
        parser.add_option( "-d", "--database", dest = "db",
                           help="Searched database" )
        parser.add_option( "-f", "--filters", dest = "filt", action="append", default = [])
        
        # set defaults
        parser.set_defaults(path=".")
        
        # process options
        opts, args = parser.parse_args(argv)
        
        if not len(argv):
            print program_info, "\n"
            print available_databases()            
            print "Run with '-h' in order to show params help\n"
            return False
        
        if opts.db not in StarsProvider.STARS_PROVIDERS:
            print "Error: " + "Unresolved database %s \n" % opts.db
            print available_databases()            
            return False
        
        #-------    Core    ------
        
        UNFOUND_LIM = 2
        
     
        resolver = StatusResolver( status_file_path = opts.input )
        queries = resolver.getQueries()
        
        star_filters = _load_filters( opts.filt )
        
        print sum_txt( opts.db, opts.input,len( resolver.status_queries ), [filt.__class__.__name__ for filt in star_filters] , opts.output )
        
        searcher = StarsSearcher( star_filters, SAVE_PATH=opts.output, SAVE_LIM=1, OBTH_METHOD=opts.db, UNFOUND_LIM=UNFOUND_LIM)
        searcher.queryStars(queries)
        
        print "Download is done. Results and status file were saved into %s folder"% opts.output

    except Exception, e:
        indent = len(program_name) * " "
        sys.stderr.write(program_name + ": " + repr(e) + "\n")
        sys.stderr.write(indent + "  for help use --help")
        return 2

def available_databases():
    '''Find all available databases'''
    
    providers = StarsProvider.STARS_PROVIDERS
    
    txt =  "Available databases:\n"
    txt += "%s\t|\t%s\n" % ("Db key", "Name")
    txt += "---------------------------\n"
    for key, value in providers.iteritems():
        txt += "%s\t|\t%s\n" % (key,value.__name__)
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
        filt_input = [filt_input]
           
    star_filters = []    
    for filter_path in filt_input:
        star_filters.append( FilterLoader( filter_path ).getFilter() )
      
    return star_filters   


if __name__ == "__main__":    
    sys.exit(main())