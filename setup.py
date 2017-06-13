import pkgutil
import os
from setuptools import setup, find_packages

setup(
  name = 'lcc',
  packages = find_packages(),
  version = '1.0.5',
  description = 'Light Curves Classifier is package for classification stars by using their light curves and metadata',
  author = 'Martin Vo',
  author_email = 'mavrix@seznam.cz',
  url = 'https://github.com/mavrix93/LightCurvesClassifier', 
  download_url = 'https://github.com/mavrix93/LightCurvesClassifier/archive/v1.0.0.tar.gz', 
  install_requires = ["numpy", "scipy", "matplotlib", "pandas", "PyBrain", "pyfits", "scikit-learn", "kplr", "astroML", "astropy", "requests", "bs4", "pathos"],
  keywords = ['light curves', 'classifying', 'machine-learning', 'astronomy', 'data-mining'],
  classifiers = [],
)

