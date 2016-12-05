# Light Curve Classifier

## Introduction
The Light Curve Classifier is a Python package for classifying astronomical objects. It is
accomplished mainly by their light curves, but there are no limits to achieve that
by any other attribute of stars. The package can used for several tasks:

+ Download light curves from implemented databases
+ Learn implemented filters on train sample and find the most optional parameters
+ Run systematic search and filter stars directly in databases

New filters, database connctors or learning methods can be easily implemented thanks to class interfaces (see "Implementing new classes" section). However there are many of them already included, so there are lots task which can be done just via command line. These exutables are all you need for using the package:

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

## Usage

### Filtering stars via Abbe Value Filter

Our task is to find stars with a trend in their light curves. This can be reached by calculating of Abbe value.

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






Build data folders tree and examples
In order to create necessary data folders for input/output there is a script build data structure.py.
It will be disused about it more in 3.2. Before using it is needed to tun the builder.
There is one mandatory key which have to be specified.
There are example scripts in src/examples and example light curves in src/examples/ex-
amples data. If build data structure.py is run with ’y’ option all example data is trans-
ferred into data folders and all example scripts are executed. There is no need to store
more data, because prepare scripts will create files for tuning and queries and tuning
scripts make filters etc.
In case of parameter ’y’ just empty data folders will be created.
3
How does it work?
The package is quite extensive and capable to be extended by user classes (see Pro-
gramers guide for more information). However, the upper most layer for users usage is
quite simple and straightforward. Whole procedure of finding the most optional filter
parameters and then sorting stars can be executed by two commands e.g.:
m a k e f i l t e r . py − i f i l t e r c o m b i n a t i o n s . t x t −f C o m p a r i n g F i l t e r −s q u a s a r s
−c c e p h e i d s −d NeuronDecider −o M y F i l t e r . p i c k l e
f i l t e r s t a r s . py − i o g l e q u e r y . t x t −o o g l e l c s −d ” O g l e I I ” −f M y F i l t e r .
pickle
All combinations for evaluating are located in ’filter combinations.txt’, ’ComparingFil-
ter’ is used, searched stars are quasars and there is a sample of cepheids in order to
train the ’NeuronDecider’ and the most optional filter is saved as ’MyFilter.pickle’.
This filter is then used for filtering ’OgleII’ database via queries in ’ogle query.txt’ and
the result file with light curves are saved into ’ogle lcs’ folder.
3.1
Status file
Parameters to try or queries can be specified in a special file where first row starts with
’#’ and then there are names of parameters which can be used for finding the most
optional parameters of a filter or as query for a database. Next rows consist of values
for tuning or queries. All columns are separated by ’;’ (can be changed in settings).
Example status files used as input
#s t a r i d ; t a r g e t ; f i e l d n u m
5 ; lmc ; 1
7 ; smc ; 1
7 5 ; lmc ; 2
23.2 Data folder hierarchy
3 HOW DOES IT WORK?
1 ; smc ; 2
Listing 1: Query Ogle database
#d a y s p e r b i n
0.5
10
30
50
Listing 2: Tune AbbeValueFilter according to given combination of parameters
Example output status files:
#vario days per bin vario alphabet size false negative rate
9
17
0.0
8
16
0.0
false positive rate true negative rate precision true positive rate
0.2
0.8
0.83
1.0
0.2
0.8
0.83
1.0
Table 1: Combinations for tuning and result statistical values
#s t a r i d ; f i e l d n u m ; t a r g e t ; name ; found ; f i l t e r e d ; p a s s e d
1 ; 1 ; lmc ; LMC SC1 1 ; True ; True ; F a l s e
2 ; 1 ; lmc ; LMC SC1 2 ; True ; True ; F a l s e
3 ; 1 ; lmc ; LMC SC1 3 ; True ; True ; F a l s e
4 ; 1 ; lmc ; LMC SC1 4 ; True ; True ; F a l s e
5 ; 1 ; lmc ; LMC SC1 5 ; True ; F a l s e ; F a l s e
6 ; 1 ; lmc ; LMC SC1 6 ; True ; True ; F a l s e
7 ; 1 ; lmc ; LMC SC1 7 ; True ; True ; F a l s e
8 ; 1 ; lmc ; LMC SC1 8 ; True ; True ; F a l s e
9 ; 1 ; lmc ; LMC SC1 9 ; True ; True ; F a l s e
Listing 3: Queries and result of filtering
3.2
Data folder hierarchy
Next to the src/ (source) folder there is a data/ folder where all data files are saved.
All input/outputs are loaded/saved into a folder in data/.
This behavior can be suppressed by entering word ’HERE:’ (e.g. ’HERE:file name’). It
forces to take relative path from the directory of executing the script.
There are 5 main folders:
1. data/inputs/
• Location of files of queries and files from tuning parameters
2. data/light curves/
• Location of light curve subfolders.
3. data/star filters/
33.3 Getting stars
3 HOW DOES IT WORK?
• Location where tuned filters are saved and can be loaded by make filer.py
script
4. data/tuning logs/
• Location of output files from tuning - statistic for every combination of pa-
rameters, graphs (probability distribution with train objects and histograms).
5. data/databases/
• Location of local db files (e.g. sqlite db files).
3.3
Getting stars
For filtering
Stars for filtering can be obtained by providing database key and name of query file
separated by ”:”.
• db name : query f ile.
Database key is resolved as name of connector class (Any class in src/db tier/connectors/
which inherits StarsCatalogue base class) and query f ile is name of the file with queries
in data/inputs/.
#s t a r i d ; t a r g e t ; f i e l d n u m
5 ; lmc ; 1
5 ; smc ; 1
5 ; smc ; 2
8 ; lmc ; 1
Listing 4: Example query file for Ogle database
For tuning filters
There are some special approaches to obtain stars for tuning filters. The approach
mentioned above for filtering is accessible by almost the same way, but with adding key
”QUERY” as is shown below.
1. QUERY:db name : query f ile
- Remote database is queried (db key is name of connector class)
Example: QUERY:OgleII:query file.txt
2. LOCAL:db name : query f ile
- Local database is queried (according to key in settings.DATABASES)
Example: LOCAL:milliquas:query file.txt
43.4 Deciders
4 WHAT CAN BE USED?
3. stars f older key : number or stars f older key%f loat number or stars f older key
- Light curves from folder according to first key is loaded (according to settings.STARS PATH
dictionary). All stars are obtained if there is no special mark with number, in
case of integer after ’:’ just this number of stars are loaded and if there are is a
float number after ’%’ this percentage number of all stars are loaded.
Example: quasars:10 or be stars%0.5 or cepheids
The behavior of last two approaches is possible via first method. Local database db key
(connector class name) is LocalDbClient and then it is necessary to add column named
db key into query file to resolve which local database will be queried. Light curves in
folders can be accessed by F ileM anager and including path column (optionally with
f iles limit column).
#r mag ; b mag ; s t a r c l a s s ; r e d s h i f t
>1; >1;Q;>5
Listing 5: Query file for LOCAL:db name : query f ile
Please note that using special symbols ”>”, ”<” an ”! =” is possible just for local
database queries so far. This will be upgraded in a next version.
3.4
Deciders
Deciders manage all learning and then recognizing of inspected objects. They can
be loaded via name of their class (if they are located in src/stars processing/deciders
inheriting BaseDesider class). They are learned on train sample of searched and con-
tamination objects. After learning there are tuning log file which evaluate precision of
the filtering. Also there are histograms for every free variable and probability space
plot if there is two free variables.
In current version, parameters of filters are evaluated according to precision defined
true positive
. The combination with highest precision is considered as the
as true positive+f
alse p ositive
best. It can be changed in cong/deciders settings.
4
What can be used?
There are many modules ready to use - filters, connectors and deciders. In this chapter
they will be briefly introduced.
4.1
Filters
ColorIndexFilter
ColorIndexFilter sorts stars according to magnitudes in different filters. It is necessary
to specify colors for a filter as python list and particular colors surrounded by commas
as is shown in 6. Ranges of colors are learned by a decider.
54.1 Filters
4 WHAT CAN BE USED?
#c o l o r s
[ ” b mag−r mag ” ]
[ ” v mag ” , ” i mag ” ]
[ ” b mag−r mag ” , ”v mag−i mag ” ]
Listing 6: File of combinations for tuning
AbbeValueFilter
Abbe value quantify extensions of trends in light curves and it is defined as:
n
A =
n − 1
n−1
2
μ=1 (x μ+1 − x μ )
n
 ̄ ) 2 ,
μ=1 (x μ − x
.
(1)
The parameter which needs to be calculated is days per bin which is ratio for dimension
transfer. Inner variable which is calculated by learning is Abbe value limit of searched
objects and contamination objects.
ComparingFilter
The filter compare two light curves of stars and measure dissimilarity of them by SAX
method (see https://cs.gmu.edu/ jessica/sax.htm). Methods for comparing light curves
are described by sub-filters. There are three implemented sub-filters:
• CurvesShapeFilter - compares shapes of light curves
• HistShapeFilter - Compares shapes of light curve’s histograms
• VariogramShapeFilter - Compare shapes of light curve’s variograms
Given sample of searched objects is split into a train sample and a reference sample
which is then compared with inspected light curves. There are coordinates (one co-
ordinate per sub-filter) calculated for every inspected star as average distance to all
reference stars (comparing stars). See 6.1.
During tuning filters there is no need to specify all subfilters , but just ComparingFilter
and subfilters are resolved automatically by parameters specified in the file of filter
combinations (see 6.1)
VariogramSlope
It filters stars according to variogram slopes of their light curves.
CurveDensityFilter
It filters stars with lower density of measurement per day then it is desired. For example
it can filter all stars with light curves where is no more measurement then 50 per day
etc.
64.2 Implemented connectors
4.2
4 WHAT CAN BE USED?
Implemented connectors
OgleII BVI database
This module is connected on query webpage at http://ogledb.astrouw.edu.pl/ ogle/photdb/bvi query.html.
Database can be queried by one of these combinations
• ra, dec, target
• f ield, starid, target
• f ield num, starid, target
Both right ascension and declination are in angle degrees, target is lmc for Large Magel-
lanic Cloud, smc for Small Magellanic Cloud and bul for galactic bulge. Each observed
target is divided into f ields - LM C SC1, SM C SC1 and BU L SC1 are first fields
in these target areas. Anyway it is recommended to use f ield num so the root name
is resolved according to target. Query f ield:LM C SC11, starid:5, target:lmc is the
same as f ield num:11, starid:5, target:lmc.
Stars obtained from this database contain a light curve in I filter and length of approx-
imately 2000 days, coordinates and magnitudes in B, V and I filter.
LocalDbClient
This connector manages local databases. They are accessible via db key parameter. All
stars downloaded during filtering are uploaded into local database with a reference to
a folder and name of light curve file.
Also there is a Milliquas database (included as SQLite file) of 1.4 millions of quasars.
See http://heasarc.gsfc.nasa.gov/w3browse/all/milliquas.html. The database scheme is
the same as for database for saving downloaded stars.
74.2 Implemented connectors
Key
id
name
identifier
db origin
ra
dec
star class
light curve
uploaded
b mag
v mag
i mag
r mag
redshift
lc n
lc time delta
crossmatch id
Type
int
str
str
str
float
float
str
str
datetime
float
float
float
float
float
int
float
ints (one to many)
4 WHAT CAN BE USED?
Description
Database identifier
Name of the star
Identifier in the database db origin
Name of database from which it was downloaded
Right ascension on degreees
Declination in degrees
Name of type of the star
Name of light curve file and path from data/light curves
Date of uploading
Magnitude in B filter in mag
Magnitudein V filter in mag
Magnitude in I filter in mag
Magnitude in R filter in mag
Redshift value
Number of point of light curve
Time length of observing in light curve
Database identifier to crossmatched stars
Table 2: Database scheme for local and milliquas database
Database can be queried via keys in 2. It also supports >, < and ! = operators (as was
shown in 5). Star objects returned by queries also contain light curves, so it is possible
to filter them by light curve filters or just show their plots.
#r mag ; b mag ; db key
>1; >1; l o c a l
Listing 7: Query file for local database
#r mag ; b mag ; db key
>1; >1; m i l l i q u a s
Listing 8: Query file for milliquas database
Please note that there cannot be present two or more keys with one name in one query
(same row), so it is not possible to have close ranges of values so far. For example
dec > 20.4; dec < 20.5. This will be fixed in a next version.
KeplerArchive
Connector to Kepler Objects of Interest catalog [1] and its light curves from MAST [?].
The kplr package [?] was used for this purpose. There are two options for query so far:
1. By Kepler unique identifier - kic
2. By coordinates with square radius for area search
84.3 Deciders
5 USAGE
FileManager
This connector class manages light curve files. Path is resolved via settings.ST ARS P AT H
variable where key is the key which is mentioned in queries and value is real path. So it is
possible to load stars from any local folder in case if it is registered in settings.ST ARS P AT H.
However stars folders can be accessed even by specifying relative paths if path variable
starts with ”Here:”.
Please note that queried folder cannot contains other files with same suffix as light
curves - basically all file with suffix dat is considered as light curves. It can be changed
by suffix variable in the query file.
4.3
Deciders
Learned deciders estimate probability of membership of inspected objects to the searched
group. By default border value is set to 0.85 - every object with probability of member-
ship higher then 85% is considered as a member of searched group. It can be changed
in src/conf/deciders settings.py.
NeuronDecider
It learns neuron grid according to Pybrain implementation. By default there is one
hidden layer. It can be changed in src/conf/deciders settings.py. Number of input
neurons is flexible and it is automatically set according to number of free variables of
given filter. For more information see: pybrain.org
LDADec
See http://scikit-learn.org/0.16/modules/generated/sklearn.lda.LDA.html
GaussianNBDec
See http://scikit-learn.org/stable/modules/naive bayes.html#gaussian-naive-bayes
GMMBayesDec
See http://scikit-learn.org/stable/modules/naive bayes.html
QDADec
See http://scikit-learn.org/0.16/modules/generated/sklearn.qda.QDA.html
5
Usage
The brief description of program parameters can be shown by running with -h.
95 USAGE
Parameters for make filter.py
-i, –input
Name (with path if desired) to the file of filter parameters combinations in data/inputs/.
For relative path from folder of executing the script enter ”HERE:” before the path.
-o, –file name
Name of result filter file
-f, –filter
Name of filter (class) name in src/stars processing/filters imp/. More filters can be used
by adding more ”-f filter name” pairs. Run script without parameters to see available
filters.
-s, –searched
Special text for obtaining sample of searched stars. See 3.3 for more information.
-c, –contamination
Special text for obtaining sample of contamination stars. See 3.3 for more information.
-d, –decider
Decider (class) name in src/stars processing/deciders/. Run script without parameters
to see available deciders.
-l, –log
Name of the folder where log files about tuning and plots will be saved in data/tun-
ing logs/. For relative path from folder of executing the script enter ”HERE:” before
the path.
Parameters for filter stars.py
-o, –output
Name of folder for saving light curves of stars passed thru filtering from data/light curves/.
For relative path from folder of executing the script enter ”HERE:” before the path.
-i, –input
Name of the file of queries in data/inputs/. For relative path from folder of executing
the script enter ”HERE:” before the path.
105.1 Parameters for prepare query.py
6 EXAMPLES
-d, –database
Name of database connector (name of the class in src/db tier/connectors/). Run script
without parameters to see available connectors.
-f, –filter
Name of the filter file in data/star filters/. More filters can be used by adding more ”-f
filter name” pairs.
5.1
Parameters for prepare query.py
-o, –output
Name of the query file or file of filter combinations which will be created in data/inputs
-p, –param
Parameter name (column header) which will be generated
-r, –range
Range of parameters separated by ’:’ - from num:to num:step num.
-d, –delim
Delimiter for the output file
NOTE: There have to be the same number of –param an –range parameters
6
6.1
Examples
Classifying quasars in histogram-variogram space
Prepare files
First of all we need to create a file of parameters from which the best combination will
be used for creating the filter.
p r e p a r e q u e r y . py −o examples / t u n i n g h i s t v a r i o f i l t e r . t x t −p
h i s t d a y s p e r b i n −r ” 9 7 ; 8 0 ” −p v a r i o d a y s p e r b i n −r 9 −p
v a r i o a l p h a b e t s i z e −r 16 −p h i s t a l p h a b e t s i z e −r 7
Listing 9: Creating of the file o filter parameters
File of two combination tuning histvario filter.txt is created in data/inputs/examples/.
Also we can make query file for the filtering.
116.1 Classifying quasars in histogram-variogram space
6 EXAMPLES
p r e p a r e q u e r y . py −o examples / q u e r y o g l e . t x t −p s t a r i d −r 1 : 1 0 −p t a r g e t −
r lmc −p f i e l d n u m −r 1
Listing 10: Query file for OgleII database
Make filter
Now we can make the filter. In this step it is convenient to check deciders settings
file (src/conf/deciders settings.py) and think about T RESHOLD parameter. During
filtering all inspected stars are evaluated by probability of membership. All stars with
higher probability then T RESHOLD will pass thru filtering.
m a k e f i l t e r . py − i examples / t u n i n g h i s t v a r i o f i l t e r . t x t −f
C o m p a r i n g F i l t e r −s q u a s a r s : 2 0 −c c e p h e i d s : 5 −c s t a r s : 1 5 −d
GaussianNBDec −o examples / H i s t V a r i o q u a s a r s . f i l t e r − l examples /
HistVario quasars
Listing 11: Creating of the filter
We are training the filter to find quasars and distinguish them from non variable stars
and cepheids.
Tuning i s about t o s t a r t . There a r e 2 c o m b i n a t i o n s t o t r y
Estimating combinations :
[############################################################] 2/2
∗∗∗∗∗∗∗∗∗∗∗∗∗∗∗∗∗∗∗∗∗∗∗∗∗∗∗∗∗∗
Best params :
{
” vario days per bin ”: 9 ,
” hist alphabet size ”: 7 ,
” h i s t d a y s p e r b i n ” : 97 ,
” v a r i o a l p h a b e t s i z e ” : 16
}
Statistic :
{
” precision ”: 1.0 ,
” true positive rate ”: 0.833 ,
” true negative rate ”: 1.0 ,
” f als e po sit ive ra te ”: 0.0 ,
” f a l s e n e g a t i v e r a t e ”: 0.059
}
Listing 12: Commandline output
Information about tuning is saved into data/tuning logs to examples/HistVario quasars
(specified in 11 by ’-f’). There are one log file about precision of given combinations.
#v a r i o d a y s p e r b i n
vario alphabet size
true negative rate
9
7
97
hist alphabet size
hist days per bin
precision
true positive rate
false positive rate
false negative rate
16
1.0
0.833
1.0
0.0
0.059
126.1 Classifying quasars in histogram-variogram space
9
7
80
16
1.0
0.833
6 EXAMPLES
1.0
0.0
0.059
Listing 13: HistVario quasars log.dat
Also there are probability space image for every combination and histograms for every
combination and every inner variable - in this example inner variable is dissimilarity in
each subfilter.
13REFERENCES
REFERENCES
Filter stars in OgleII
Finally we can use our filter saved into data/star filters.
f i l t e r s t a r s . py − i examples / q u e r y o g l e . t x t −o examples / −d ” O g l e I I ” −f
examples / H i s t V a r i o q u a s a r s . f i l t e r
Listing 14: Run filtering in OgleII
Light curves of stars passed thru filtering are save into data/light curves + our output
directory specified by ’-o’. Status file is also created in the folder.
#s t a r i d ; f i e l d n u m ; t a r g e t ; name ; found ; f i l t e r e d ; p a s s e d
1 ; 1 ; lmc ; LMC SC1 1 ; True ; True ; F a l s e
2 ; 1 ; lmc ; LMC SC1 2 ; True ; True ; F a l s e
3 ; 1 ; lmc ; LMC SC1 3 ; True ; True ; F a l s e
4 ; 1 ; lmc ; LMC SC1 4 ; True ; True ; F a l s e
5 ; 1 ; lmc ; LMC SC1 5 ; True ; True ; True
6 ; 1 ; lmc ; LMC SC1 6 ; True ; True ; F a l s e
7 ; 1 ; lmc ; LMC SC1 7 ; True ; True ; F a l s e
8 ; 1 ; lmc ; LMC SC1 8 ; True ; True ; F a l s e
9 ; 1 ; lmc ; LMC SC1 9 ; True ; True ; F a l s e
Listing 15: Status file
Stars passed thru filtering are also uploaded into local database and can be obtained
again.
References
[1] “Nasa exoplanet archive.” http://exoplanetarchive.ipac.caltech.edu/.
14

