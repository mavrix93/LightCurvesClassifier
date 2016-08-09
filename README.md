Light Curve Analyzer



Usage

The usage can be divided into two main steps:


Obtain parameters of filters
Systematic search in given database

There are a tool for every of these steps. The first helps to calculate the propriety of chosen filters and find optimal values for them. The second proceed searching into the database according to file of queries. Results are saved into a log file and can be easily managed by the tool for reading the log file.


Input 
	
	Light curves of searched type of stars 
	Light curves of unsearched types in order to learn what is not desired
	Specify filters which will be used, it is possible to implement own 
	Specify database connector for searching (can be even searching thru downloaded lcs in folder) or implement own
	Verify 
	
	Verify input light curves can be resolved into LightCurve objects
	Verify whether the filters implements Filter class
	Verify whether the database connector implements LightCurvesDb class
	Calculate parameters of the filters
	
	Get best parameters of the filters
	Get accuracy of this filters (according this user can decide if a filter will be used)
	Searching
	
	Specify extent of searching or make file of query
	Systematic search in the specified database
	Save matched light curves as files (by default - can be changed) 
	Generate status file (query file with new columns of searching status)
	In case of interuption, rerun scanning according to last log)
	
Structure of the package




entities
	
	The most elemental classes of the program (e.g. Star, LightCurve, Declination etc.)
	dbtier
	
	Classes which provide unitary data from the databases (Objects of Star type)
	utils
	
	Modules for analysing time series, support methods for other classes, methods for visualizing data etc.
	starsproccesing
	
	Modules for proccesing light curves and sorting them by filters
	commandline
	
	Main modules for executing the program and its tools
	conf
	
	Configuration files containing information about structure of data folders and classes for estimating parameters of the filters
	tests
	
	Test classes for checking performance of the program
	

Entities

Here is an example of creating a Star object containing a light curve. Anyway it is not necessary to create these objects manuly, but they will be created by StarProviders (e.g. databse connectors).

[language=Python]
import numpy as np
from entities.right_ascension import RightAscension
from entities.declination import Declination
from entities.light_curve import LightCurve
from entities.star import Star

#Coordinate values and its units
ra_value, ra_unit = 5.5	, "hours"
dec_value, dec_unit = 49.1, "degrees"

#Identifiers of the star
db_origin, identifier = "ogleII", "field": "LMC_SC1", "starid": 123456, "target":"lmc",

#Data for the ligh curve        
time_data = np.linspace(245000, 245500, 500)
mag_data = np.sin(np.linspace(0,10,500)) + np.random.rand()
err_data = np.random.rand(500)


#Creating coordinate objects
ra = RightAscension(ra_value, ra_unit)
dec = Declination(dec_value, dec_unit)

#Creating light curve object        
lc = LightCurve([time_data, mag_data, err_data])

#Creating star object        
star = Star(db_origin: identifier, ra, dec, "v_mag" : v_mag, "b_mag" : b_max)
star.putLightCurve(lc)


LightCurve

This the most fundamental class of the program, however it is not accessed directly but just like an attribute of Star object (see below). It contains data about the light curve (times, magnitudes and optionally errors).

Star

This the most fundamental objects of the program. Star objects contain information about the inspected astronomical body - identificators in certain databases, coordinates, light curve etc.. 

TODO: Write more about attributes, identifiers, methods etc.

AbstractCoordinate, Declination and RightAscension

The AbstractCoordinate is the common abstract class which is inherited by both Declination and Right Ascension. Differencies for these two classes are just in used units and its restrictions. Coordinate unit can be specified and values are then checked whether they corespond with coordinate restrinctions.


Exceptions
There are all exceptions which can be raised by the program




Db tier

In the example below stars in certain area in OGLEII database is obtained.

[language=Python]
from entities.right_ascension import RightAscension
from entities.declination import Declination
from db_tier.stars_provider import StarsProvider

db_key = "ogle"
query =
        "ra":RightAscension(5.56, "hours"),
        "dec":Declination(-69.99),
        "delta":3,
        "target":"lmc"
         


Database connector class in resolved by dbkey (see StarsProvider below). For example for loading stars from folder input would like this:

[language=Python]
db_key = "file"
query = "path" : path_to_the_folder_of_light_curve_files


Moreover OgleII client class supports query via field-starid-target or starcat-target. The type of query is resolved automatically by keys in query dictionary.

[language=Python]
db_key = "ogle"
query ="field": "LMC_SC1", "starid": 12345, "target": "lmc"	

The second part of the example (below) is common for every database and every type of query (beause of StarsProvider interface).


[language=Python]
stars_prov = StarsProvider().getProvider(obtain_method = db_key,
                                        obtain_params = query)
stars = stars_prov.getStarsWithCurves()

StarsCatalogue

Common abstract class for every database connector which provides Star objects. Every inherited classes need to impelement method getStars.

LightCurvesDb

The LightCurvesDb is common class for all connector classes to the databases which contain light curves data. It also inherit StarsCatalogue abstract class. That means that these connectors provide Star objects enchanted by LightCurve attributes.

StarsProvider

All database connectors are not accessed directly, but by this class. It reads from config file which contains keys and name of the database connector module in dbtier package. That allows to call db connectors by keys (see above in example).

CrossmatchManager
*NEED TO BE UPGRADED*

OGLEII

Connector class for OGLEII database thru web interface

FileManager

Manager for obtaining Star objects from the light curve files

TapClient

Common class for connectors to the databases via TAP protocol. The class can be accessed directly. In example below complete light curve of the star "MyStar1" is obtained in the database "http://mydb.org/tap" from table "lightcurvetable".

[language=Python]
tap_params = 
"URL" : "http://my_db.org/tap",
"table" : "light_curve_table",
"conditions" : ("ident1": "MyStar", "ident2": 1),
"select" : "*"

lc = TapClient().postQuery(tap_params)
light_curve = LightCurve(lc)


MachoDb
TODO: NEED TO BE UPGRADED

conf

The idea of conf files is about having all parameters in one place. The configuration file can be created like an ordinary text file in format  per row or it can be created automatically by tools for estimating he most optional parameters. 

glo
 Global parameters of the program. There are strucure and paths to the data folders (e.g. light curve folder of certain stars), verbosity level etc.
 
DefaultEstimator

Estimator class which is used by ParamsEstimation class (see below) by default. As all estimator classes it has to inherit methods of GridSearch library also it has to implement fit and score methods. The first method learns to recognize input stars according to the input sample and the second one calculate precision of examined combination.

ParamsEstimation

The class for calculating best filter parameters according to input sample of searched and undesired stars. It is also needed to specify combination of parameters for examing and the estimator (see above). In the following example AbbeValueFilter is tested or more precisely is tested which of given values is the most optimal. The result is saved into the file and printed.

[language=Python]
tuned_params = ["abbe_lim": 0.35,"abbe_lim": 0.4, "abbe_lim": 0.45]
es = ParamsEstimation(quasars, stars ,AbbeValueFilter , tuned_params)
es.fit()

filters params

There are configuration files for certain projects (e.g. filters parameters for quasars searching) in this subpackage. 

stars processing

utils

data analysis
Mainly there are functions for processing time series (e.g. calculate histogram, normalize, PAA etc.).

commons

There are decorators for validating input/output of functions. Usage is shown in example below. 

TODO: NEED TO BE CHECKED
[language=Python]
class Foo(object):
	@mandatory_args(("param1"),("param2","param3","param4"))
	@default_values(param5 = 1, param6 = 11)
	@args_type(param1 = (list,), param2 = (str, int), param3 = (str, int, float), param4 = (str,float))
	def __init__(self,*args,**kwargs):
	...	

Every Foo object has to be initialized with one or three parameters. In case of one it has to be list in case of three params - first has to be string or int etc. Also if  and  is not specified their value would be set by default decorator.

helpers

There are support functions (e.g. progress bar)

output process modules

Functions for serializing objects. Especially saving/loading them into/from the files. 

Stars

Methods for managing lists of Star objects. For instance getsortedstars takes list of stars and returns the dictionary where keys are types of the stars (e.g. quasars, cepheids etc.) and its values are lists of the stars of the certain type.

Also there are methods for visualizing stars. 



Output graph of plotStarsPicture method


stars processing
 This package contains three subpackages:

filters tools
	
	Support modules for particular filter implementations
	filters impl
	
	Star filters implementations
	systematic search
 
 Modules for systematic searching of databases and filtering its results
 
BaseFilter

Every filter has to inherit this class which ensures that every filter class has applyFilter method.

•

Implementing new modules
Filters
Database connectors




