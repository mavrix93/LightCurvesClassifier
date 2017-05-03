"""
Code to obtain WCS headers for FITS files using astrometry.net

Astrometry.net has oodles of configurable parameters.  Some of
them can be passed in via the solverParameters argument to getWCSFieldsFor,
a dictionary with keys including:

indices
  (default: "index-\*.fits", meaning all indices in your default index dir)
  The file names from anet's index directory you want to have used.
  glob patterns are expanded, but no recursion takes place.

  This could be something like::
  
    ["index-4211.fits", "index-4210.fits", "index-4209.fits"]
  
  for largeish images or::

    ["index-4203-\*.fits", "index-4202-*.fits"]
  
  for small ones.  You can also give absolute path names for custom
  indices that live, e.g., in your resource directory.

total_timelimit
  (defaults to 600) -- number of seconds after which the anet run
  should cancel itself.

tweak
  (defaults to True) -- try to obtain a polynomic correction to the
  entire image after obtaining a solution?  This can go wrong in
  particular for exposures with many objects, so you might want to 
  set it to off for such cases.

fields
  (default to 1) -- FITS extension to work on

endob
  (defaults to not given) -- last object to be processed.  You don't want to
  raise this too high.  The library will only pass on 10 objects at a
  time anyway, but going too high here will waste lots of time on images
  that are probably not going to resolve anyway.

lower_pix
  (defaults to not given) -- smallest permissible pixel size in arcsecs.  If
  at all possible, constrain this for much better results.
  
upper_pix
  (defaults to not given) -- largest permissible pixel size in arcsecs.
  See lower_pix.

plots
	(defaults to False) -- generate all kinds of pretty plots?

downsample
	(defaults to not given) -- factor to downsample the image before
	trying to solve.  This may be necessary when not using sextractor,
	and it should be something like 2, 3, or 4.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from __future__ import with_statement

import glob
import gzip
import os
import shutil
import subprocess

from gavo import base
from gavo import utils
from gavo.utils import fitstools
from gavo.utils import codetricks
from gavo.utils import pyfits

__docformat__ = "restructuredtext en"

anetPath = "/usr/local/astrometry/bin"
anetIndexPath = "/usr/local/astrometry/data"
solverBin = os.path.join(anetPath, "solve-field")
sextractorBin = "sextractor"


PARAM_DEFAULTS = {
		"total_timelimit": 600,
		"fields": "1",
		"endob": None,
		"lower_pix": None,
		"upper_pix": None,
		"tweak": True,
		"pix_units": "app",
		"plots": False,
		"downsample": None,
	}


class Error(base.Error):
	pass

class NotSolved(Error):
	pass

class ObjectNotFound(Error):
	pass

class ShellCommandFailed(Error):
	def __init__(self, msg, retcode):
		Error.__init__(self, msg)
		self.msg, self.retcode = msg, retcode
	
	def __str__(self):
		return "External program failure (%s).  Program output: %s"%(
			self.retcode, self.msg)


def _feedFile(targDir, fName, **ignored):
	"""links fName to "in.fits" in the sandbox.

	If fName ends with .gz, the function assumes it's a gzipped file and
	unzips it to in.fits instead.
	"""
	srcName = os.path.join(os.getcwd(), fName)
	destName = os.path.join(targDir, "img.fits")
	if fName.endswith(".gz"):
		with open(destName, "w") as destF:
			utils.cat(gzip.open(srcName), destF)
	else:
		os.symlink(srcName, destName)


def _runShellCommand(cmd, args):
	with open("lastCommand.log", "a") as logF:
		logF.write("\n\n================\nNow running: %s\n\n"%
			" ".join([cmd]+args))
		logF.flush()
		proc = subprocess.Popen([cmd]+args, stdout=logF,
			stderr=subprocess.STDOUT)
		proc.communicate()
	if proc.returncode==-2:
		raise KeyboardInterrupt("Child was siginted")
	elif proc.returncode:
		raise ShellCommandFailed(open("lastCommand.log").read(), proc.returncode)


def _copyCurrentTree(copyTo):
	if copyTo is not None:
		try:
			shutil.rmtree(copyTo)
		except os.error:
			pass
		shutil.copytree(".", copyTo)


# Minimal configuration for sextractor for anet use.
# Do not override values in here in your sexConfigs
_ANET_SEX_STUB = """# sextractor control file for astrometry.net
CATALOG_TYPE     FITS_1.0
# The output file name
CATALOG_NAME     img.axy
# The name of the file containing _ANET_SEX_PARAM
PARAMETERS_NAME  anet.param
FILTER_NAME anet.filter
"""

# export column spec for sextractor; referenced in _ANET_SEX_STUB
_ANET_SEX_PARAM = """X_IMAGE
Y_IMAGE
MAG_ISO
FLUX_AUTO
ELONGATION
"""

# Blatantly stolen from anet...
_ANET_SEX_FILTER = """CONV NORM
# 5x5 convolution mask of a gaussian PSF with FWHM = 2.0 pixels.
0.006319 0.040599 0.075183 0.040599 0.006319
0.040599 0.260856 0.483068 0.260856 0.040599
0.075183 0.483068 0.894573 0.483068 0.075183
0.040599 0.260856 0.483068 0.260856 0.040599
0.006319 0.040599 0.075183 0.040599 0.006319
"""


def _createSextractorFiles(sexControl):
	with open("anet.control", "w") as f:
		f.write(_ANET_SEX_STUB+sexControl)
	with open("anet.param", "w") as f:
		f.write(_ANET_SEX_PARAM)
	with open("anet.filter", "w") as f:
		f.write(_ANET_SEX_FILTER)


def _extractSex(filterFunc=None):
	"""does source extraction using Sextractor.

	If filterFunc is not None, it is called before sorting the extracted
	objects. It must change the file named in the argument in place.
	"""
	_runShellCommand(sextractorBin, ["-c", "anet.control", "img.fits"])
	if filterFunc is not None:
		filterFunc("img.axy")


_PARAMETER_MAP = [
	("total_timelimit", "--cpulimit"),
	("fields", "--fields"),
	("lower_pix", "--scale-low"),
	("upper_pix", "--scale-high"),
	("pix_units", "--scale-units"),
	("endob", "--depth"),
	("downsample", "--downsample"),
]
	
def _addArgsFor(actPars, args):
	if not actPars["tweak"]:
		args.append("--no-tweak")
	if not actPars["plots"]:
		args.append("--no-plots")
	for key, opthead in _PARAMETER_MAP:
		if actPars[key] is not None:
			args.extend([opthead, str(actPars[key])])


def _solveField(fName, solverParameters, sexControl, objectFilter,
		verbose):
	"""tries to solve an image anet's using solve-field.

	See _resolve for the meaning of the arguments.
	"""
	args = ["--continue"]
	objectSource = "img.fits"
	if sexControl is not None:
		_createSextractorFiles(sexControl)
		if sexControl==None:
			pass
		elif sexControl=="":
			args.extend(["--use-sextractor", "--sextractor-path", sextractorBin])
		else:
			_extractSex(objectFilter)
			width, height = fitstools.getPrimarySize("img.fits")
			args.extend(["--x-column", "X_IMAGE", 
				"--y-column", "Y_IMAGE",
				"--sort-column", "FLUX_AUTO",
				"--use-sextractor",
				"--width", str(width), "--height", str(height)])
			objectSource = "img.axy"
#	args.append("--no-fits2fits") # leaks into tmp as of 0.36 otherwise
	args.append("-v")

	if "indices" in solverParameters:
		with open("backend.cfg", "w") as backendCfg:
			for indF in solverParameters["indices"]:
				fullPath = os.path.join(anetIndexPath, indF)
				for fName in glob.glob(fullPath):
					backendCfg.write("index %s\n"%fName)
			backendCfg.write("inparallel")
		args.extend(["--backend-config", "backend.cfg"])


	actPars = PARAM_DEFAULTS.copy()
	actPars.update(solverParameters)
	_addArgsFor(actPars, args)

	args.append(objectSource)
	if verbose:
		print "Running %s %s"%(solverBin, " ".join(args))
	_runShellCommand(solverBin, args)

# staggered solving: This seemed like a good idea at some point but
# now probably no longer is.
#	minInd, maxInd = int(actPars["startob"]), int(actPars["endob"])
#	curStart = minInd
#	while True:
#		if curStart+10>maxInd:
#			break
#		args.extend(["--depth", "%s-%s"%(curStart+1, curStart+15), "img.fits"])
#		_runShellCommand(solverBin, args)
#		if os.path.exists("img.solved"):
#			break
#		curStart += 5
#		args[-3:] = []


def _resolve(fName, solverParameters={}, sexControl=None, objectFilter=None,
		copyTo=None, verbose=False):
	"""runs the astrometric calibration pipeline.

	solverParameters is a dictionary; most keys in it are simply turned
	into command line options of solve-field.

	This function litters the working directory with all kinds of files and does
	not clean up, so you'd better run it in a sandbox.

	It raises a NotSolved exception if no solution could be found; otherwise
	you should find the solution in img.wcs.
	"""
	try:
		_solveField(fName, solverParameters, sexControl, objectFilter, verbose)
	except Exception:
		_copyCurrentTree(copyTo)
		raise
	_copyCurrentTree(copyTo)
	if os.path.exists("img.solved"):
		return
	raise NotSolved(fName)


def _retrieveWCS(srcDir, fName, **ignored):
	return pyfits.getheader("img.wcs").ascard


def getWCSFieldsFor(fName, solverParameters, sexControl=None, objectFilter=None,
		copyTo=None, verbose=False):
	"""returns a pyfits cardlist for the WCS fields on fName.

	solverParameters is a dictionary mapping solver keys to their values,
	sexScript is a script for SExtractor, and its presence means that
	SExtractor should be used for source extraction rather than what anet
	has built in.  objectFilter is a function that is called with the
	name of the FITS with the extracted sources.  It can remove or add
	sources to that file before astrometry.net tries to match.

	To see what solverParameters  are avaliable, check the module docstring.
	"""
	try:
		res = codetricks.runInSandbox(_feedFile, _resolve, _retrieveWCS,
			fName, solverParameters=solverParameters, sexControl=sexControl,
			objectFilter=objectFilter, copyTo=copyTo, verbose=verbose)
	except NotSolved:
		return None
	return res
