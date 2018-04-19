from setuptools import setup, find_packages

setup(
  name='lcc',
  packages=find_packages(),
  version='1.2.2',
  description='Light Curves Classifier is package for classification stars by using their light curves and metadata',
  author='Martin Vo',
  author_email='mavrix@seznam.cz',
  url='https://github.com/mavrix93/LightCurvesClassifier',
  download_url='https://github.com/mavrix93/LightCurvesClassifier/archive/v1.0.0.tar.gz',
  install_requires=["numpy", "scipy", "matplotlib", "pandas", "scikit-learn",
                    "kplr", "astroML", "astropy", "requests", "bs4", "pathos", "tqdm", "keras",
                    "redis", "rq"],
  keywords=['light curves', 'machine-learning', 'astronomy', 'data-mining'],
  classifiers=[
    'Development Status :: 4 - Beta',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3.6'],
)

