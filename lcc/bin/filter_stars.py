#!/usr/bin/env python
# encoding: utf-8
import json
from optparse import OptionParser
import os
import sys
import warnings

from lcc.db_tier.stars_provider import StarsProvider
from lcc.stars_processing.systematic_search.stars_searcher import StarsSearcher
from lcc.data_manager.status_resolver import StatusResolver
from lcc.entities.exceptions import QueryInputError
from lcc.data_manager.filter_serializer import FiltersSerializer
from lcc.data_manager.prepare_package import prepare_run



__all__ = []
__version__ = 0.3
__date__ = '2016-09-05'
__updated__ = '2017-02-08'


def main(project_settings, argv=None):
    program_info = """ABOUT
    The program downloads light curves from astronomical databases
    which pass thru given filters (or all).

    Database to query:
    ------------------
        Database is specified by '-d' and name of connector class.
        
        Note:
            There is a overview of available connectors at the end (if it is
            launched from command line without parameters)
        
    
    Status file:
    ------------
        Queries can be specified in the file where first
        row starts with '#' and then there are keys for query a database.
        Next rows consist of searched values. All columns are separated
        by ';' (can be changed in settings).
        
        Note:
            Example files can be find in data/inputs/examples
        
    Getting filter:
    ---------------
        Filter is loaded from prepared filter object (learned). If it is desired
        to load filter with certain parameters it can be also created by
        tuning tool by giving one combination of parameters.
        
        Note:
            All classes which inherits BaseFilter class located
            in the filters_imp package are considered as filters.
            
                
    Data folder hierarchy:
    -----------------------
        Next to src/ (source) folder there is a data/ folder where all data files
        are saved. All input/outputs are loaded/saved into a folder in data/.
        
        This behaviour can be suppressed by entering word 'HERE:'
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
        
    
    Running the program:
    -------------------
        By executing the script all inputs are verified and database is queried.
        Light curves (if any) of stars passed thru filtering are saved into
        'data/light_curves/' + your folder(specified via '-o') and stars are
        saved into local database. So it is possible to load them with their
        values or filter them by other filters.
        Also result file is saved into the folder with light curves in format
        'connector_name'_'filter_name'.txt. 
        
        (TODO)
        It is possible to continue with unfinished query. If query file has
        three more columns generated during the filtering about status of
        particular queries the program will find last finished query and it will
        continues form that point.

    Examples
    --------
        *Just downloading a light curves:
        
            For Ogle query file (named query.txt):
                #starid;field_num;target
                1;1;lmc
                12;1;lmc
            
            ./filter_stars.py -i query.txt -o my_lc_folder -d "OgleII"
        
            The light curves and status file will be saved into "data/light_curves/my_lc_folder" folder.
           
       
            
        *With filtering
        
            It is possible to insert more then one filter by adding combination
            '-f' + filter_name multiple times as is shown in example below.
            
            A command for executing searching light curves in OGLE database
            with filtering:
            
            ./filter_stars.py -i query.txt -o out/ -d "OgleII" -f abbe_filter.conf -f vario_slope.pickel
        """

    program_name = os.path.basename(sys.argv[0])
    program_version = "v0.2"
    program_build_date = "%s" % __updated__

    program_version_string = '%%prog %s (%s)' % (
        program_version, program_build_date)
    program_longdesc = "Run script without params to get info about the program and list of available databases"
    program_license = "Copyright 2016 Martin Vo"

    if argv is None:
        argv = sys.argv[1:]
    try:
        # setup option parser
        parser = OptionParser(version=program_version_string,
                              epilog=program_longdesc,
                              description=program_license)
        parser.add_option("-r", "--run", dest="run",
                          help="Name of this run (name of folder for results)", type=str)

        parser.add_option("-q", "--query", dest="query",
                          help="Name of the query file in %PROJECT_DIR/queries")

        parser.add_option("-d", "--database", dest="db",
                          help="Searched database")

        parser.add_option("-s", "--coords", dest="save_coords", default="y",
                          help="Save params coordinates of inspected stars if 'y'.")

        parser.add_option("-f", "--filter", dest="filt", action="append", default=[],
                          help="Name of the filter file in filters folder (%PROJECT_DIR/filters)")

        # process options
        opts, args = parser.parse_args(argv)

        if not len(argv):
            print program_info, "\n"
            print json.dumps(StarsProvider().STARS_PROVIDERS.keys())
            print "Run with '-h' in order to show params help\n"
            return False

        if opts.db not in StarsProvider().STARS_PROVIDERS:
            print "Error: " + "Unresolved database %s \n" % opts.db
            print json.dumps(StarsProvider().STARS_PROVIDERS.keys())
            return False

        # -------    Core    ------

        header = "#" + " " * 40 + \
            "Light Curves Classifier - Filter stars" + " " * 30 + "#"
        print "\n\n\t" + "#" * len(header)
        print "\t#" + " " * (len(header) - 2) + "#"
        print "\t" + header
        print "\t#" + " " * (len(header) - 2) + "#"

        UNFOUND_LIM = 2

        print "Loading query..."
        try:
            resolver = StatusResolver(
                status_file_path=os.path.join(project_settings.QUERIES, opts.query))
            queries = resolver.getQueries()
        except IOError:
            raise IOError("Query file was not found")
        except Exception as e:
            print "Err:", e
            raise QueryInputError("There is an issue in query file")

        print "Loading filters"
        star_filters = [FiltersSerializer(
            filt_name, project_settings.FILTERS).loadFilter() for filt_name in opts.filt]

        if not star_filters:
            filt_txt = ""
        else:
            filt_txt = [filt.__class__.__name__ for filt in star_filters]

        if opts.save_coords == "y":
            save_coords = True
        else:
            save_coords = False

        prepare_run(project_settings.RESULTS, opts.run)

        print _sum_txt(opts.db, len(resolver.status_queries), filt_txt)

        searcher = StarsSearcher(star_filters,
                                 save_path=os.path.join(
                                     project_settings.RESULTS, opts.run, "lcs"),
                                 save_lim=1,
                                 stat_file_path=os.path.join(
                                     project_settings.RESULTS, opts.run, "query_status.txt"),
                                 obth_method=opts.db,
                                 unfound_lim=UNFOUND_LIM,
                                 save_coords=save_coords)
        searcher.queryStars(queries)

    except Exception, e:
        print e, "\n\n"
        indent = len(program_name) * " "
        sys.stderr.write(program_name + ": " + repr(e) + "\n")
        sys.stderr.write(indent + "  for help use --help")
        return 2


def _sum_txt(db, num_queries, star_filters):
    '''Get info text before querying'''

    sumup_txt = '''
    \n\nDownloading from %s database is about to start..
The query file was loaded and there were found %i queries.
%s filter/s will be used.
    \n\n''' % (db, num_queries, star_filters)
    return sumup_txt


if __name__ == "__main__":
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    sys.exit(main())
