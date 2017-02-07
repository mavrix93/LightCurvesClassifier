#!/usr/bin/env python
# encoding: utf-8
from __future__ import division

import json
from optparse import OptionParser
import os
import sys
import warnings

from lcc.api.input_parse import parse_tun_query
from lcc.api.stars_handling import getStars
from lcc.data_manager.filter_serializer import FiltersSerializer
from lcc.data_manager.package_reader import PackageReader
from lcc.data_manager.prepare_package import rec
from lcc.data_manager.prepare_package import tree
from lcc.data_manager.status_resolver import StatusResolver
from lcc.entities.exceptions import QueryInputError
from lcc.stars_processing.tools.params_estim import ParamsEstimator
from lcc.stars_processing.tools.visualization import plotProbabSpace
from lcc.stars_processing.utilities.compare import ComparativeBase
import numpy as np
from lcc.stars_processing.tools.visualization import plotHist

__all__ = []
__version__ = 0.3
__date__ = '2016-09-23'
__updated__ = '2017-02-07'

debug = True


def main(project_settings, argv=None):
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

    DEF_FILT_NAME = "Unnamed"

    if argv is None:
        argv = sys.argv[1:]
    try:
        # setup option parser
        parser = OptionParser(version=program_version_string,
                              epilog=program_longdesc,
                              description=program_license)

        parser.add_option("-i", "--input", dest="input",
                          help="Name of the file of tuning combinations (present in $PROJEC_DIR/inputs/tun_params)")

        parser.add_option("-n", "--name", dest="filt_name",
                          help="Name of the filter")

        parser.add_option("-f", "--descriptor", dest="descriptors",
                          action="append", default=[],
                          help="Descriptors (this key can be used multiple times)")

        parser.add_option("-s", "--searched", dest="searched", action="append",
                          default=[],
                          help="Searched stars folder (present in $PROJEC_DIR/inp_lcs)")

        parser.add_option("-c", "--contamination", dest="cont", action="append", default=[],
                          help="Contamination stars folder (present in $PROJEC_DIR/inputs/lcs)")

        parser.add_option("-t", "--template", dest="template", action="append", default=[],
                          help="Template stars folder (present in $PROJEC_DIR/inputs/lcs) if comparative filters are used")

        parser.add_option("-d", "--decider", dest="deciders", default=[],
                          help="Decider for learning to recognize objects")

        parser.add_option("-p", "--split", dest="split_ratio", default="3:1",
                          help="Split ratio for train-test sample")

        # process options
        opts, args = parser.parse_args(argv)

        if not len(argv):
            print program_info, "\n"
            print "Available databases:\n\t%s\n" % json.dumps(PackageReader().getClassesDict("connectors").keys(), indent=4)
            print "Available descriptors:\n\t%s\n" % json.dumps(PackageReader().getClassesDict("descriptors").keys(), indent=4)
            print "Available deciders:\n\t%s\n" % json.dumps(PackageReader().getClassesDict("deciders").keys(), indent=4)
            print "Run with '-h' in order to show params help\n"
            return False

        # -------    Core    ------
        try:
            descriptors = [desc for desc in PackageReader().getClasses(
                "descriptors") if desc.__name__ in opts.descriptors]

        except KeyError:
            raise Exception("There are no descriptor %s.\nAvailable filters: %s" % (
                opts.filt, PackageReader().getClassesDict("descriptors")))
        if len(opts.descriptors) != len(descriptors):
            raise QueryInputError("No all descriptors have been found. Got: %s\nFound: %s" % (
                opts.descriptors, descriptors))

        header = "#" + " " * 40 + \
            "Light Curves Classifier - Make Filter" + " " * 30 + "#"
        print "\n\n\t" + "#" * len(header)
        print "\t#" + " " * (len(header) - 2) + "#"
        print "\t" + header
        print "\t#" + " " * (len(header) - 2) + "#"
        print "\t" + "#" * len(header) + "\nSelected descriptors: " + ", ".join([d.__name__ for d in descriptors])
        inp = os.path.join(project_settings.TUN_PARAMS, opts.input)

        try:
            _tuned_params = StatusResolver(status_file_path=inp).getQueries()
            tuned_params = parse_tun_query(_tuned_params)
        except IOError:
            raise Exception(
                "File of parameters combinations was not found:\n%s" % inp)

        if not tuned_params:
            raise QueryInputError("Empty parameters file")

        # TODO: Add check that tuned_paramters are these params needed to
        # construct filter.
        try:
            deciders = [desc for desc in PackageReader().getClasses(
                "deciders") if desc.__name__ in opts.deciders]
        except KeyError:
            raise Exception(
                "Unknown decider %s\nAvailable deciders: %s" % (opts.deciders, PackageReader().getClasses(
                    "deciders")))

        print "Selected deciders: " + ", ".join([d.__name__ for d in deciders])
        print "\nLoading stars..."
        searched = getStars(opts.searched, project_settings.INP_LCS,
                            query_path=project_settings.QUERIES, progb_txt="Querying searched stars: ")
        others = getStars(opts.cont, project_settings.INP_LCS,
                          query_path=project_settings.QUERIES, progb_txt="Querying contamination stars: ")
        print "Sample of %i searched objects and %i of contamination objects was loaded" % (len(searched), len(others))

        static_params = {}
        if opts.template:
            temp_stars = getStars(
                opts.template, project_settings.INP_LCS, query_path=project_settings.QUERIES)
        for desc in descriptors:
            if issubclass(desc, ComparativeBase):
                static_params[desc.__name__] = {}
                static_params[desc.__name__]["comp_stars"] = temp_stars

        filt_name = opts.filt_name
        if not filt_name:
            filt_name = DEF_FILT_NAME
        if "." in filt_name:
            filt_name = filt_name[:filt_name.rfind(".")]

        filter_path = os.path.join(project_settings.FILTERS, filt_name)

        d = tree()
        d[filt_name]

        rec(d, project_settings.FILTERS)

        save_params = {"roc_plot_path": filter_path,
                       "roc_plot_name": "ROC_plot.png",
                       "roc_plot_title": filt_name,
                       "roc_data_path": filter_path,
                       "roc_data_name": "ROC_data.dat",
                       "stats_path": filter_path,
                       "stats_name": "stats.dat"}

        try:
            ratios = [int(sp) for sp in opts.split_ratio.split(":")]
        except ValueError:
            raise ValueError(
                "Ratios have to be numbers separated by ':'. Got:\n%s" % opts.split_ratio)

        es = ParamsEstimator(searched=searched,
                             others=others,
                             descriptors=descriptors,
                             deciders=deciders,
                             tuned_params=tuned_params,
                             static_params=static_params,
                             split_ratio=ratios[0] / sum(ratios[:2]))

        print "\nTuning is about to start. There are %i combinations to try" % len(tuned_params)

        star_filter, _, _ = es.fit(_getPrecision, save_params=save_params)

        FiltersSerializer(
            filt_name + ".filter", filter_path).saveFilter(star_filter)

        plotProbabSpace(star_filter, opt="save", path=filter_path,
                        file_name="ProbabSpace.png",
                        title="".join([d.__name__ for d in deciders]),
                        searched_coords=star_filter.searched_coords,
                        contaminatiom_coords=star_filter.others_coords)
        desc_labels = []
        for desc in star_filter.descriptors:
            if hasattr(desc.LABEL, "__iter__"):
                desc_labels += desc.LABEL
            else:
                desc_labels.append(desc.LABEL)

        plotHist(star_filter.searched_coords, star_filter.others_coords,
                 labels=desc_labels, save_path=filter_path,
                 file_name="CoordsDistribution")

        header = "\t".join(desc_labels)
        np.savetxt(os.path.join(project_settings.FILTERS, filt_name, "searched_coords.dat"),
                   star_filter.searched_coords, "%.3f", header=header)
        np.savetxt(os.path.join(project_settings.FILTERS, filt_name, "contam_coords.dat"),
                   star_filter.others_coords, "%.3f", header=header)

        print "\nIt is done.\n\t" + "#" * len(header)

    except Exception, e:
        if debug:
            raise
        indent = len(program_name) * " "
        sys.stderr.write(program_name + ": " + repr(e) + "\n")
        sys.stderr.write(indent + "  for help use --help")
        return 2


def _getPrecision(*args, **kwargs):
    return kwargs["precision"]

if __name__ == "__main__":
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    sys.exit(main())
