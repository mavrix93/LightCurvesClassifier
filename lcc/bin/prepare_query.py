#!/usr/bin/env python
# encoding: utf-8
from optparse import OptionParser
import os
import sys

from lcc.entities.exceptions import QueryInputError
import numpy as np
from lcc.data_manager.status_resolver import StatusResolver
from lcc.utils.helpers import get_combinations


sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


__all__ = []

__version__ = 0.1
__date__ = '2016-11-07'
__updated__ = '2017-02-02'


def main(project_settings, argv=None):
    """Command line options."""

    program_info = """ABOUT
    
    The program creates query files or files of parameters to tune. Name of output
    file is specified by '-o' option. This file will be created in data/inputs/.
    
    Name of parameters are specified by '-p' and their ranges via '-r'. Format
    of ranges is: from_number:to_number:step_number (i.e. 1:10:2 means from
    1 to 10 with step size 2 --> 1,3,5..). It is not necessary to specify step,
    in that  case step will be taken as 1.
        
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

    program_version_string = '%%prog %s (%s)' % (
        program_version, program_build_date)
    program_longdesc = "Run script without paramas to get info about the program."
    program_license = "Copyright 2016 Martin Vo"

    # Separator for range keys input text
    RANGES_SEPARATOR = ":"

    ENUM_SYMBOL = ","

    if argv is None:
        argv = sys.argv[1:]
    try:
        # setup option parser
        parser = OptionParser(version=program_version_string,
                              epilog=program_longdesc,
                              description=program_license)
        parser.add_option("-o", "--output", dest="output", default="my_query.txt",
                          help="Name of the query file which will be created in data/inputs")
        parser.add_option("-p", "--param", dest="param", action="append", default=[],
                          help="Parameter name which will be generated")
        parser.add_option("-r", "--range", dest="range", action="append", default=[],
                          help="Range of parameters separated by ':' - from_num:to_num:step_num.")
        parser.add_option("-d", "--delim", dest="delim", default=";",
                          help="Delimiter for the output file")
        parser.add_option("-f", "--folder", dest="folder", default=".",
                          help="Path where the query file will be saved")

        # process options
        opts, args = parser.parse_args(argv)

        if not len(argv):
            print program_info, "\n"
            print "Run with '-h' in order to show params help\n"
            return False

        ranges = opts.range
        params = opts.param

        if not len(params) == len(ranges):
            raise QueryInputError(
                "Number of parameters and ranges have to be the same")

        x = []
        for i in range(len(params)):
            just_one = False
            enum = _enumeration(ranges[i], ENUM_SYMBOL)
            if not enum:
                parts = ranges[i].split(RANGES_SEPARATOR)

                n = len(parts)

                if n == 1:
                    just_one = True

                elif n == 2:
                    step = 1

                elif n > 3:
                    raise Exception(
                        "There cannot be more then three separators %s" % RANGES_SEPARATOR)

                else:
                    step = parts[2]

                if not just_one:
                    from_n = parts[0]
                    to_n = parts[1]
                    try:
                        x.append(range(int(from_n), int(to_n), int(step)))
                    except:
                        x.append(
                            np.arange(float(from_n), float(to_n), float(step)))
                else:
                    x.append(parts)

            else:
                x.append(enum)

        query = get_combinations(params, *x)

        if opts.folder == "t":
            path = project_settings.TUN_PARAMS
        elif opts.folder == "q":
            path = project_settings.QUERIES
        else:
            path = opts.folder
        file_name = opts.output

        StatusResolver.save_query(query, file_name, path, opts.delim)

        print "\nDone.\nFile %s was saved into %s" % (file_name, path)

    except Exception, e:
        indent = len(program_name) * " "
        sys.stderr.write(program_name + ": " + repr(e) + "\n")
        sys.stderr.write(indent + "  for help use --help")
        return 2


def _enumeration(param, ENUM_SYMBOL=","):
    if ENUM_SYMBOL in param:
        return [en.strip() for en in param.split(ENUM_SYMBOL)]

    else:
        return False


if __name__ == "__main__":
    sys.exit(main())
