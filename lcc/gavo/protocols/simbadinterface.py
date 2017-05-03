"""
A caching proxy for CDS' Simbad object resolver.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import cPickle
import os
import socket
import tempfile
import urllib
import warnings

from gavo import base
from gavo import utils
from gavo.utils import ElementTree


class ObjectCache(object):
	def __init__(self, id):
		self.id = id
		self._loadCache()

	def _getCacheName(self):
		return os.path.join(base.getConfig("cacheDir"), "oc"+self.id)

	def _loadCache(self):
		try:
			self.cache = cPickle.load(open(self._getCacheName()))
		except IOError:
			self.cache = {}
	
	def _saveCache(self, silent=False):
		try:
			handle, name = tempfile.mkstemp(dir=base.getConfig("cacheDir"))
			f = os.fdopen(handle, "w")
			cPickle.dump(self.cache, f)
			utils.safeclose(f)
			os.rename(name, self._getCacheName())
		except (IOError, os.error):
			if not silent:
				raise

	def addItem(self, key, record, save, silent=False):
		self.cache[key] = record
		if save:
			self._saveCache(silent)
	
	def sync(self):
		self._saveCache(silent=True)
	
	def getItem(self, key):
		return self.cache[key]


class Sesame(object):
	"""is a simple interface to the simbad name resolver.
	"""
	SVC_URL = "http://cdsweb.u-strasbg.fr/cgi-bin/nph-sesame/-ox/SN?"

	def __init__(self, id="simbad", debug=False, saveNew=False):
		self.saveNew = saveNew
		self.debug = debug
		self._getCache(id)

	def _getCache(self, id):
		self.cache = ObjectCache(id)

	def _parseXML(self, simbadXML):
		try:
			et = ElementTree.fromstring(simbadXML)
		except Exception, msg: # simbad returned weird XML
			warnings.warn("Bad XML from simbad (%s)"%str(msg))
			return None
	
		res = {}
		nameMatch = et.find("Target/name")
		if nameMatch is None:
			# no such object, return a negative
			return None

		res["oname"] = nameMatch.text
		firstResponse = et.find("Target/Resolver")
		if not firstResponse:
			return None

		res["otype"] = getattr(firstResponse.find("otype"), "text", None)
		try:
			res["RA"] = float(firstResponse.find("jradeg").text)
			res["dec"] = float(firstResponse.find("jdedeg").text)
		except ValueError:
			# presumably null position
			return None
		return res

	def query(self, ident):
		try:
			return self.cache.getItem(ident)
		except KeyError:
			try:
				f = urllib.urlopen(self.SVC_URL+urllib.quote(ident))
				response = f.read()
				f.close()

				newOb = self._parseXML(response)
				self.cache.addItem(ident, newOb, save=self.saveNew)
				return newOb
			except socket.error: # Simbad is offline
				raise base.ui.logOldExc(base.ValidationError(
					"Simbad is offline, cannot query.",
					"hscs_pos", # really, this should be added by the widget
					hint="If this problem persists, complain to us rather than simbad."))
	
	def getPositionFor(self, identifier):
		data = self.query(identifier)
		if not data:
			raise KeyError(identifier)
		return float(data["RA"]), float(data["dec"])
	

def getSimbadPositions(identifier):
	"""returns ra and dec from Simbad for identifier.

	It raises a KeyError if Simbad doesn't know identifier.
	"""
	return base.caches.getSesame("simbad").getPositionFor(identifier)


base.caches.makeCache("getSesame", lambda key: Sesame(key, saveNew=True))


if __name__=="__main__":
	s = Sesame(debug=True)
	print s.query("M 33")
