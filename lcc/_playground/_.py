from lcc.db_tier.stars_provider import StarsProvider
from lcc.utils.stars import plotStarsPicture
from lcc.stars_processing.deciders.unsupervised.k_means_decider import KMeansDecider
from lcc.stars_processing.descriptors.position_descriptor import PositionDescriptor

ra = 11.091536 * 15
dec = -61.86248
p = "/home/martin/workspace/LightCurvesClassifier/data/project/inp_lcs/stars_fits"
#query = [{"starid": i + 1, "field": "SMC_SC1"} for i in range(1, 3)]
#query = {"ra": ra, "dec": dec, "delta": 15,  "db": "phot"}
query = {"path": p}
stars = StarsProvider.getProvider("FileManager", query).getStarsWithCurves()
for st in stars:
    print st.more.get("b_mag"), st.more.get("v_mag")