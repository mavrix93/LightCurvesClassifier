\documentclass[12pt]{article}
\usepackage[margin=3cm]{geometry}
\usepackage{srcltx}
\usepackage[utf8]{inputenc}
\usepackage{hyperref}
\usepackage{amsmath}
\usepackage{graphicx}
\usepackage{float}				%nenechá skákat text mezi tabulky
\restylefloat{table}		%též
\usepackage{subcaption}

\usepackage{listings}             % Include the listings-package
\usepackage{color}
 
\definecolor{mygreen}{rgb}{0,0.6,0}
\definecolor{mygray}{rgb}{0.5,0.5,0.5}
\definecolor{mymauve}{rgb}{0.58,0,0.82}

\lstset{ %
  backgroundcolor=\color{white},   % choose the background color
  basicstyle=\footnotesize,        % size of fonts used for the code
  breaklines=true,                 % automatic line breaking only at whitespace
  captionpos=b,                    % sets the caption-position to bottom
  commentstyle=\color{mygreen},    % comment style
  escapeinside={\%*}{*)},          % if you want to add LaTeX within your code
  keywordstyle=\color{blue},       % keyword style
  stringstyle=\color{mymauve},     % string literal style
  showstringspaces=false,
}

% Python for inline
\newcommand\pythoninline[1]{{\pythonstyle\lstinline!#1!}}

\begin{document}

\tableofcontents

\section*{Light Curve Analyzer}

fdff

\section{Usage}

The usage can be divided into two main steps:

\begin{enumerate}
\item Obtain parameters of filters
\item Systematic search in given database
\end{enumerate}

There are a tool for every of these steps. The first helps to calculate the propriety of chosen filters and find optimal values for them. The second proceed searching into the database according to file of queries. Results are saved into a log file and can be easily managed by the tool for reading the log file.

\begin{itemize}
\item Input 
	\begin{enumerate}
	\item Light curves of searched type of stars 
	\item Light curves of unsearched types in order to learn what is not desired
	\item Specify filters which will be used, \bf{it is possible to implement own }
	\item Specify database connector for searching (can be even searching thru downloaded lcs in folder) or \bf{implement own}
	\end{enumerate}
\item Verify 
	\begin{enumerate}
	\item Verify input light curves can be resolved into \textit{LightCurve} objects
	\item Verify whether the filters implements \textit{Filter} class
	\item Verify whether the database connector implements \textit{LightCurvesDb} class
	\end{enumerate}
\item Calculate parameters of the filters
	\begin{enumerate}
	\item Get best parameters of the filters
	\item Get accuracy of this filters (according this user can decide if a filter will be used)
	\end{enumerate}
\item Searching
	\begin{enumerate}
	\item Specify extent of searching or make file of query
	\item Systematic search in the specified database
	\item Save matched light curves as files (by default - \bf{can be changed}) 
	\item Generate status file (query file with new columns of searching status)
	\item In case of interuption, rerun scanning according to last log)
	\end{enumerate}
\end{itemize}

\section{Structure of the package}

%Diagram of the packages

\begin{itemize}
\item \textit{entities}
	\begin{itemize}
	\item The most elemental classes of the program (e.g. \textit{Star}, \textit{LightCurve}, \textit{Declination} etc.)
	\end{itemize}
\item \textit{db$\_$tier}
	\begin{itemize}
	\item Classes which provide unitary data from the databases (Objects of \textit{Star} type)
	\end{itemize}
\item \textit{utils}
	\begin{itemize}
	\item Modules for analysing time series, support methods for other classes, methods for visualizing data etc.
	\end{itemize}
\item \textit{stars$\_$proccesing}
	\begin{itemize}
	\item Modules for proccesing light curves and sorting them by filters
	\end{itemize}
\item \textit{commandline}
	\begin{itemize}
	\item Main modules for executing the program and its tools
	\end{itemize}
\item \textit{conf}
	\begin{itemize}
	\item Configuration files containing information about structure of data folders and classes for estimating parameters of the filters
	\end{itemize}
\item \textit{tests}
	\begin{itemize}
	\item Test classes for checking performance of the program
	\end{itemize}
\end{itemize}


\subsection{Entities}

Here is an example of creating a \textit{Star} object containing a light curve. Anyway it is not necessary to create these objects manuly, but they will be created by \textit{StarProviders} (e.g. databse connectors).

\begin{lstlisting}[language=Python]
import numpy as np
from entities.right_ascension import RightAscension
from entities.declination import Declination
from entities.light_curve import LightCurve
from entities.star import Star

#Coordinate values and its units
ra_value, ra_unit = 5.5	, "hours"
dec_value, dec_unit = 49.1, "degrees"

#Identifiers of the star
db_origin, identifier = "ogleII", {"field": "LMC_SC1", "starid": 123456, "target":"lmc"},

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
star = Star({db_origin: identifier}, ra, dec, {"v_mag" : v_mag, "b_mag" : b_max})
star.putLightCurve(lc)

\end{lstlisting}

\subsubsection*{LightCurve}

This the most fundamental class of the program, however it is not accessed directly but just like an attribute of \textit{Star} object (see below). It contains data about the light curve (times, magnitudes and optionally errors).

\subsubsection*{Star}

This the most fundamental objects of the program. Star objects contain information about the inspected astronomical body -- identificators in certain databases, coordinates, light curve etc.. 

TODO: Write more about attributes, identifiers, methods etc.

\subsubsection*{AbstractCoordinate, Declination and RightAscension}

The \textit{AbstractCoordinate} is the common abstract class which is inherited by both \textit{Declination} and \textit{Right Ascension}. Differencies for these two classes are just in used units and its restrictions. Coordinate unit can be specified and values are then checked whether they corespond with coordinate restrinctions.


\subsubsection*{Exceptions}
There are all exceptions which can be raised by the program




\subsection{Db tier}

In the example below stars in certain area in OGLEII database is obtained.

\begin{lstlisting}[language=Python]
from entities.right_ascension import RightAscension
from entities.declination import Declination
from db_tier.stars_provider import StarsProvider

db_key = "ogle"
query ={
        "ra":RightAscension(5.56, "hours"),
        "dec":Declination(-69.99),
        "delta":3,
        "target":"lmc"
         }

\end{lstlisting}

Database connector class in resolved by \textit{db$\_$key} (see \textit{StarsProvider} below). For example for loading stars from folder input would like this:

\begin{lstlisting}[language=Python]
db_key = "file"
query = {"path" : path_to_the_folder_of_light_curve_files}
\end{lstlisting}


Moreover \textit{OgleII} client class supports query via field-starid-target or starcat-target. The type of query is resolved automatically by keys in \textit{query} dictionary.

\begin{lstlisting}[language=Python]
db_key = "ogle"
query ={"field": "LMC_SC1", "starid": 12345, "target": "lmc"}		
\end{lstlisting}

The second part of the example (below) is common for every database and every type of query (beause of \textit{StarsProvider} interface).


\begin{lstlisting}[language=Python]
stars_prov = StarsProvider().getProvider(obtain_method = db_key,
                                        obtain_params = query)
stars = stars_prov.getStarsWithCurves()
\end{lstlisting}

\subsubsection*{StarsCatalogue}

Common abstract class for every database connector which provides \textit{Star} objects. Every inherited classes need to impelement method \textit{getStars}.

\subsubsection*{LightCurvesDb}

The \textit{LightCurvesDb} is common class for all connector classes to the databases which contain light curves data. It also inherit \textit{StarsCatalogue} abstract class. That means that these connectors provide \textit{Star} objects enchanted by \textit{LightCurve} attributes.

\subsubsection*{StarsProvider}

All database connectors are not accessed directly, but by this class. It reads from config file which contains keys and name of the database connector module in db$\_$tier package. That allows to call db connectors by keys (see above in example).

\subsubsection*{CrossmatchManager}
*NEED TO BE UPGRADED*

\subsubsection*{OGLEII}

Connector class for OGLEII database thru web interface

\subsubsection*{FileManager}

Manager for obtaining \textit{Star} objects from the light curve files

\subsubsection*{TapClient}

Common class for connectors to the databases via TAP protocol. The class can be accessed directly. In example below complete light curve of the star "MyStar1" is obtained in the database "http://my$\_$db.org/tap" from table "light$\_$curve$\_$table".

\begin{lstlisting}[language=Python]
tap_params = {
"URL" : "http://my_db.org/tap",
"table" : "light_curve_table",
"conditions" : ("ident1": "MyStar", "ident2": 1),
"select" : "*"}

lc = TapClient().postQuery(tap_params)
light_curve = LightCurve(lc)
\end{lstlisting}


\subsubsection*{MachoDb}
TODO: NEED TO BE UPGRADED

\subsection{conf}

The idea of conf files is about having all parameters in one place. The configuration file can be created like an ordinary text file in format $variable\_name = variable\_value$ per row or it can be created automatically by tools for estimating he most optional parameters. 

\subsection*{glo}
 Global parameters of the program. There are strucure and paths to the data folders (e.g. light curve folder of certain stars), verbosity level etc.
 
\subsubsection*{DefaultEstimator}

Estimator class which is used by \textit{ParamsEstimation} class (see below) by default. As all estimator classes it has to inherit methods of \textit{GridSearch} library also it has to implement \textit{fit} and \textit{score} methods. The first method learns to recognize input stars according to the input sample and the second one calculate precision of examined combination.

\subsubsection*{ParamsEstimation}

The class for calculating best filter parameters according to input sample of searched and undesired stars. It is also needed to specify combination of parameters for examing and the estimator (see above). In the following example \textit{AbbeValueFilter} is tested or more precisely is tested which of given values is the most optimal. The result is saved into the file and printed.

\begin{lstlisting}[language=Python]
tuned_params = [{"abbe_lim": 0.35},{"abbe_lim": 0.4}, {"abbe_lim": 0.45}]
es = ParamsEstimation(quasars, stars ,AbbeValueFilter , tuned_params)
es.fit()
\end{lstlisting}

\subsubsection*{filters params}

There are configuration files for certain projects (e.g. filters parameters for quasars searching) in this subpackage. 

\subsection{stars processing}

\subsection{utils}

\subsection*{data analysis}
Mainly there are functions for processing time series (e.g. calculate histogram, normalize, PAA etc.).

\subsubsection*{commons}

There are decorators for validating input/output of functions. Usage is shown in example below. 

TODO: NEED TO BE CHECKED
\begin{lstlisting}[language=Python]
class Foo(object):
	@mandatory_args(("param1"),("param2","param3","param4"))
	@default_values(param5 = 1, param6 = 11)
	@args_type(param1 = (list,), param2 = (str, int), param3 = (str, int, float), param4 = (str,float))
	def __init__(self,*args,**kwargs):
		...	
\end{lstlisting}

Every \textit{Foo} object has to be initialized with one or three parameters. In case of one it has to be list in case of three params - first has to be string or int etc. Also if $param5$ and $param6$ is not specified their value would be set by default decorator.

\subsubsection*{helpers}

There are support functions (e.g. progress bar)

\subsubsection*{output process modules}

Functions for serializing objects. Especially saving/loading them into/from the files. 

\subsubsection*{Stars}

Methods for managing lists of \textit{Star} objects. For instance \textit{get$\_$sorted$\_$stars} takes list of stars and returns the dictionary where keys are types of the stars (e.g. quasars, cepheids etc.) and its values are lists of the stars of the certain type.

Also there are methods for visualizing stars. 


\begin{figure}[H]
\centering
\includegraphics[scale=0.35]{figures/star_picture.png}
\caption{Output graph of \textit{plotStarsPicture} method}
\end{figure}


\subsection{stars processing}
 This package contains three subpackages:
\begin{itemize}
\item filters tools
	\begin{itemize}
	\item Support modules for particular filter implementations
	\end{itemize}
\item filters impl
	\begin{itemize}
	\item Star filters implementations
	\end{itemize}
\item systematic search
 \begin{itemize}
 \item Modules for systematic searching of databases and filtering its results
 \end{itemize}
\end{itemize}

\subsubsection*{BaseFilter}

Every filter has to inherit this class which ensures that every filter class has \textit{applyFilter} method.

\subsubsection*{•}

\section{Implementing new modules}
\subsection{Filters}
\subsection{Database connectors}




\end{document}
