# Light Curves Classifier

## Introduction
The Light Curve Classifier is a Python package for classifying astronomical objects. It is
accomplished mainly by their light curves, but there are no limits to achieve that
by any other attribute of stars. The package can used for several tasks:

+ Download light curves from implemented databases
+ Teach implemented filters on train sample in order to filter another stars
+ Run systematic search and filter stars directly in databases

New filters, database connectors or classifiers can be easily implemented thanks to class interfaces (see "Implementing new classes" section). However there are many of them already included. Package can be used in two ways:

+ Via command line API

+ By using the package programmatically 
Of course the second option brings much more functionality. However command line API allows accomplish the most of tasks.

## Philosophy of the program

[Workflow](https://cloud.githubusercontent.com/assets/17453516/23814530/26486e96-05e4-11e7-90cc-876eea1904dd.png)

Let's say that one has data of objects of interest and one would like to find other of these objects in huge databases. No matter what these objects are and what they have in common - all we have to do is to specify few parameters and the program will do all the magic for us. 


### Description of the stars
Stars can be described by many attributes like: distance, temperature, coordinates, variance, dissimilarity from our template curve, color indexes etc. For particular tasks these "properties of interest" have to be chosen - for example if one desires to classify members of a cluster of stars one would use distance and coordinates as values which describes particular stars. Another example could be distinguishing variable stars from non-variable, for this task one could use something like variance or for example the slopes of fitted light curves (with reduced dimension) by linear function.


### Classifying

Data of "stars of interest" and some other contamination data can be used as train sample. By chosing descriptive properties of stars we can transform all stars into parametric coordinates. These values can be used for training some supervised machine methods. After that they are able to decide if an inspected star belongs to the search group of stars.

### Searching

There are many connectors to astronomical databases such as: OgleII, Kepler, Asas, Corot and Macho. All one need to do is specify the queries for the selected database.


## Installation

The package can be easily installed via pip:

pip install lcc

Or it can be "installed" manually.

1) Download the package from git repository

2) Export the root of the package to sys path
	
There is one extra step if you want to use the command line API:

3) Copy lcc/api/lcc into a location of executables or add it to the sys/python path 

#### For linux users:
------
```
git clone https://github.com/mavrix93/LightCurvesClassifier.git
mv LightCurvesClassifier /to/new/location/of/the/package
cd /to/new/location/of/the/package
echo "export PYTHONPATH=$PYTHONPATH:/to/new/location/of/the/package/LightCurvesClassifier" >> ~/.bashrc

cp /to/new/location/of/the/package/LightCurvesClassifier/lcc/api/lcc /usr/local/bin/
```


## Command line 

The main tasks of the program will be introduced on the command line API usage. Skip this section to "Using the package" if there is no intention to use the command line API.

### Creating the project

Browse to the folder where you wish to create the new project and run:

```
lcc create_project MyFirstProject
```

Setting file and folders for inputs and outputs are created in the project directory. Now you can execute three commands from the project folder (in the directory where the setting file is):

1. lcc prepare_query
2. lcc make_filter
3. lcc filter_stars

#### Directories role

##### tun_params
Location of the files of combinations for tuning filter

#### queries
Location of the file for quering databases

##### filter
There are one folder per filter which contains the filter object and files with information about the filter tuning - probability plots,
ROC curves, statistical info etc.

##### inp_lcs
Location of light curve files

##### query_result
Output folder of found star objects

#### Prepare query
Support tool for making files of queries or files of tuning combinations in given ranges.

| option | flag option |  description | default value |
|:-------:|:---------:|:------:|:---------:|
|-o | --output | Name of the query file | my_query.txt |
|-p | --param | Parameter name which will be generated| |
|-r | --range | Range of parameters separated by ':' - from_num:to_num:step_num | |
| -d |--delim | Delimiter for the output file | ; |
| -f | --folder | Path where the query file will be saved * | current folder |

*There are two shortcuts for the --folder paramater to the folder for queries - "q" and for tuning parameters - "t".

Example

```
lcc prepare_query -o tune_lc_shape.txt -p CurvesShapeDescr:alphabet_size -r 5:19:3 -p CurvesShapeDescr:days_per_bin -r 30:120:40 -p QDADec:treshold -r 0.1:0.99:0.08
```

Thi genarates *tune_lc_shape.txt* file in *tun_params* directory which looks like that:

```
#QDADec:treshold;CurvesShapeDescr:alphabet_size;CurvesShapeDescr:days_per_bin
0.1;5;30
0.18;5;30
0.26;5;30
...
```

#### Make filter

This script creates new filter objects which are then able to recognize if an inspected
star object is a member of searched group or if it is not. The learning is performed
by different methods (which can be specified) on the train sample of searched objects and
the contamination sample. 


| option | flag option |  description | default value |
|:-------:|:---------:|:------:|:---------:|:-----:|:--------:|:------:|
| -i | --input | Name of the file of the tuning combinations (present in PROJEC_DIR/tun_params)| |
| -n | --name | Name of the filter (the filter file will be appended by ".filter" | Unnamed |
| -f | --descriptor | Descriptors (this key can be used multiple times | |
| -d | --decider | Decider for learning to recognize objects | |
| -s | --searched | Searched stars folder (present in PROJEC_DIR/inp_lcs)| |
| -c | --contamination | Contamination stars folder (present in PROJEC_DIR/inp_lcs)| |
| -t | --template | Template stars folder (present in PROJEC_DIR/inp_lcs) if comparative filters are used | |
| -p | --split | Split ratio for train-test sample | 3:1 |

Number of stars can be specified after the name of folders for loading the stars. If there is a *dir_name:number*, just *number* of stars are loaded (randomly). If there is a *dir_name%float_number*, just this precentage number if loaded.
Stars can be also obtained from databases. For this option *db_name:query_file* have to be specified. For example:
```
OgleII:query_file.txt
```
where *query_file.txt* is located in *PROJECT_DIR/queries*

Example:
```
lcc make_filter -i tuning_histvario.txt -f HistShapeDescr -f VariogramShapeDescr -s quasars:50 -c some_stars:50 -t templ_qso:1 -d GaussianNBDec -n HistVarioFilter
```
This command loads *tuning_histvario.txt* file of the combination of parameters (see example in "Prepare query" section), it uses Histogram Shape Descriptor  and Variogram Shape Descriptor to describe each star object. Train sample of searched stars is stored in *PROJECT_DIR/inp_lcs/quasars*, contamination sample in ROJECT_DIR/inp_lcs/some_stars* and a template star in ROJECT_DIR/inp_lcs/templ_qso*.

After the tuning result files will be saved in *PROJECT_DIR/filter/HistVarioFilter*.

#### Filter stars
After creation of filter object it is possible to use the filter. The searching can be executed on the remote databses or on the files stored locally.


| option | flag option |  description | default value |
|:-------:|:---------:|:------:|:---------:|
| -r | --run | Name of this run (name of the folder for results)| |
| -q | --query | Name of the query file in *PROJECT_DIR/queries* | |
| -d | --database | Searched database | |
| -s | --coords | Save params coordinates of inspected stars if 'y' | y |
| -f | --filter | Name of the filter file in the filters folder |   |  |

Example:

```
lcc filter_stars -r FirstRun -d OgleII -q ogle_query.txt -f HistVario/HistVario.filter -s y
```

This command creates folder *FirstRun* in *PROJECT_DIR/query_results* where status file about progress of filtering and passed lightcurves will be stored. Search is executed in *OgleII* via queries in *PROJECT_DIR/queries/ogle_query.txt* by using *HistVario.filter* for filtering.

### Examples

#### Filtering stars via Abbe Value Descriptor

Our task is to find stars with a trend in their light curves and then find some of them in OgleII database. It can be reached by calculating of Abbe value - light curves with a trend have Abbe values near to 0 and non-variable light curves 1.

First of all we need to prepare files of descriptor parameters which will be tuned and queries for OgleII databse. For Abbe Value Descriptor there is just one parameter which have to be find - dimension of reduced light curve (bins). Let's try values between 10 and 150 which step of 5:

```
lcc prepare_query -o tuning_abbe.txt  -p AbeValueDescr:bins -r 10:150:5 -f t
```

This generates file named "tuning_abbe.txt" in *tun_params*.

| #AbbeValueDescr:bins |
|-------|
| 10    |
| 20    |
| 30    |
| ...   |
| 130   |
| 140   |


```
lcc prepare_query -o query_ogle.txt  -p starid -r 1:100 -p field_num -r 1:10 -p target -r lmc -f q
```


Then we can learn AbbeValueDesc on the train sample of quasars and the non variable stars as contamination sample. Our learning method is GaussianNBDec (description of all implemented methods can be found in a next section).

```
lcc make_filter -i tuning_abbe.txt -f AbbeValueDesc -s quasars -c stars -d GaussianNBDec -n AbbeValue_quasar
```



```
lcc filter_stars.py -d OgleII -i query_ogle.txt -f AbbeValue_quasar/AbbeValue_quasar.filter -r FoundQuasars
```


# The package

Let's look how could be achieved the same result as in previous example by using the package directly.

```
import os
import pandas as pd

from lcc.db_tier.stars_provider import StarsProvider
from lcc.stars_processing.tools.params_estim import ParamsEstimator
from lcc.stars_processing.systematic_search.stars_searcher import StarsSearcher
from lcc.utils.helpers import  get_combinations
from lcc.data_manager.package_reader import PackageReader


# The query #
#=============

# Tunning parameters
tun_param = "bins"
bin_from = 10
bin_to = 150
bin_step = 5

# Descriptor and decider
descr_name = "AbbeValueDescr"
decid_name = "GaussianNBDec"

# Loading training stars
LCS_PATH = "/home/martin/workspace/LightCurvesClassifier/data/project/inp_lcs"
obt_method = "FileManager"
quasars_path = os.path.join(LCS_PATH, "quasars")
stars_path = os.path.join(LCS_PATH, "some_stars")

# Query for OgleII
db_name = "OgleII"
starid_from = 1
# starid_to = 100
starid_to = 10
field_num_from = 1
# field_num_to = 10
field_num_to = 2
target = "lmc"


# Prepare for tuning
descriptor = PackageReader().getClassesDict("descriptors").get(descr_name)
decider = PackageReader().getClassesDict("deciders").get(decid_name)

tun_params = [{descr_name : {tun_param : abbe_value}} for abbe_value in range(bin_from, bin_to, bin_step)]

quasars = StarsProvider.getProvider(obt_method, {"path" : quasars_path}).getStarsWithCurves()
stars = StarsProvider.getProvider(obt_method, {"path" : stars_path}).getStarsWithCurves()

# Estimate all combinations and get the best one
es = ParamsEstimator(searched=quasars,
                     others=stars,
                     descriptors=[descriptor],
                     deciders=[decider],
                     tuned_params=tun_params)

star_filter, best_stats, best_params = es.fit()

# Prepare queries and run systematic search by using the filter
queries = get_combinations(["starid", "field_num", "target"],
                           range(starid_from, starid_to),
                           range(field_num_from, field_num_to),
                           [target])

searcher = StarsSearcher([star_filter],
                         obth_method=db_name)
searcher.queryStars(queries)

passed_stars = searcher.passed_stars

```

# Database connectors
## Usage


There are two groups of database connectors:

+ Star catalogs
    - Information about star attributes can be obtained

+ Light curves archives
    - Information about star attributes can be obtained and its light curves
    
In term of program structure - all connectors return star objects, but just Light curves archives also obtaining light curves. Star objects can be obtained by the common way:

    queries = [{"ra": 297.8399, "dec": 46.57427, "delta": 10},
                {"kic_num": 9787239},
                {"kic_jkcolor": (0.3, 0.4), "max_records": 5}]
    client = StarsProvider().getProvider(obtain_method="KeplerArchive",
                                         obtain_params=queries)
    stars = client.getStarsWithCurves()

Because of common API for all connectors therefore databases can be queried by the same syntax. Keys for quering depends on designation in particular databases. However there are common keys for cone search:

* ra
    - Right Ascension in degrees
    
* dec
    - Declination in degrees
    
* delta
    - Circle radius in arcseconds
    
* nearest (optional)
    - Nearest star to the seach center is returned if it is True
    
    
Stars can be then easily crossmatched:

    queries = [{"ra": 0.4797, "dec": -67.1290, "delta": 10, "nearest": True}]
    
    one_star_in_many_databases = []
    for archive in ["AsasArchive", "OgleII", "CorotBrightArchive", "KeplerArchive"] :
        client = StarsProvider().getProvider(obtain_method=archive,
                                             obtain_params=queries)
        one_star_in_many_databases += client.getStarsWithCurves()

## Implementing new connectors

All connectors accept input (queries) in unitary format (list of dictionaries) and implements one (stars catalogs) or two (light curves archives) methods which return Star objects. In order to access the connector by *StarsProvder* (as is shown in examples above) the module have to be located in *db_tier.connectors* package. This is all magic need to be done to have compatible connector with the rest of the package.

The connectors have to inherit *StarsCatalogue* or *LightCurvesDb* classes. This ensures that all connectors are able to return unitary Star objects in the same manner. Inheritage of these classes helps *StarsProvider* to find connectors.

Moreover connectors can inherite other interface classes which bring more funcionality to child classes. For example *TapClient* can be used for VO archives providing TAP access. 

### VizierTapBase

Common interface for all databases accessible via Vizier. For many databases there is no need to write any new methods. Let's look at an example of implementation of MACHO database:

    class MachoDb(VizierTapBase, LightCurvesDb):
        '''
        Client for MACHO database

        EXAMPLES:
        ---------
            queries = [{"Field": 1 , "Tile": 3441, "Seqn": 25}]
            client = StarsProvider().getProvider(obtain_method="MachoDb",
                                                 obtain_params=queries)
            stars = client.getStarsWithCurves()
        '''

        TABLE = "II/247/machovar"
        LC_URL = "http://cdsarc.u-strasbg.fr/viz-bin/nph-Plot/w/Vgraph/txt?II%2f247%2f.%2f{macho_name}&F=b%2br&P={period}&-x&0&1&-y&-&-&-&--bitmap-size&600x400"

        NAME = "{Field}.{Tile}.{Seqn}"
        LC_FILE = ""

        LC_META = {"xlabel": "Time",
                   "xlabel_unit": "MJD (JD-2400000.5)",
                   "origin": "MACHO"}

        IDENT_MAP = {"MachoDb":  ("Field", "Tile", "Seqn")}
        MORE_MAP = collections.OrderedDict((("Class", "var_type"),
                                            ("Vmag", "v_mag"),
                                            ("Rmag", "r_mag"),
                                            ("rPer", "period_r"),
                                        ("bPer", "period_b")))

   
