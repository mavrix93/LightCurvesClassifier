"""
Helper code for logging to files.

All logs that could be used both interactively and from the web server
but have group ownership gavo and mode (at least) 664.  Only then can
both parties write logs.

The RotatingFileHandler in this module tries to ensure this.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import grp
import os
import warnings
from logging import handlers

from gavo import base


try:
	GAVO_GROUP_ID = grp.getgrnam(base.getConfig("group"))[2]
except KeyError:
	warnings.warn("Cannot figure out id of group '%s'.  Logging will break.")
	GAVO_GROUP_ID = -1


class RotatingFileHandler(handlers.RotatingFileHandler):
	"""logging.handler.RotatingFile with forced group support.
	"""
	def __init__(self, *args, **kwargs):
		handlers.RotatingFileHandler.__init__(self, *args, **kwargs)
		self._setOwnership()
	
	def _setOwnership(self):
		# This will fail if we don't own the file.  This doesn't hurt as long
		# as whoever created the file already fixed the permission
		try:
			os.chmod(self.stream.name, 0664)
			os.chown(self.stream.name, -1, GAVO_GROUP_ID)
		except os.error: # don't worry, see above
			pass
	
	def doRollover(self):
		handlers.RotatingFileHandler.doRollover(self)
		self._setOwnership()
