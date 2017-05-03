"""
OS abstractions and related.
"""

#c Copyright 2008-2016, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import contextlib
import os
import tempfile
import urllib2

from . import codetricks
from . import misctricks


def safeclose(f):
	"""syncs and closes the python file f.

	You generally want to use this rather than a plain close() before
	overwriting a file with a new version.
	"""
	f.flush()
	os.fsync(f.fileno())
	f.close()


@contextlib.contextmanager
def safeReplaced(fName):
	"""opens fName for "safe replacement".

	Safe replacement means that you can write to the object returned, and
	when everything works out all right, what you have written replaces
	the old content of fName, where the old mode is preserved if possible.  
	When there are errors, however, the old content remains.
	"""
	targetDir = os.path.abspath(os.path.dirname(fName))
	try:
		oldMode = os.stat(fName)[0]
	except os.error:
		oldMode = None

	handle, tempName = tempfile.mkstemp(".temp", "", dir=targetDir)
	targetFile = os.fdopen(handle, "w")

	try:
		yield targetFile
	except:
		try:
			os.unlink(tempName)
		except os.error:
			pass
		raise

	else:
		safeclose(targetFile)
		os.rename(tempName, fName)
		if oldMode is not None:
			try:
				os.chmod(fName, oldMode)
			except os.error:
				pass


class _UrlopenRemotePasswordMgr(urllib2.HTTPPasswordMgr):
	"""A password manager that grabs credentials from upwards in
	its call stack.

	This is for cooperation with urlopenRemote, which defines a name
	_temp_credentials.  If this is non-None, it's supposed to be
	a pair of user password presented to *any* realm.  This means
	that, at least with http basic auth, password stealing is
	almost trivial.
	"""
	def find_user_password(self, realm, authuri):
		creds = codetricks.stealVar("_temp_credentials")
		if creds is not None:
			return creds


_restrictedURLOpener = urllib2.OpenerDirector()
_restrictedURLOpener.add_handler(urllib2.HTTPRedirectHandler())
_restrictedURLOpener.add_handler(urllib2.HTTPHandler())
_restrictedURLOpener.add_handler(urllib2.HTTPSHandler())
_restrictedURLOpener.add_handler(urllib2.HTTPErrorProcessor())
_restrictedURLOpener.add_handler(
	urllib2.HTTPBasicAuthHandler(_UrlopenRemotePasswordMgr()))
_restrictedURLOpener.add_handler(urllib2.FTPHandler())
_restrictedURLOpener.add_handler(urllib2.UnknownHandler())
_restrictedURLOpener.addheaders = [("user-agent", 
	"GAVO DaCHS HTTP client")]

def urlopenRemote(url, data=None, creds=(None, None)):
	"""works like urllib2.urlopen, except only http, https, and ftp URLs
	are handled.

	The function also massages the error messages of urllib2 a bit.  urllib2
	errors always become IOErrors (which is more convenient within the DC).

	creds may be a pair of username and password.  Those credentials
	will be presented in http basic authentication to any server
	that cares to ask.  For both reasons, don't use any valuable credentials
	here.
	"""
	# The name in the next line is used in _UrlopenRemotePasswrodMgr
	_temp_credentials = creds #noflake: Picked up from down the call chain
	try:
		res = _restrictedURLOpener.open(url, data)
		if res is None:
			raise IOError("Could not open URL %s -- does the resource exist?"%
				url)
		return res
	except (urllib2.URLError, ValueError), msg:
		msgStr = str(msg)
		try:
			msgStr = msg.args[0]
			if isinstance(msgStr, Exception):
				try:  # maybe it's an os/socket type error
					msgStr = msgStr.args[1]
				except IndexError:  # maybe not...
					pass
			if not isinstance(msgStr, basestring):
				msgStr = str(msg)
		except:
			# there's going to be an error message, albeit maybe a weird one
			pass
		raise IOError("Could not open URL %s: %s"%(url, msgStr))


def fgetmtime(fileobj):
	"""returns the mtime of the file below fileobj.

	This raises an os.error if that file cannot be fstated.
	"""
	try:
		return os.fstat(fileobj.fileno()).st_mtime
	except AttributeError:
		raise misctricks.logOldExc(os.error("Not a file: %s"%repr(fileobj)))


def cat(srcF, destF, chunkSize=1<<20):
	"""reads srcF into destF in chunks.
	"""
	while True:
		data = srcF.read(chunkSize)
		if not data:
			break
		destF.write(data)


def ensureDir(dirPath, mode=None, setGroupTo=None):
	"""makes sure that dirPath exists and is a directory.

	If dirPath does not exist, it is created, and its permissions are
	set to mode with group ownership setGroupTo if those are given.

	setGroupTo must be a numerical gid if given.

	This function may raise all kinds of os.errors if something goes
	wrong.  These probably should be handed through all the way to the
	user since when something fails here, there's usually little
	the program can safely do to recover.
	"""
	if os.path.exists(dirPath):
		return
	os.mkdir(dirPath)
	if mode is not None:
		os.chmod(dirPath, mode)
	if setGroupTo:
		os.chown(dirPath, -1, setGroupTo)
