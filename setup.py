
from distutils.core import setup
import pkgutil

def getPackages(path="."):
    p = set()
    for importer, modname, ispkg in pkgutil.walk_packages(path=path, onerror=lambda x: None):
	if "." in modname:
	    p.add( modname[:modname.rfind(".")] )
    return p

setup(
  name = 'lcc',
  packages = getPackages(), # this must be the same as the name above
  version = '0.9.1',
  description = 'Light Curves Classifier is package for classification stars by using their light curves and metadata',
  author = 'Martin Vo',
  author_email = 'mavrix@seznam.cz',
  url = 'https://github.com/mavrix93/LightCurvesClassifier', # use the URL to the github repo
  download_url = 'https://github.com/mavrix93/LightCurvesClassifier/archive/0.1.tar.gz', # I'll explain this in a second
  keywords = ['light curves', 'classifying', 'machine-learning', 'astronomy', 'data-mining'],
  classifiers = [],
)

