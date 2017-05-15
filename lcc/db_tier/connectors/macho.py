import collections

from lcc.db_tier.base_query import LightCurvesDb
from lcc.db_tier.vizier_tap_base import VizierTapBase


# TODO: Convert coo query from degrees to h:m:s, d:m:s
# NOTE: Please note that coordinates query is not available now
class Macho(VizierTapBase, LightCurvesDb):
    """
    Client for MACHO database of variable stars. It inherits `VizierTapBase` - see
    documentation of this class to class attributes description.

    EXAMPLES
    --------
    queries = [{"Field": 1 , "Tile": 3441, "Seqn": 25}]
    client = StarsProvider.getProvider(obtain_method="Macho",
                                       obtain_params=queries)
    stars = client.getStars()
    """

    TABLE = "II/247/machovar"
    LC_URL = "http://cdsarc.u-strasbg.fr/viz-bin/nph-Plot/w/Vgraph/txt?II%2f247%2f.%2f{macho_name}&F=b%2br&P={period}&-x&0&1&-y&-&-&-&--bitmap-size&600x400"

    NAME = "{Field}.{Tile}.{Seqn}"
    LC_FILE = ""

    LC_META = {"xlabel": "Time",
               "xlabel_unit": "MJD (JD-2400000.5)",
               "origin": "MACHO"}

    IDENT_MAP = {"Macho": ("Field", "Tile", "Seqn")}
    MORE_MAP = collections.OrderedDict((("Class", "var_type"),
                                        ("Vmag", "v_mag"),
                                        ("Rmag", "r_mag"),
                                        ("rPer", "period_r"),
                                        ("bPer", "period_b")))

    QUERY_OPTION = ["ra", "dec", "delta", "nearest", "Field", "Tile", "Seqn"]
