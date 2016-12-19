# Light Curve Classifier

## Introduction
The Light Curve Classifier is a Python package for classifying astronomical objects. It is
accomplished mainly by their light curves, but there are no limits to achieve that
by any other attribute of stars. The package can used for several tasks:

+ Download light curves from implemented databases
+ Teach implemented filters on train sample in order to filter another stars
+ Run systematic search and filter stars directly in databases

New filters, database connectors or classifiers can be easily implemented thanks to class interfaces (see "Implementing new classes" section). However there are many of them already included, so there are lots of tasks which can be done just via command line. Package can be used in two ways:

+ Via command line

+ By using the package programatically 

The second option looks more complicated for the first sight, but the uppermost layer of modules which need to be used is quite simple. This approach allows to utilize the whole potential of the program. In the first part usage via command line will be introduced.

## Data folders tree

In order to create necessary data folders for input/output there is a script build data structure.py

There is one mandatory key which have to be specified.
There are example scripts in src/examples and example light curves in src/examples/ex-
amples data. If build data structure.py is run with ’y’ option all example data is trans-
ferred into data folders and all example scripts are executed. There is no need to store
more data, because prepare scripts will create files for tuning and queries and tuning
scripts make filters etc.
In case of parameter ’y’ just empty data folders will be created.
3

## Command line 

These exutables are all you need for using the package:

1. make filter.py
2. filter stars.py
3. prepare query.py

#### Make filter
This script creates new filter object which is then able to recognize if an inspected
star object is a member of searched group or if it is not. The learning is performed
by different methods (which can be specified) on train sample of searched objects and
contamination objects (other stars).

#### Filter stars
After creation of filter object it is possible to filter given sample of star objects. In-
spected stars can be obtained by various connectors which will be described in a next
chapter.

#### Prepare query
Support tool for making files of queries or files of tuning combinations in given ranges.






### Intro via example

#### Filtering stars via Abbe Value Filter

Our task is to find stars with a trend in their light curves. It can be reached by calculating of Abbe value.

First of all we need to prepare files of filter parameters which will be tuned. For Abbe Value Filter there is just one parameter which have to be find - dimension of reduced light curve (bins). Let's try values between 10 and 150 which step of 5:

```
./prepare_query.py -o tuning_abbe_filter.txt  -p bins -r 10:150:5
```

This generates file named "tuning_abbe_filter.txt" in data/inputs.

| #bins |
|-------|
| 10    |
| 20    |
| 30    |
| ...   |
| 130   |
| 140   |


Then we can learn AbbeValueFilter on train sample of quasars and non variable stars as contamination sample. Our learning method is GaussianNBDec (description of all implemented methods can be found in a next section).

```
./make_filter.py  -i tuning_abbe_filter.txt -f AbbeValueFilter -s quasars -c stars -d GaussianNBDec -o AbbeValue_quasar.filter -l AbbeValue_quasar
```



```
./filter_stars.py -d FileManager -i query_folders.txt -f AbbeValue_quasar.filter -o examples
```



# Database connectors
## Usage


There are two groups of database connectors:

+ Star catalogs
    - Information about star attributes can be obtained

+ Light curves archives
    - Information about star attributes can be obtained and its light curves
    
In term of program structure - all connectors return stars objects, but just Light curves archives also obtaining light curves. Star objects can be obtained by common way:

    queries = [{"ra": 297.8399, "dec": 46.57427, "delta": 10},
                {"kic_num": 9787239},
                {"kic_jkcolor": (0.3, 0.4), "max_records": 5}]
    client = StarsProvider().getProvider(obtain_method="KeplerArchive",
                                         obtain_params=queries)
    stars = client.getStarsWithCurves()

Because of common API for all connectors therefore databases can be queried by the syntax. Keys for quering depends on designation in particular databases. Anyway there are common keys for cone search:

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

All connectors accept input (queries) in unitary format (list of dictionaries) and implements one (stars catalogs) or two (light curves archives) methods which return Star object. In order to access the connector by *StarsProvder* (as is shown in examples above) the module have to be located in *db_tier.connectors* package. This is all magic need to be done to have compatible connector with rest of the package.

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

    
## Available connectors
### KeplerArchive
Connector to Kepler Input Catalog Targets by [kplr](http://dan.iel.fm/kplr/) package. See available query keys in [official field description](http://archive.stsci.edu/search_fields.php?mission=kic10). 
