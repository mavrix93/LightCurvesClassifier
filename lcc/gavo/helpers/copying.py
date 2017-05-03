"""
Helpers for pulling data from CDs, DVDs and similar media.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import fcntl
import os
import shutil
import subprocess
import sys
import time

from gavo import base
from gavo.user import ui  #noflake: Need side effect

CTL_CD_EJECT = 0x5309
CTL_CD_QCHANGE = 0x5325


class CDHandler(object):
	"""A wrapper for mounting and ejecting CDs.

	This assumes that you let users mount CDs, e.g. via a line like

	/dev/scd0       /media/cdrom0   udf,iso9660 user,noauto     0       0

	in /etc/fstab.  In this example, devPath would be /dev/scd0 and
	mountPath /media/cdrom0.
	"""
	def __init__(self, devPath, mountPath):
		self.devPath, self.mountPath = devPath, mountPath

	def ejectMedium(self):
		"""ejects the current CD.
		"""
		cd = os.open(self.devPath, os.O_RDONLY|os.O_NONBLOCK)
		try:
			fcntl.ioctl(cd, CTL_CD_EJECT)
		finally:
			if cd>=0:
				os.close(cd)
	
	def mediumChanged(self):
		"""returns True if there's a new medium available.
		"""
		cd = os.open(self.devPath, os.O_RDONLY|os.O_NONBLOCK)
		try:
			if cd<0:
				return False
			else:
				return fcntl.ioctl(cd,  CTL_CD_QCHANGE, 0)==0
		finally:
			if cd>=0:
				os.close(cd)

	def mount(self):
		subprocess.check_call(["mount", self.mountPath])
	
	def unmount(self):
		subprocess.check_call(["umount", self.devPath])

	def isMounted(self):
		f = open("/proc/mounts")
		stuff = f.read()
		f.close()
		return self.mountPath in stuff


def _getCurMax(destBase):
	"""returns the highest index of ??\d+-formed names in destBase.
	"""
	def brutalInt(val):
		try:
			return int(val)
		except ValueError:
			return 0
	try:
		return max([brutalInt(n[2:]) for n in os.listdir(destBase)]+[0])
	except IOError:
		return 0


def changeCD(cdHandler):
	if cdHandler.isMounted():
		cdHandler.unmount()
	cdHandler.ejectMedium()
	sys.stdout.write("Waiting for Medium")
	sys.stdout.flush()
	while not cdHandler.mediumChanged():
		time.sleep(1)
		sys.stdout.write(".")
		sys.stdout.flush()


def readCDs(destBase, cdHandler):
	"""runs a crude UI to read CDs in batch.

	The idea is that you get a copy-in script by writing something like
	
	import os
	from gavo import api

	rd = api.getRD("foo/bar")
	cd = CDHandler("/dev/cdrom", "mnt/cd")
	copying.readCDs(os.path.join(rd.resdir, "raw"), cd)
	"""
	if not os.path.exists(destBase):
		os.mkdir(destBase)
		srcCount = 0
	else:
		srcCount = _getCurMax(destBase)+1

	while 1:
		changeCD(cdHandler)
		dest = os.path.join(destBase, "cd%03d"%srcCount)
		print "Now writing to", dest
		try:
			cdHandler.mount()
			shutil.copytree(cdHandler.mountPath, dest)
		except (subprocess.CalledProcessError, shutil.Error, KeyboardInterrupt):
			base.ui.notifyError("Copying failed or interrupted."
				"  Removing destination %s. Try again.")%dest
			if os.path.exists(dest):
				shutil.rmtree(dest)
			sys.exit(1)
		srcCount += 1
