"""
An observer doing logging of warnings, infos, errors, etc.

No synchronization takes place; it's probably not worth sweating this.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import logging
import os

from gavo import base
from gavo.base import ObserverBase, listensTo
from gavo.protocols.gavolog import RotatingFileHandler


class LoggingUI(ObserverBase):
	logLineFormat = "%(asctime)s [%(levelname)s %(process)s] %(message)s"

	def __init__(self, eh):
		ObserverBase.__init__(self, eh)
		errH = RotatingFileHandler(
			os.path.join(base.getConfig("logDir"), "dcErrors"),
			maxBytes=500000, backupCount=3, mode=0664)
		errH.setFormatter(
			logging.Formatter(self.logLineFormat))
		self.errorLogger = logging.getLogger("dcErrors")
		self.errorLogger.addHandler(errH)
		self.errorLogger.propagate = False

		infoH = RotatingFileHandler(
			os.path.join(base.getConfig("logDir"), "dcInfos"),
			maxBytes=500000, backupCount=1, mode=0664)
		infoH.setFormatter(logging.Formatter(self.logLineFormat))
		self.infoLogger = logging.getLogger("dcInfos")
		self.infoLogger.propagate = False
		self.infoLogger.addHandler(infoH)
		self.infoLogger.setLevel(logging.DEBUG)

	@listensTo("ExceptionMutation")
	def logOldException(self, res):
		if base.DEBUG:
			excInfo, newExc = res
			self.infoLogger.info("Swallowed the exception below, re-raising %s"%
				str(newExc), exc_info=excInfo)
	
	@listensTo("Info")
	def logInfo(self, message):
		self.infoLogger.info(message)
	
	@listensTo("Warning")
	def logWarning(self, message):
		self.infoLogger.warning(message)
	
	@listensTo("Error")
	def logError(self, message):
		self.errorLogger.error(str(message), exc_info=True)
