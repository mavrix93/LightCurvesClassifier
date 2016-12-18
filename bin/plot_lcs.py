#!/usr/bin/env python
# encoding: utf-8
from optparse import OptionParser
import os
import sys
import warnings

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db_tier.stars_provider import StarsProvider
from entities.exceptions import InvalidFilesPath
from utils.helpers import create_folder
from utils.stars import plotStarsPicture


__all__ = []

__version__ = 0.1
__date__ = '2016-12-06'
__updated__ = '2016-12-17'


def main(argv=None):
    '''Command line options.'''

    program_info = """ABOUT
    
    The script creates images of light curves in specified folder. Output images 
    are stored by default in the folder of light curve files into "images", but
    path to another directory can be specified.
    
    Note:
    -----
        All paths are relative to location of execution.    
    
    Example:
    --------
        ./src/bin/plot_lcs.py -p data/light_curves/some_stars -o my_images/nonvar_stars
    """

    program_name = os.path.basename(sys.argv[0])
    program_version = "v0.1"
    program_build_date = "%s" % __updated__

    program_version_string = '%%prog %s (%s)' % (
        program_version, program_build_date)
    program_longdesc = "Run script without paramas to get info about the program."
    program_license = "Copyright 2016 Martin Vo"

    if argv is None:
        argv = sys.argv[1:]
    try:
        # setup option parser
        parser = OptionParser(version=program_version_string,
                              epilog=program_longdesc,
                              description=program_license)
        parser.add_option("-o", "--output", dest="output", default=None,
                          help="Relative path to the folder where images will be saved")
        parser.add_option("-p", "--path", dest="Relative path to the folder of light curves",
                          help="")

        # process options
        opts, args = parser.parse_args(argv)

        if not len(argv):
            print program_info, "\n"
            print "Run with '-h' in order to show params help\n"
            return False

        if opts.path:
            path = opts.path
        else:
            raise InvalidFilesPath("There is no path %s" % opts.path)

        if opts.output:
            save_path = opts.output
        else:
            save_path = os.path.join(path, "images")

        stars = StarsProvider().getProvider(obtain_method="FileManager",
                                            obtain_params={"path": "HERE:%s" % path}).getStarsWithCurves()

        print "\n\nThere are %i stars in the folder which will be plotted into %s.\nThis will take a while..." % (len(stars), save_path)
        create_folder(save_path)
        plotStarsPicture(stars, option="save", save_loc=save_path)

        print "\n%s\nImages of light curves in %s were saved into %s" % ("=" * 20, path, save_path)

    except Exception, e:
        indent = len(program_name) * " "
        sys.stderr.write(program_name + ": " + repr(e) + "\n")
        sys.stderr.write(indent + "  for help use --help")
        return 2


if __name__ == "__main__":
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    warnings.filterwarnings("ignore", category=UserWarning)
    sys.exit(main())
