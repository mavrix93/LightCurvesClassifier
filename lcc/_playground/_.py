from lcc.db_tier.stars_provider import StarsProvider
from lcc.utils.stars import plotStarsPicture
from lcc.stars_processing.deciders.unsupervised.k_means_decider import KMeansDecider
from lcc.stars_processing.descriptors.position_descriptor import PositionDescriptor
from astropy.coordinates import SkyCoord
from astropy import units as u

coo = SkyCoord("4:41:56.22", "-66:51:59.1", unit=(u.hourangle, u.degree))
print coo
field = "LMC149.3"
starid = 8505
query = {"target": "all", "coo": coo}
stars = StarsProvider.getProvider(
    "OgleIII", query).getStars()
for st in stars:
    print st
