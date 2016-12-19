
src.db_tier.connectors package
******************************


Submodules
==========


src.db_tier.connectors.asas_archive module
==========================================

**class src.db_tier.connectors.asas_archive.AsasArchive(queries)**

..

   Bases: ``db_tier.vizier_tap_base.VizierTapBase``,
   ``db_tier.base_query.LightCurvesDb``

   Asas archive of variable stars. It inherits *VizierTapBase* - see
   documentation of this class to class attributes description.

   -[ Example ]-

   queries = [{"ASAS": "000030-3937.5"},
      {"ra": 0.4797, "dec": -67.1290, "delta": 10}]

   client = StarsProvider.getProvider(obtain_method="AsasArchive",
      obtain_params=queries)

   stars = client.getStarsWithCurves(do_per=True)

   ``DEC = '_DE'``

   ``IDENT_MAP = {'asas': 'ASAS'}``

   ``LC_META = {'color': 'V', 'origin': 'ASAS'}``

   ``LC_URL = 'http://cdsarc.u-str ... 64%2f.%2f{asas_id}&P=0'``

   ``MORE_MAP = OrderedDict([('Per', ... '), ('LC', 'lc_file')])``

   ``NAME = '{ASAS}'``

   ``RA = '_RA'``

   ``TABLE = 'II/264/asas3'``

   ``TAP_URL = 'http://tapvizier.u-strasbg.fr/TAPVizieR/tap'``


src.db_tier.connectors.corot_archive module
===========================================

**class
src.db_tier.connectors.corot_archive.CorotBrightArchive(queries)**

..

   Bases: ``db_tier.vizier_tap_base.VizierTapBase``,
   ``db_tier.base_query.LightCurvesDb``

   CoRoT connector. TAP query and downloading of the light curve fits
   are executed on Vizier catalog. It inherits *VizierTapBase* - see
   documentation of this class to class attributes description.

   -[ EXAMPLES ]-

   queries = [{"ra": 102.707, "dec": -0.54089, "delta": 10},
      {"CoRot": 116}]

   client =
   StarsProvider.getProvider(obtain_method="CorotBrightArchive",

   ..

      obtain_params=queries)

   stars = client.getStarsWithCurves(max_bins=10000)

   ``IDENT_MAP = OrderedDict([('Vizie ... ghtArchive', 'CoRoT')])``

   ``LC_FILE = 'FileName'``

   ``LC_META = {'origin': 'CoRoT',  ... ime', 'ylabel': 'Flux'}``

   ``LC_URL = 'http://vizier.u-str ... us=-%2b&B/corot/files/'``

   ``MORE_MAP = OrderedDict([('(B-V) ... g'), ('Teff', 'temp')])``

   ``NAME = '{Star}'``

   ``TABLE = 'B/corot/Bright_star'``

**class
src.db_tier.connectors.corot_archive.CorotFaintArchive(queries)**

..

   Bases: ``src.db_tier.connectors.corot_archive.CorotBrightArchive``

   Corot archive of faint stars

   -[ Examples ]-

   queries = [ { "Corot" : "102706554"},
      {"ra": 100.94235, "dec" : -00.89651, "delta" : 10}]

   client = StarsProvider().getProvider( obtain_method =
   "CorotFaintArchive", obtain_params = queries) stars =
   client.getStarsWithCurves(max_bins = 10000 )

   ``ERR_COL = 5``

   ``ERR_MAG_RATIO = 16.0``

   ``IDENT_MAP = {'CorotFaintArchive': 'CoRoT'}``

   ``LC_META = {'ylabel_unit': 'Ele ... ime', 'ylabel': 'Flux'}``

   ``MAG_COL = 4``

   ``MORE_MAP = OrderedDict([('SpT', ... ), ('Gmean', 'g_mag')])``

   ``NAME = 'CoRoT'``

   ``TABLE = 'B/corot/Faint_star'``

   ``TIME_COL = 2``


src.db_tier.connectors.file_manager module
==========================================

**class src.db_tier.connectors.file_manager.FileManager(*args,
**kwargs)**

..

   Bases: ``db_tier.base_query.LightCurvesDb``

   This class is responsible for managing light curve files

   ``path``

   ..

      *str* -- Path key of folder of light curves registered in
      settings. If path starts with "HERE:" such as
      "HERE:path/to/the/folder", relative path is taken.

   ``star_class``

   ..

      *str* -- Name of the loaded star-like type (e.g. Cepheids)

   ``suffix``

   ..

      *str* -- Suffix of light curve files in the folder. If suffix is
      "fits", files are loaded as fits files, otherwise files are
      considered as .dat files of light curve such as:

      ..

         #time    mag    err 12    13.45    0.38

   ``files_limit``

   ..

      *int, str* -- Number of files which will be loaded

   ``db_ident``

   ..

      *str* -- Name of the database to which the file name will be
      assigned

      EXAMPLE:
         For the file "my_macho_star.dat" and given db_ident as
         "macho" makes Star object:

         star.ident["macho"] --> my_macho_star

   ``files_to_load``

   ..

      *iterable of str* -- List of file names which should be loaded
      from the given folder. If it is not specified all files will be
      loaded

   ``object_file_name``

   ..

      *str* -- Name of the pickle file which contains list of star
      objects

   ``DB_ORIGIN = 'DB_ORIGIN'``

   ``DEFAULT_STARCLASS = 'star'``

   ``DEFAULT_SUFFIX = 'dat'``

   ``FITS_CLASS = 'CLASS'``

   ``FITS_DEC = 'DEC'``

   ``FITS_DEC_UNIT = 'DEC_UN'``

   ``FITS_NAME = 'IDENT'``

   ``FITS_RA = 'RA'``

   ``FITS_RA_UNIT = 'RA_UN'``

   ``FITS_SUFFIX = ('fits', 'FITS')``

   ``REL_PATH = 'HERE:'``

   **getStarsWithCurves()**

   ..

      Common method for all stars provider

      If there are object_file_name in query dictionary, the object
      file of list of stars is loaded. In other case files from given
      path of the folder is loaded into star objects.

      :Returns:
         Star objects with light curves

      :Return type:
         list of *Star* objects

   ``static parseFileName(file_path)``

   ..

      Return cleaned name of the star without path and suffix

   ``classmethod writeToFITS(file_name, star, clobber=True)``


src.db_tier.connectors.kepler_archive module
============================================

**class
src.db_tier.connectors.kepler_archive.KeplerArchive(obtain_params)**

..

   Bases: ``db_tier.base_query.LightCurvesDb``

   This is connector to Kepler archive of light curves using kplr
   package

   -[ EXAMPLE ]-

   queries = [{"ra": 297.8399, "dec": 46.57427, "delta": 10},
      {"kic_num": 9787239}, {"kic_jkcolor": (0.3, 0.4), "max_records":
      5}]

   client = StarsProvider().getProvider(obtain_method="KeplerArchive",
      obtain_params=queries)

   stars = client.getStarsWithCurves()

   ``DEC_IDENT = 'kic_dec'``

   ``IDENTIFIER = {'kic_2mass_id': '2mass', '_name': 'kepler'}``

   ``LC_META = {'origin': 'Kepler', ... IME', 'ylabel': 'Flux'}``

   ``NAME = '_name'``

   ``RA_IDENT = 'kic_degree_ra'``

   ``STAR_MORE_MAP = {'kic_gmag': 'g_mag' ... ', 'kic_jmag':
   'j_mag'}``

   **getStars(lc=False)**

   ..

      :Returns:
         List of Star objects according to queries

      :Return type:
         list of *Star* objects

   **getStarsWithCurves()**

   ..

      :Returns:
         List of Star objects with light curves according to queries

      :Return type:
         list of *Star* objects


src.db_tier.connectors.macho_client module
==========================================

**class src.db_tier.connectors.macho_client.MachoDb(queries)**

..

   Bases: ``db_tier.vizier_tap_base.VizierTapBase``,
   ``db_tier.base_query.LightCurvesDb``

   Client for MACHO database. It inherits *VizierTapBase* - see
   documentation of this class to class attributes description.

   -[ EXAMPLES ]-

   queries = [{"Field": 1 , "Tile": 3441, "Seqn": 25}] client =
   StarsProvider.getProvider(obtain_method="MachoDb",

   ..

      obtain_params=queries)

   stars = client.getStarsWithCurves()

   ``IDENT_MAP = {'MachoDb': ('Field', 'Tile', 'Seqn')}``

   ``LC_FILE = ''``

   ``LC_META = {'xlabel_unit': 'MJD ... CHO', 'xlabel': 'Time'}``

   ``LC_URL = 'http://cdsarc.u-str ... &--bitmap-size&600x400'``

   ``MORE_MAP = OrderedDict([('Class ...  ('bPer', 'period_b')])``

   ``NAME = '{Field}.{Tile}.{Seqn}'``

   ``TABLE = 'II/247/machovar'``


src.db_tier.connectors.ogle_client module
=========================================

**class src.db_tier.connectors.ogle_client.OgleII(queries)**

..

   Bases: ``db_tier.base_query.LightCurvesDb``

   OgleII class is responsible for searching stars in OGLE db
   according to query. Then it can download light curves and saved
   them or retrieve stars object (with lc, coordinates, name...)

   ``LC_META = {'origin': 'OgleII', ...  'ylabel': 'magnitude'}``

   ``MAX_REPETITIONS = 3``

   ``MAX_TIMEOUT = 60``

   ``QUERY_TYPE = 'bvi'``

   ``ROOT = 'http://ogledb.astrouw.edu.pl/~ogle/photdb'``

   ``TARGETS = ['lmc', 'smc', 'bul', 'sco']``

   **getStars()**

   ..

      Get Star objects

   **getStarsWithCurves()**

   ..

      Get Star objects with light curves

   **oneQuery(query)**


Module contents
===============
