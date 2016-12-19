
src.db_tier package
*******************


Subpackages
===========

* `src.db_tier.connectors package <Src.Db_Tier.Connectors>`_
  * `Submodules <Src.Db_Tier.Connectors#submodules>`_
  * `src.db_tier.connectors.asas_archive module
    <Src.Db_Tier.Connectors#module-src.db_tier.connectors.asas_archive>`_
  * `src.db_tier.connectors.corot_archive module
    <Src.Db_Tier.Connectors#module-src.db_tier.connectors.corot_archive>`_
  * `src.db_tier.connectors.file_manager module
    <Src.Db_Tier.Connectors#module-src.db_tier.connectors.file_manager>`_
  * `src.db_tier.connectors.kepler_archive module
    <Src.Db_Tier.Connectors#module-src.db_tier.connectors.kepler_archive>`_
  * `src.db_tier.connectors.macho_client module
    <Src.Db_Tier.Connectors#module-src.db_tier.connectors.macho_client>`_
  * `src.db_tier.connectors.ogle_client module
    <Src.Db_Tier.Connectors#module-src.db_tier.connectors.ogle_client>`_
  * `Module contents
    <Src.Db_Tier.Connectors#module-src.db_tier.connectors>`_

Submodules
==========


src.db_tier.TAP_query module
============================

**class src.db_tier.TAP_query.TapClient**

   Bases: ``src.db_tier.base_query.LightCurvesDb``

   Common class for all TAP db clients

   ``COO_UNIT_CONV``

      *int, float* -- Conversion rate of coordinates from degrees

   ``QUOTING``

      *list, tuple* -- Expressions with any of these symbols are
      quoted

   ``COO_UNIT_CONV = 1``

   ``QUOTING = [' ', '/', '_', '-', '.', '+']``

   **postQuery(tap_params)**

      Post query according to given parameters

      :Parameters:
         **tap_params** (*dict*) --

         Tap query parameters. It has to contains four keys.

         Dict keys:
            URL(str)
               Url of tap server

            table(str)
               Name of table for query

            select(str/list)
               Select string or list of column names

            conditions(list/tuple)
               For each condition in the list of conditions there is a
               tuple - ("name of column", "condition") or ("name of
               column", "lower value", "upper value" for search in the
               range

      :Returns:
         Result from the query as nested lists

      :Return type:
         list of lists


src.db_tier.base_query module
=============================

**class src.db_tier.base_query.LightCurvesDb**

   Bases: ``src.db_tier.base_query.StarsCatalogue``

   **getStarsWithCurves()**

      Query *Star* objects

      :Returns:
         List of *Star* objects appended by *LightCurve* instances

      :Return type:
         list

**class src.db_tier.base_query.StarsCatalogue**

   Bases: ``object``

   **coneSearch(coo, stars, delta_deg, nearest=False)**

      Filter results from cone search

      :Parameters:
         * **coo** (*astropy.coordinates.sky_coordinate.SkyCoord*) --
           Center of searching

         * **stars** (list of *Star* objects) -- Stars returned by
           query

         * **delta_deg** (*float**,
           **astropy.units.quantity.Quantity*) -- Radius from center
           of searching

         * **nearest** (*bool*) -- Nearest star to the center of
           searching is returned if it is True

      :Returns:
         List of *Star* objects

      :Return type:
         list

   **getStars()**

      Query *Star* objects

      :Returns:
         List of *Star* objects

      :Return type:
         list


src.db_tier.stars_provider module
=================================


src.db_tier.vizier_tap_base module
==================================

**class src.db_tier.vizier_tap_base.VizierTapBase(queries)**

   Bases: ``db_tier.TAP_query.TapClient``

   Base class for all tap connectors using VizieR database. In the
   most situations new connectors will contain just few class
   attributes and there will not be need to write new or overwrite
   current methods.

   ``TAP_URL``

      *str* -- Url to tap server

   ``FILES_URL``

      *str* -- Path to light curve files storage

   ``TABLE``

      *str* -- Name of querid table

   ``RA``

      *str* -- Name of right ascension column. It should be in
      degrees, anyway it is necessary to convert them

   ``DEC``

      *str* -- Name of declination column. It should be in degrees,
      anyway it is necessary to convert them

   ``NAME``

      *preformated str* -- Preformated string with dictionary keys.

      -[ EXAMPLE ]-

      "{Field}.{Tile}.{Seqn}"

      Keys represent name of columns

   ``LC_FILE``

      *str* -- Column name which can be used for obtaining light curve
      files. By default it is set to None that means that is not
      necessary to include any other column in order to get light
      curves

   ``LC_META``

      *dict* -- Meta data for light curve.

      -[ Example ]-

      {"xlabel" : "Terrestrial time",

      ..

         "xlabel_unit" : "days", "ylabel" : "Flux", "ylabel_unit" :
         "Electrons per second", "color" : "N/A", "invert_yaxis" :
         False}

      Light curve is expected by default (magnitudes and Julian days)

   ``TIME_COL``

      *int* -- Number (starts with 0) of times column in data file

   ``MAG_COL``

      *int* -- Number (starts with 0) of magnitudes column in data
      file

   ``ERR_COL``

      *int* -- Number (starts with 0) of errors column in data file

   ``ERR_MAG_RATIO``

      *float:* -- Ratio between error and magnitude values

      Note:
         Added because of Corot Archive of Faint Stars.

   ``IDENT_MAP``

      *ordered dict* -- Ordered dictionary of "name of database" :
      "column name/s of identifiers"

      -[ Example ]-

      IDENT_MAP = {"MachoDb" :  ("Field", "Tile", "Seqn") }

      This allows NAME attribute to access these keys (see above) and
      construct unique identifier for the star.

      For one item dictionaries can be used simple dictionary, because
      there is no need to keep order of items.

   ``MORE_MAP``

      *ordered dict* -- Ordered dictionary of "column names" : "key in
      new dictionary which is be stored in Star object"

      -[ Example ]-

      MORE_MAP = collections.OrderedDict((("Per", "period"),
         ("Class" , "var_type"), ("Jmag" , "j_mag"), ("Kmag" ,
         "k_mag"), ("Hmag" , "h_mag")))

   **This class inherits TapClient which brings methods for
   creating,**

   **posting and returning tap queries. Methods of this class manage**

   **results and create Star objects and light curves.**

   **There is no need overwrite methods in inherited classes in the
   most**

   **cases. Anyway obtaining light curves can be different for many**

   **databases. In this case it would be sufficient to just
   implement**

   **new _getLightCurve method.**

   **Brief description of methods can be found below at their
   declaration.**

   ``DEC = 'DEJ2000'``

   ``DELIM = None``

   ``ERR_COL = 2``

   ``ERR_MAG_RATIO = 1.0``

   ``LC_FILE = None``

   ``MAG_COL = 1``

   ``RA = 'RAJ2000'``

   ``TAP_URL = 'http://tapvizier.u-strasbg.fr/TAPVizieR/tap'``

   ``TIME_COL = 0``

   **getStars(lc=False, **kwargs)**

      Get star objects

      :Parameters:
         **lc** (*bool*) -- Star is appended by light curve if True

      :Returns:
         List of stars

      :Return type:
         list

   **getStarsWithCurves(**kwargs)**

      Get star objects with light curves

      :Parameters:
         **kwargs** (*dict*) --

         Optional parameters which have effect just if certain
         database provides this option.

         For example CoRoT archive contains very large light curves,
         so the dimension of light curve can be reduced by *max_bins*
         keyword.

      :Returns:
         List of stars with their light curves

      :Return type:
         list


Module contents
===============
