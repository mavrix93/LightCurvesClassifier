# Light Curve Classifier

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

Let's say that one has data of objects of interest and one would like to find other of these objects in huge databases. No matter what these objects are and what they have in common - all we have to do is to specify few parameters and the program will do all the magic for us. 


### Description of the stars
Stars can be described by many attributes like: distance, temperature, coordinates, variance, dissimilarity from our template curve, color indexes etc. For particular tasks these "properties of interest" have to be chosen - for example if one desires to classify members of a cluster of stars one would use distance and coordinates as values which describes particular stars. Another example could be distinguishing variable stars from non-variable, for this task one could use something like variance or for example the slopes of fitted light curves (with reduced dimension) by linear function.


### Classifying

Data of "stars of interest" and some other contamination data can be used as train sample. By chosing descriptive properties of stars we can transform all stars into parametric coordinates. These values can be used for training some supervised machine methods. After that they are able to decide if an inspected star belongs to the search group of stars.

### Searching

There are many connectors to astronomical databases such as: OgleII, Kepler, Asas, Corot and Macho. All one need to do is specify the queries for the selected database.


## Installation

So far the package is not stored in pip repository and it has to be "installed" manually.

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
|:-------:|:---------:|:------:|:---------:|:-----:|:--------:|:------:|
|-o | --output | Name of the query file | my_query.txt |
|-p | --param | Parameter name which will be generated| |
|-r | --range | Range of parameters separated by ':' - from_num:to_num:step_num | |
| -d |--delim | Delimiter for the output file | ; |
| -f | --folder | Path where the query file will be saved * | current folder |

*There are two shortcuts for the --folder paramater to the folder for queries - "q" and for tuning parameters - "t".

#### Make filter
This script creates new filter objects which are then able to recognize if an inspected
star object is a member of searched group or if it is not. The learning is performed
by different methods (which can be specified) on train sample of searched objects and
contamination objects (other stars).

#### Filter stars
After creation of filter object it is possible to filter given sample of star objects. In-
spected stars can be obtained by various connectors which will be described in a next
chapter.





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
