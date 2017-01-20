#!/usr/bin/env python
# encoding: utf-8
from __future__ import division
import json
from optparse import OptionParser
import os
import random
import sys
import warnings

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from conf import settings
from tools.package_reader import PackageReader
from db_tier.stars_provider import StarsProvider
from entities.exceptions import QueryInputError
from tools.params_estim import ParamsEstimator
from stars_processing.systematic_search.status_resolver import StatusResolver
from utils.helpers import create_folder, progressbar


__all__ = []
__version__ = 0.3
__date__ = '2016-09-23'
__updated__ = '2017-01-07'

debug = True


def main(argv=None):
    '''Command line options.'''

    program_info = """ABOUT
    The program searches for the most optional parameters for given filters
    according to sample of searched and other train light curves.
    
    Getting stars
    -------------
        Stars can be obtained by three different ways resolved from query text
        according to format:
        
            1.QUERY:db_name:query_file_in_inputs_folder
                --> Remote database is queried (db key is name of connector class)
                
                    Example:
                        QUERY:OgleII:query_file.txt
                        
                    Note:
                        There is a overview of available database connectors
                        at the end (if it is launched from command line without
                        parameters)
            
            2.stars_folder_key:number or stars_folder_key%float_number or stars_folder_key
                --> Light curves from folder according to first key is loaded
                    (according to settings.STARS_PATH dictionary). All stars are
                    loaded if there is no number and ':', in case of integer after
                    ':' just this number of stars are loaded and if there are is a float
                    number after '%' this percentage number of all stars are loaded.
                    
                    Example:
                        quasars:10    or    be_stars%0.5    or    cepheids
                        
                    Note:
                        There is a overview of registered light curve locations 
                        at the end (if it is launched from command line without
                        parameters)
    
    Status file:
    ------------
        Parameters to try or queries can be specified in the file where first
        row starts with '#' and then there are names of parameters which can be used
        for finding the most optional parameters of a filter or as query for a database.
        Next rows consist of values to tune or queries. All columns are separated
        by ';' (can be changed in settings).
        
        Note:
            Example files can be find in data/inputs/examples
        
    Getting filter:
    ---------------
        Filter is loaded by name of the filter class in the filter package
        specified in settings.
            
            Note:
                All classes which inherits BaseFilter class located
                in the filters_imp package are considered as filters.
                
    Data folder hierarchy:
    -----------------------
        Next to src/ (source) folder there is a data/ folder where all data files
        are saved. All input/outputs are loaded/saved into a folder in data/.
        
        This behavior can be suppressed by entering word 'HERE:'
        (e.g. 'HERE:path_of_the_file_with_its_name'). It forces to take relative
        path from the directory of executing the script.
        
        There are 5 main folders:
          
            1. data/inputs/
                Location of files of queries and files fro tuning parameters
            
            2. data/light_curves/
                Location of light curve subfolders.
            
            3. data/star_filters/
                Location where tuned filters is saved (or can be loaded by
                filter_lcs script)
            
            4. data/tuning_logs/
                Location of output files from tuning - statistic for every combination
                of parameters, graphs (probability distribution with train objects
                and histograms).
            
            5. data/databases/
                Location of local db files (sqlite).
                
    Deciders:
    --------
        Deciders manage all learning and then recognizing of inspected objects.
        They can be loaded via name of their class. 
    
        Note:
            There is a overview of implemented deciders at the end (if it is
            launched from command line without parameters)
            
            
    Running the program:
    -------------------
        By executing the script all inputs are verified. If everything is ok,
        all combinations of parameters are evaluated and the best is saved
        into data/stars_filters/ folder (if not specified otherwise).
        
        Records about tuning are saved into data/tuning_logs/ - plots of probability
        space and train objects, histograms for particular parameters and
        log file of statistic values about particular combinations.
        
        Note:
            Plot of probability space is created just in case of 2 prameters
            tuning.
            
      
    Examples
    ---------
        Example 1:
            File tuned_params.txt:
                #smooth_ratio
                0.2
                0.3
                0.5
                0.8
                0.9
                
            ./make_filter.py   -i tuned_params.txt
                                -f AbbeValueFilter
                                -s quasars:30
                                -c stars%0.5
                                -c cepheids
                                -o MyAbbeFilter
                                -d NeuronDecider
                
            In the example file above one row represents one combination of parameters (per column).
            Class name is AbbeValueFilter. Desired light curves are quasars (30
            of them are loaded) and they are trained on a "contamination sample"
            of ordinary stars (50 % of available light curves in the folder)
            and cepheids (all light curves in the folder).
            
        Example 2:
            File in/tuned_params_histvario.txt:
                #hist_days_per_bin;vario_days_per_bin;vario_alphabet_size;hist_alphabet_size      
                97;9;17;7
                80;8;16;7
            
            ./make_filter.py   -i tuned_params_histvario.txt
                                -f ComparingFilter
                                -s quasars:9
                                -c cepheids:7
                                -d GaussianNBDec
                                -o MyCompFilter
                                
            
            In the second example above there is a special case of tuning for ComparingFilter.
            In this case whole searched sample is not assigned as train sample, 
            but it's half (in this version, in future there will be more options)
            is taken as comparing sample - these stars will be compared with
            inspected stars.  
            
            Comparative filter is composed from subfilters which is resolved
            from file of tuning parameters. Subfilters which can be constructed
            from given parameters are used.
            
            Note:
                Subfilters specified how stars are compared (e.g. their histograms,
                shape of curves, varigram etc.).
                They are located in 'filters_impl' package (same as ordinary filters)
                and they are distinguished via heritage of 'ComparativeSubFilter'
                class.

                        
        """

    program_name = os.path.basename(sys.argv[0])
    program_version = "v0.2"
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
        parser.add_option("-i", "--input", dest="input",
                          help="Path to the query file")
        parser.add_option("-o", "--file_name", dest="file_name", default="my_filter.pickle",
                          help="Name of result filter file")
        parser.add_option("-f", "--filter", dest="filt",
                          help="Name of filter class name")
        parser.add_option("-s", "--searched", dest="searched", action="append", default=[],
                          help="Designation of searched light curves folder (in settings)")
        parser.add_option("-c", "--contamination", dest="cont", action="append", default=[],
                          help="Designation of contamination light curve folder (in settings)")
        parser.add_option("-d", "--decider", dest="decider", default=None,
                          help="Decider for learning to recognize objects")
        parser.add_option("-l", "--log", dest="log",  default=".",
                          help="Path to the folder where info about tuning and plot will be saved")
        parser.add_option("-p", "--split", dest="split_ratio",  default="3:1",
                          help="Split ratio of given sample of stars for train:test:template (If there are comparing filter there is no need to give template ratio")

        # process options
        opts, args = parser.parse_args(argv)

        if not len(argv):
            print program_info, "\n"
            print "Databases accessible via QUERY:db_key:query_file:\n\t%s\n" % json.dumps(PackageReader().getClassesDict("connectors").keys(), indent=4)
            print "Stars path accessible via STARS_PATH key:\n\t%s\n" % json.dumps(settings.STARS_PATH, indent=4)
            print "Available filters:\n\t%s\n" % json.dumps(PackageReader().getClassesDict("filters").keys(), indent=4)
            print "Available deciders:\n\t%s\n" % json.dumps(PackageReader().getClassesDict("deciders").keys(), indent=4)
            print "Run with '-h' in order to show params help\n"
            return False

        # -------    Core    ------

        try:
            filt = PackageReader().getClassesDict("filters")[opts.filt]
        except KeyError:
            raise Exception("There are no filter %s.\nAvailable filters: %s" % (
                opts.filt, PackageReader().getClassesDict("filters")))

        if opts.input.startswith("HERE:"):
            inp = opts.input[5:]
        else:
            inp = os.path.join(settings.INPUTS_PATH, opts.input)

        try:
            tuned_params = StatusResolver(status_file_path=inp).getQueries()
        except IOError:
            raise Exception(
                "File of parameters combinations was not found:\n%s" % inp)

        if not tuned_params:
            raise Exception("Empty parameters file")
        # TODO: Add check that tuned_paramters are these params needed to
        # construct filter.

        if opts.log.startswith("HERE:"):
            log_path = opts.log[5:]
        else:
            log_path = os.path.join(settings.TUNING_LOGS, opts.log)

        create_folder(log_path)

        all_deciders = PackageReader().getClassesDict("deciders")
        try:
            decider = all_deciders[opts.decider]()
        except KeyError:
            raise Exception(
                "Unknown decider %s\nAvailable deciders: %s" % (opts.decider, all_deciders))

        addit_params = {}
        searched = _getStars(opts.searched)

        try:
            ratios = [int(sp) for sp in opts.split_ratio.split(":")]
        except ValueError:
            raise ValueError(
                "Ratios have to be numbers separated by ':'. Got:\n%s" % opts.split_ratio)

        if opts.filt == "ComparingFilter":
            template_ratio = ratios[-1] / sum(ratios)
            split_n = int(len(searched) * template_ratio)
            addit_params["compar_stars"] = searched[split_n:]
            searched = searched[: split_n]
            addit_params["compar_filters"] = _getSubFilters(tuned_params[0])

        es = ParamsEstimator(searched=searched,
                               others=_getStars(opts.cont),
                               tuned_params=tuned_params,
                               decider=decider,
                               star_filter=filt,
                               log_path=log_path,
                               split_ratio=ratios[0] / sum(ratios[:2]),
                               plot_save_path=log_path,
                               plot_save_name=opts.file_name,
                               save_filter_name=opts.file_name, **addit_params)

        print "Tuning is about to start. There are %i combinations to try" % len(tuned_params)

        es.fit()

        print "It is done.\nLog file and plots have been saved into %s " % opts.log

    except Exception, e:
        if debug:
            raise
        indent = len(program_name) * " "
        sys.stderr.write(program_name + ": " + repr(e) + "\n")
        sys.stderr.write(indent + "  for help use --help")
        return 2


def _getStars(queries):
    """
    Get stars from query text. According to format of the query text different
    methods are called.

        1.LOCAL:db_name:query_file_in_inputs_folder
            --> Local database is queried (according to key in settings.DATABASES)

        2.QUERY:db_name:query_file_in_inputs_folder
            --> Remote database is queried (db key is name of connector class)

        3.stars_folder_key:number or stars_folder_key:float_number or stars_folder_key
            --> Light curves from folder according to first key is loaded
                (according to settings.STARS_PATH dictionary). All stars are
                loaded if there is no number and ':', in case of integer after
                ':' just this number of stars are loaded and if there are float
                number after ':' this percentage number of all stars are loaded.

    """
    LOC_QUERY_KEY = "LOCAL"
    ORDINARY_QUERY_KEY = "QUERY:"

    stars = []
    for query in queries:
        query = query.strip()

        if query.startswith(ORDINARY_QUERY_KEY):
            stars += _getStarsFromRemoteDb(query[len(ORDINARY_QUERY_KEY):])

        else:
            stars += _getStarsFromFolder(query)

    if not stars:
        raise QueryInputError("There no stars. Your query: %s" % query)

    return stars


def _getStarsFromFolder(single_path):
    """
    Get stars from folder/s. If path is iterable (case that more folders were
    given, light curves from that all folder will be loaded

    Parameters
    -----------
        single_path : str
            Name of the folder of lightcurves from "light_curve" directory (specified
            in settings). 

    Returns
    --------
        stars : List of Star objects
            Stars from the folder
    """

    p, restr = _check_sample_name(single_path)
    try:
        st = StarsProvider().getProvider(obtain_method="FileManager",
                                         path=p).getStarsWithCurves()
        stars = _split_stars(st, restr)

    except KeyError:
        raise Exception("\n\nThere no folder with light curves named %s.\nAvailable light curve folders %s" % (
            p, settings.STARS_PATH))

    if not stars:
        raise Exception(
            "There are no stars in path with given restriction %s " % single_path)

    random.shuffle(stars)
    return stars


def _getStarsFromRemoteDb(query):
    """
    This method parsing the query text in order to return desired stars
    from remote database.

    Parameters
    -----------
        query : str
            Query text contains db_key and query file separated by ':'

    Returns
    --------
        List of Star objects

    Example
    -------
        _getStarsFromRemoteDb("OgleII:query_file.txt") --> [Star objects]

        query_file.txt:
            #starid;field;target
            1;1;lmc
            10;1;smc
    """

    try:
        db_key, query_file = query.split(":")
    except:
        QueryInputError(
            "Key for resolving stars source was not recognized:\n%s" % query)

    queries = StatusResolver(
        os.path.join(settings.INPUTS_PATH, query_file)).getQueries()

    stars = []

    for query in progressbar(queries, "Querying stars: "):
        starsProvider = StarsProvider().getProvider(obtain_method=db_key,
                                                    obtain_params=query)

        stars += starsProvider.getStarsWithCurves()

    return stars


def _split_stars(stars, restr):
    random.shuffle(stars)
    num = None
    if type(restr) == float:
        n = len(stars)
        num = int(n * restr)

    elif type(restr) == int:
        num = restr

    return stars[:num]


def _getSubFilters(params):
    sub_filters = []
    for subf in PackageReader().getClasses("sub_filters"):
        try:
            subf(**params)
            sub_filters.append(subf)
        except TypeError as e:
            pass
    if not sub_filters:
        raise Exception(
            "There are no filter which can be constructed from given parameters %s" % params)
    return sub_filters


def _check_sample_name(star_class):

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
            raise Exception(
                "There have to be just one '%' special mark in the star class name.\Got %s" % star_class)

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
            raise Exception(
                "There have to be just one ':' special mark in the star class name.\Got %s" % star_class)

    return star_class, None


if __name__ == "__main__":
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    sys.exit(main())
