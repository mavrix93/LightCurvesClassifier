"""
Common code supporting functionality described in DALI.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from gavo import base
from gavo import formats
from gavo import utils
from gavo.base import sqlmunge

# Upload stuff -- note that TAP uploads are somewhat different from the
# DALI ones, as TAP allows multiple uploads in one string. Hence, we
# have a different (and simpler) implementation here.


def getUploadKeyFor(inputKey):
	"""returns an input key for file items in "PQL".

	This is actually specified by DALI.  In that scheme, the parameter
	is always called UPLOAD (there can thus only be one such parameter,
	but it can be present multiple times if necessary, except we've
	not figured out how to do the description right in that case).

	It contains a comma-separated pair of (key,source) pairs, where
	source is a URL; there's a special scheme param: for referring to 
	inline uploads by their name.

	This is used exclusively for metadata generation, and there's special
	code to handle it there.  There's also special code in 
	inputdef.ContextGrammar to magcially make UPLOAD into the file 
	parameters we use within DaCHS.  Sigh.
	"""
	return inputKey.change(
		name="INPUT:UPLOAD",
		type="pql-upload",
		description="An upload of the form '%s,URL'; the input for this"
			" parameter is then taken from URL, which may be param:name"
			" for pulling the content from the inline upload name.  Purpose"
			" of the upload: %s"%(inputKey.name, inputKey.description),
		values=None)

# pql-uploads never contribute to SQL queries
sqlmunge.registerSQLFactory("pql-upload", lambda field, val, sqlPars: None)


def parseUploadString(uploadString):
	"""returns resourceName, uploadSource from a DALI upload string.
	"""
	try:
		destName, uploadSource = uploadString.split(",", 1)
	except (TypeError, ValueError):
		raise base.ValidationError("Invalid UPLOAD string",
			"UPLOAD", hint="UPLOADs look like my_upload,http://foo.bar/up"
				" or inline_upload,param:foo.")
	return destName, uploadSource


class URLUpload(object):
	"""a somewhat FieldStorage-compatible facade to an upload coming from
	a URL.

	The filename for now is the complete upload URL, but that's likely
	to change.
	"""
	def __init__(self, uploadURL, uploadName):
		self.uploadURL, self.name = uploadURL, uploadName
		self.file = utils.urlopenRemote(self.uploadURL)
		self.filename = uploadURL
		self.headers = self.file.info()
		major, minor, parSet = formats.getMIMEKey(self.headers.get(
			"content-type", "*/*"))
		self.type = "%s/%s"%(major, minor)
		self.type_options = dict(parSet)
	
	@property
	def value(self):
		try:
			f = utils.urlopenRemote(self.uploadURL)
			return f.read()
		finally:
			f.close()


def mangleUploads(argDict):
	"""manipulates argDict to turn DALI UPLOADs into DaCHS input files.

	These are as in normal CGI: uploads are under "their names" (with
	DALI uploads, the resource names), with values being
	FieldStorage-compatible things having name, filename, value, file, type,
	type_options, and headers.

	ArgDict is manipulated in place.
	"""
	uploads = argDict.pop("UPLOAD", [])
	if not uploads:
		return
		
	for uploadString in uploads:
		destName, uploadSource = parseUploadString(uploadString)
		if uploadSource.startswith("param:"):
			try:
				argDict[destName] = argDict.pop(uploadSource[6:])[0]
			except (KeyError, IndexError):
				raise base.ValidationError("%s references a non-existing"
					" parameter."%uploadSource, "UPLOAD", 
					hint="If you pass UPLOAD=foo,param:x,"
					" you must pass a file upload under the key x.")
		else:
			argDict[destName] = URLUpload(uploadSource, destName)
