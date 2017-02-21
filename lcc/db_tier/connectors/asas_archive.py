import collections
import requests

from lcc.db_tier.base_query import LightCurvesDb
from lcc.db_tier.vizier_tap_base import VizierTapBase


class AsasArchive(VizierTapBase, LightCurvesDb):
    '''
    Asas archive of variable stars. It inherits `VizierTapBase` - see
    documentation of this class to class attributes description.

    As for all TAP queries it is possible to use "<" and ">" marks (for example
    {"Per":">2.5}).

    Example
    -------
    queries = [{"ASAS": "000030-3937.5"},
               {"ra": 0.4797, "dec": -67.1290, "delta": 10}]
    client = StarsProvider.getProvider(obtain_method="AsasArchive",
                                          obtain_params=queries)
    stars = client.getStarsWithCurves(do_per=True)
    '''

    TAP_URL = "http://tapvizier.u-strasbg.fr/TAPVizieR/tap"
    LC_URL = "http://cdsarc.u-strasbg.fr/viz-bin/nph-Plot/Vgraph/txt?II%2f264%2f.%2f{asas_id}&P=0"

    TABLE = "II/264/asas3"

    RA = "_RA"  # Deg
    DEC = "_DE"  # Deg
    NAME = "{ASAS}"

    LC_META = {"color": "V",
               "origin": "ASAS"}

    IDENT_MAP = {"asas": ("ASAS")}
    MORE_MAP = collections.OrderedDict((("Per", "period"),
                                        ("Class", "var_type"),
                                        ("Jmag", "j_mag"),
                                        ("Kmag", "k_mag"),
                                        ("Hmag", "h_mag"),
                                        ("LC", "lc_file")))

    def _getLightCurve(self, star, do_per=False, *args, **kwars):
        url = self.LC_URL.format(asas_id=star.name)
        if do_per:
            per = star.more.get("period", None)
            if per:
                url = url[:-1] + "%f" % per
                self.LC_META["xlabel"] = "Period"
                self.LC_META["xlabel_unit"] = "phase"

        response = requests.get(url)
        time = []
        mag = []
        err = []
        for line in response.iter_lines():
            line = line.strip()
            if not line.startswith((" ", "#")):
                parts = line.split(self.DELIM)
                if len(parts) == 3:
                    time.append(float(parts[self.TIME_COL]))
                    mag.append(float(parts[self.MAG_COL]))
                    err.append(float(parts[self.ERR_COL]) / self.ERR_MAG_RATIO)

        return time, mag, err
