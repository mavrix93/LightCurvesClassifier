#!/usr/bin/env python
# encoding: utf-8

'''
@author:     Martin Vo

@copyright:  All rights reserved.

@contact:    mavrix@seznam.cz
'''

import sys
import os
from optparse import OptionParser

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from entities.exceptions import QueryInputError
from conf import settings
from stars_processing.systematic_search.status_resolver import StatusResolver
from utils.helpers import get_combinations


__all__ = []

__version__ = 0.1
__date__ = '2016-11-07'
__updated__ = '2016-11-07'

def main(argv = None):
    '''Command line options.'''
    
    program_info = """ABOUT
    
        
        Example:
        
        ./prepare_query.py -o TestQuery.txt -p starid -r 5:12:3 -p field -r 1:3 -p target -r lmc,smc
        
        --> generates
        
        #starid;target;field
        5;lmc;1
        5;smc;1
        5;lmc;2
        5;smc;2
        8;lmc;1
        8;smc;1
        8;lmc;2
        8;smc;2
        11;lmc;1
        11;smc;1
        11;lmc;2
        11;smc;2

        
        """
    
    program_name = os.path.basename(sys.argv[0])
    program_version = "v0.1"
    program_build_date = "%s" % __updated__

    
    program_version_string = '%%prog %s (%s)' % (program_version, program_build_date)
    program_longdesc = "Run script without paramas to get info about the program."  
    program_license = "Copyright 2016 Martin Vo"

    RANGES_SEPARATOR = ":"
    ENUM_SYMBOL = ","
    
    if argv is None:
        argv = sys.argv[1:]
    try:
        # setup option parser
        parser = OptionParser( version = program_version_string,
                               epilog = program_longdesc,
                               description = program_license)
        parser.add_option( "-o", "--output", dest = "output", default = "my_query.txt",
                           help = "Name of the query file which will be created in data/inputs")     
        parser.add_option( "-p", "--param", dest = "param" ,action = "append", default = [],
                           help = "Parameter name which will be generated")
        parser.add_option( "-r", "--range", dest = "range" ,action = "append", default = [],
                           help = "Range of parameters separated by ':' - from_num:to_num:step_num.")        
        parser.add_option( "-d", "--delim", dest = "delim", default = ";",
                           help = "Delimiter for the output file")
     
        
        # process options
        opts, args = parser.parse_args(argv)
        
        if not len(argv):
            print program_info, "\n"          
            print "Run with '-h' in order to show params help\n"
            return False
        
        ranges = opts.range
        params =  opts.param
        
        if not len( params ) == len( ranges ):
            raise QueryInputError("Number of parameters and ranges have to be the same")
        
        x = []
        for i in range( len(params) ):
            enum =  _enumeration( ranges[i], ENUM_SYMBOL)
            if not enum:
                parts = ranges[i].split( RANGES_SEPARATOR )
                
                n = len(parts)
                
                if n == 1:
                    raise Exception("Invalid range key. There needs to be ranges separated by '%s'. " % RANGES_SEPARATOR)
                
                elif n == 2:
                    step = 1
                
                elif n > 3:
                    raise Exception("There cannot be more then three separators %s" % RANGES_SEPARATOR)
                
                else:
                    step = parts[2]
                
                from_n = parts[0]
                to_n = parts[1]        
            
                x.append( range( int(from_n), int(to_n), int(step)))
                
            else:
                x.append( enum )
            
            
        
        query = get_combinations( params, *x)
        
        if opts.output.startswith("HERE:"):
            file_name = opts.output[5:]
            path = "."
        else:
            file_name = opts.output
            path = settings.INPUTS_PATH
        
        StatusResolver.save_query(query, file_name, path, opts.delim)
        
        print "Done. File %s was saved into %s" % (file_name, path) 
        
    
    
    except Exception, e:
        indent = len(program_name) * " "
        sys.stderr.write(program_name + ": " + repr(e) + "\n")
        sys.stderr.write(indent + "  for help use --help")
        return 2    
        

def _enumeration( param, ENUM_SYMBOL = "," ):    
    if ENUM_SYMBOL in param:
        return [ en.strip() for en in param.split( ENUM_SYMBOL )]
        
    else:
        return False
        
        
if __name__ == "__main__":        
    sys.exit(main())