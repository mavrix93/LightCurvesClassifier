"""
Products, a grammar to make them, and a core turning accrefs into lists
of products.

There is a substantial overlap between what's going on there and datalink
(and datalink uses some of the products mentioned here).  The cutouts
and scale things here shouldn't be developed on, all this should
move towards datalink.  Meanwhile, we still have siapCutoutCore and
friends that relies on the mess here, so all this is going to remain
for the forseeable future.  Just don't extend it.

The "user-visible" part are just accrefs, as modelled by the RAccref
-- they can contain instructions for cutouts or scaling, hence the additional
structure.

Using the product table and the ProductsGrammar, such accrefs are turned
into subclasses of ProductBase.  

These have mime types and know how to generate their data through their
synchronous iterData methods.  They must also work as nevow resources and thus
have implement asynchronuous renderHTTP(ctx) methods.  It's a bit unfortunate
that we thus depend on nevow here, but we'd have to reimplement quite a bit of
it if we don't, and for now it doesn't seem we'll support a different framework
in the forseeable future.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from __future__ import with_statement

import datetime
import gzip
import re
import os
import struct
import urllib
import urlparse
from cStringIO import StringIO

import numpy

import Image

from nevow import inevow
from nevow import static
from twisted.internet import defer
from twisted.internet import threads
from zope.interface import implements

from gavo import base
from gavo import grammars
from gavo import rsc
from gavo import rscdef
from gavo import svcs
from gavo import utils
from gavo.base import coords
from gavo.base import valuemappers
from gavo.protocols import creds
from gavo.svcs import streaming
from gavo.utils import imgtools
from gavo.utils import fitstools
from gavo.utils import pyfits


# TODO: make this configurable -- globally?  by service?
PREVIEW_SIZE = 200

REMOTE_URL_PATTERN = re.compile("(https?|ftp)://")

MS = base.makeStruct


def _getProductsTable():
	"""returns an instance of the products table.

	Clients should use the getProductsTable below to save the cost of
	constructing the table.
	"""
	td = base.caches.getRD("//products").getById("products")
	conn = base.getDBConnection("admin", autocommitted=True)
	return rsc.TableForDef(td, connection=conn)


getProductsTable = utils.CachedGetter(
	_getProductsTable,
	isAlive=lambda t: not t.connection.closed)


def makePreviewFromFITS(product):
	"""returns image/jpeg bytes for a preview of a product spitting out a
	2D FITS.
	"""
	if hasattr(product, "getFile"):
		# hack to preserve no-so-well-thought out existing functionality
		if product.rAccref.accref.endswith(".gz"):
			inFile = gzip.GzipFile(fileobj=product.getFile())
		else:
			inFile = product.getFile()

		pixels = numpy.array([row 
			for row in fitstools.iterScaledRows(inFile, 
				destSize=PREVIEW_SIZE)])
	else:
		raise NotImplementedError("TODO: Fix fitstools.iterScaledRows"
			" to be more accomodating to weird things")
	return imgtools.jpegFromNumpyArray(pixels)


def makePreviewWithPIL(product):
	"""returns image/jpeg bytes for a preview of the PIL-readable product.
	"""
	# TODO: Teach products to at least accept seek(0) and directly read from
	# them; at least make read(None) work properly
	fullsize = StringIO(product.read(1000000000))
	im = Image.open(fullsize)
	scale = max(im.size)/float(PREVIEW_SIZE)
	resized = im.resize((
		int(im.size[0]/scale),
		int(im.size[1]/scale)))	
	f = StringIO()
	resized.save(f, format="jpeg")
	return f.getvalue()


_PIL_COMPATIBLE_MIMES = frozenset(['image/jpeg', 'image/png'])

def computePreviewFor(product):
	"""returns image/jpeg bytes containing a preview of product.

	This only works for a select subset of products.  You're usually
	better off using static previews.
	"""
	if hasattr(product, "makePreview"):
		return product.makePreview()

	sourceMime = product.pr["mime"]
	if sourceMime=='image/fits':
		return makePreviewFromFITS(product)
	elif sourceMime in _PIL_COMPATIBLE_MIMES:
		return makePreviewWithPIL(product)
	else:
		raise base.DataError("Cannot make automatic preview for %s"%
			sourceMime)


class PreviewCacheManager(object):
	"""is a class that manages the preview cache.

	It's really the class that manages it, so don't bother creating instances.

	The normal operation is that you pass the product you want a preview to
	getPreviewFor.  If a cached preview already exists, you get back its content
	(the mime type must be taken from the products table).

	If the file does not exist yet, some internal magic tries to come up with
	a preview and determines whether it should be cached, in which case it does
	so provided a preview has been generated successfully.

	A cache file is touched when it is used, so you can clean up rarely used
	cache files by deleting all files in the preview cache older than some 
	limit.
	"""
	cachePath = base.getConfig("web", "previewCache")

	@classmethod
	def getCacheName(cls, accref):
		"""returns the full path a preview for accref is be stored under.
		"""
		return os.path.join(cls.cachePath, rscdef.getFlatName(accref))

	@classmethod
	def getCachedPreviewPath(cls, accref):
		"""returns the path to a cached preview if it exists, None otherwise.
		"""
		cacheName = cls.getCacheName(accref)
		if os.path.exists(cacheName):
			return cacheName
		return None

	@classmethod
	def saveToCache(self, data, cacheName):
		try:
			with open(cacheName, "w") as f:
				f.write(data)
		except IOError: # caching failed, don't care
			pass
		return data

	@classmethod
	def getPreviewFor(cls, product):
		"""returns a deferred firing the data for a preview.
		"""
		if not product.rAccref.previewIsCacheable():
			return threads.deferToThread(computePreviewFor, product)

		accref = product.rAccref.accref
		cacheName = cls.getCacheName(accref)
		if os.path.exists(cacheName):
			# Cache hit
			try:
				os.utime(cacheName, None)
			except os.error:
				pass   # don't fail just because we can't touch

			with open(cacheName) as f:
				return defer.succeed(f.read())

		else:
			# Cache miss
			return threads.deferToThread(computePreviewFor, product
				).addCallback(cls.saveToCache, cacheName)


class ProductBase(object):
	"""A base class for products returned by the product core.

	See the module docstring for the big picture.

	The constructor arguments of RAccrefs depend on what they are.
	The common interface (also used by the ProductGrammar below)
	is the the class method fromRAccref(rAccref, grammar=None).
	It returns None if the RAccref is not for a product of the
	respective sort, the product otherwise.  Grammar, if given,
	is an instance of the products grammar.  It is important, e.g.,
	in controlling access to embargoed products.  This is the main
	reason you should never hand out products yourself but always
	expose the to the user through the product core.

	The actual constructor requires a RAccref, which is exposed as the 
	rAccref attribute.  Do not use the productsRow attribute from rAccref, 
	though, as constructors may want to manipulate the content of the 
	product row (e.g., in NonExistingProduct).  Access the product
	row as self.pr in product classes.

	In addition to those, all Products have a name attribute,
	which must be something suitable as a file name; the default
	constructor calls a _makeName method to come up with one, and
	you should simply override it.

	The iterData method has to yield reasonably-sized chunks of
	data (self.chunkSize should be a good choice).	It must be
	synchronuous.

	Products usually are used as nevow resources.  Therefore, they
	must have a renderHTTP method.	This must be asynchronuous,
	i.e., it should not block for extended periods of time.

	Products also work as rudimentary files via read and close
	methods; by default, these are implemented on top of iterData.
	Clients must never mix calls to the file interface and to
	iterData.  Derived classes that are based on actual files should
	set up optimized read and close methods using the setupRealFile
	class method (look for the getFile method on the instance to see
	if there's a real file).  Again, the assumption is made there that clients
	use either iterData or read, but never both.

	If a product knows how to (quickly) generate a preview for itself,
	it can define a makePreview() method.  This must return content
	for a mime type conventional for that kind of product (which is laid
	down in the products table).
	"""
	implements(inevow.IResource)

	chunkSize = 2**16
	_curIterator = None

	def __init__(self, rAccref):
		# If you change things here, change NonExistingProduct's constructor
		# as well.
		self.rAccref = rAccref
		self.pr = self.rAccref.productsRow
		self._makeName()

	def _makeName(self):
		self.name = "invalid product"

	def __str__(self):
		return "<%s %s (%s)>"%(self.__class__.__name__,
			self.name,
			self.pr["mime"])
	
	def __repr__(self):
		return str(self)
	
	def __eq__(self, other):
		return (isinstance(other, self.__class__) 
			and self.rAccref==other.rAccref)
	
	def __ne__(self, other):
		return not self==other

	@classmethod
	def fromRAccref(self, accref, grammar=None):
		return None # ProductBase is not responsible for anything.

	@classmethod
	def setupRealFile(cls, openMethod):
		"""changes cls such that read and close work an an actual file-like 
		object rather than the inefficient iterData.

		openMethod has to be an instance method of the class returning
		an opened input file.
		"""
		cls._openedInputFile = None

		def getFileMethod(self):
			return openMethod(self)

		def readMethod(self, size=None):
			if self._openedInputFile is None:
				self._openedInputFile = openMethod(self)
			return self._openedInputFile.read(size)

		def closeMethod(self):
			if self._openedInputFile is not None:
				self._openedInputFile.close()
			self._openedInputFile = None

		cls.read = readMethod
		cls.close = closeMethod
		cls.getFile = getFileMethod

	def iterData(self):
		raise NotImplementedError("Internal error: %s products do not"
			" implement iterData"%self.__class__.__name__)

	def renderHTTP(self, ctx):
		raise NotImplementedError("Internal error: %s products cannot be"
			" rendered."%self.__class__.__name__)

	def read(self, size=None):
		if self._curIterator is None:
			self._curIterator = self.iterData()
			self._readBuf, self._curSize = [], 0

		while size is None or self._curSize<size:
			try:
				chunk = self._curIterator.next()
			except StopIteration:
				break
			self._readBuf.append(chunk)
			self._curSize += len(chunk)

		content = "".join(self._readBuf)
		if size is None:
			self._readBuf, self._curSize = [], 0
			result = content

		else:
			result = content[:size]
			self._readBuf = [content[size:]]
			self._curSize = len(self._readBuf[0])

		return result
	
	def close(self):
		for _ in self.iterData():
			pass
		self._curIterator = None
	

class FileProduct(ProductBase):
	"""A product corresponding to a local file.

	As long as the accessPath in the RAccref's productsRow corresponds
	to a real file and no params are in the RAccref, this will return
	a product.
	"""
	@classmethod
	def fromRAccref(cls, rAccref, grammar=None):
		if set(rAccref.params)-set(["preview"]):  # not a plain file
			return None
		if os.path.exists(rAccref.localpath):
			return cls(rAccref)

	def _makeName(self):
		self.name = os.path.basename(self.rAccref.localpath)
	
	def _openUnderlyingFile(self):
		# the stupid "rb" is not here for windows but for pyfits, which has
		# checks for the b now and then.
		return open(self.rAccref.localpath, "rb")

	def iterData(self):
		with self._openUnderlyingFile() as f:
			data = f.read(self.chunkSize)
			if data=="":
				return
			yield data

	def renderHTTP(self, ctx):
		request = inevow.IRequest(ctx)
		request.setHeader("content-disposition", 'attachment; filename="%s"'%
			str(self.name))
		request.setLastModified(os.path.getmtime(self.rAccref.localpath))
		res = static.File(self.rAccref.localpath)
		# we set the type manually to avoid having different mime types
		# by our and nevow's estimate.  This forces us to clamp encoding
		# to None now.  I *guess* we should do something about .gz and .bz2
		res.type = str(self.pr["mime"])
		res.encoding = None
		return res

FileProduct.setupRealFile(FileProduct._openUnderlyingFile)


class StaticPreview(FileProduct):
	"""A product that's a cached or pre-computed preview.
	"""
	
	@classmethod
	def fromRAccref(cls, rAccref, grammar=None):
		if not rAccref.params.get("preview"):
			return None
		# no static previews on cutouts
		if rAccref.params.get("sra"):
			return None

		previewPath = rAccref.productsRow["preview"]
		localName = None

		if previewPath is None:
			return None

		elif previewPath=="AUTO":
			localName = PreviewCacheManager.getCachedPreviewPath(rAccref.accref)

		else:
			# remote URLs can't happen here as RemotePreview is checked
			# before us.
			localName = os.path.join(base.getConfig("inputsDir"), previewPath)

		if localName is None:
			return None
		elif os.path.exists(localName):
			rAccref.productsRow["accessPath"] = localName
			rAccref.productsRow["mime"] = rAccref.productsRow["preview_mime"
				] or "image/jpeg"
			return cls(rAccref)


class RemoteProduct(ProductBase):
	"""A class for products at remote sites, given by their URL.
	"""
	def _makeName(self):
		self.name = urlparse.urlparse(self.pr["accessPath"]
			).path.split("/")[-1] or "file"

	def __str__(self):
		return "<Remote %s at %s>"%(self.pr["mime"], self.pr["accessPath"])
	
	@classmethod
	def fromRAccref(cls, rAccref, grammar=None):
		if REMOTE_URL_PATTERN.match(rAccref.productsRow["accessPath"]):
			return cls(rAccref)

	def iterData(self):
		f = urllib.urlopen(self.pr["accessPath"])
		while True:
			data = f.read(self.chunkSize)
			if data=="":
				break
			yield data

	def renderHTTP(self, ctx):
		raise svcs.WebRedirect(self.pr["accessPath"])


class RemotePreview(RemoteProduct):
	"""A preview that's on a remote server.
	"""
	@classmethod
	def fromRAccref(cls, rAccref, grammar=None):
		if not rAccref.params.get("preview"):
			return None
		# no static previews on cutouts
		if rAccref.params.get("sra"):
			return None
		
		if REMOTE_URL_PATTERN.match(rAccref.productsRow["preview"]):
			rAccref.productsRow["accessPath"] = rAccref.productsRow["preview"]
			rAccref.productsRow["mime"] = rAccref.productsRow["preview_mime"]
			return cls(rAccref)


class UnauthorizedProduct(FileProduct):
	"""A local file that is not delivered to the current client. 

	iterData returns the data for the benefit of preview making.
	However, there is a renderHTTP method, so the product renderer will
	not use it; it will, instead, raise an Authenticate exception.
	"""
	@classmethod
	def fromRAccref(cls, rAccref, grammar=None):
		dbRow = rAccref.productsRow
		if (dbRow["embargo"] is None 
				or dbRow["embargo"]<datetime.date.today()):
			return None
		if grammar is None or dbRow["owner"] not in grammar.groups:
			return cls(rAccref)

	def __str__(self):
		return "<Protected product %s, access denied>"%self.name

	def __eq__(self, other):
		return self.__class__==other.__class__

	def renderHTTP(self, ctx):
		raise svcs.Authenticate()


class NonExistingProduct(ProductBase):
	"""A local file that went away.

	iterData here raises an IOError, renderHTTP an UnknownURI.

	These should normally yield 404s.

	We don't immediately raise some error here as archive generation
	shouldn't fail just because a single part of it is missing.
	"""
	def __init__(self, rAccref):
		#	as rAccref.productsRow is bad here, don't call the base constructor
		self.rAccref = rAccref
		self.pr = {
			'accessPath': None, 'accref': None,
			'embargo': None, 'owner': None,
			'mime': 'text/html', 'sourceTable': None,
			'datalink': None, 'preview': None}

	def __str__(self):
		return "<Non-existing product %s>"%self.rAccref.accref

	def __eq__(self, other):
		return self.__class__==other.__class__

	@classmethod
	def fromRAccref(cls, rAccref, grammar=None):
		try:
			rAccref.productsRow
		except base.NotFoundError:
			return cls(rAccref)

	def _makeName(self):
		self.name = "missing.html"

	def iterData(self):
		raise IOError("%s does not exist"%self.rAccref.accref)

	def renderHTTP(self, ctx):
		raise svcs.UnknownURI(self.rAccref.accref)


class InvalidProduct(NonExistingProduct):
	"""An invalid file.
	
	This is returned by getProductForRAccref if all else fails.  This
	usually happens when a file known to the products table is deleted,
	but it could also be an attempt to use unsupported combinations
	of files and parameters.

	Since any situation leading here is a bit weird, we probably
	should be doing something else but just return a 404.  Hm...

	This class always returns an instance from fromRAccref; this means
	any resolution chain ends with it.  But it shouldn't be in
	PRODUCT_CLASSES in the first place since the fallback is
	hardcoded into getProductForRAccref.
	"""
	def __str__(self):
		return "<Invalid product %s>"%self.rAccref

	@classmethod
	def fromRAccref(cls, rAccref, grammar=None):
		return cls(rAccref)
	
	def _makeName(self):
		self.name = "invalid.html"
	
	def iterData(self):
		raise IOError("%s is invalid"%self.rAccref)


class CutoutProduct(ProductBase):
	"""A class representing cutouts from FITS files.
	
	This only works for local FITS files with two axes.  For everything 
	else, use datalink.
	
	We assume the cutouts are smallish -- they are, right now, not
	streamed, but accumulated in memory.
	"""
	def _makeName(self):
		self.name = "<cutout-"+os.path.basename(self.pr["accessPath"])

	def __str__(self):
		return "<cutout-%s %s>"%(self.name, self.rAccref.params)

	_myKeys = ["ra", "dec", "sra", "sdec"]
	_myKeySet = frozenset(_myKeys)

	@classmethod
	def fromRAccref(cls, rAccref, grammar=None):
		if (len(set(rAccref.params.keys())&cls._myKeySet)==4
				and rAccref.productsRow["mime"]=="image/fits"):
			return cls(rAccref)

	def _getCutoutHDU(self):
		ra, dec, sra, sdec = [self.rAccref.params[k] for k in self._myKeys]
		hdus = pyfits.open(self.rAccref.localpath, do_not_scale_image_data=True)
		try:
			skyWCS = coords.getWCS(hdus[0].header)
			pixelFootprint = numpy.asarray(
				numpy.round(skyWCS.wcs_sky2pix([
					(ra-sra/2., dec-sdec/2.),
					(ra+sra/2., dec+sdec/2.)], 1)), numpy.int32)
			res = fitstools.cutoutFITS(hdus[0], 
				(skyWCS.longAxis, min(pixelFootprint[:,0]), max(pixelFootprint[:,0])),
				(skyWCS.latAxis, min(pixelFootprint[:,1]), max(pixelFootprint[:,1])))
		finally:
			hdus.close()

		return res

	def iterData(self):
		res = self._getCutoutHDU()
		bytes = StringIO()
		res.writeto(bytes)
		del res

		yield bytes.getvalue()

	def _writeStuffTo(self, destF):
		for chunk in self.iterData():
			destF.write(chunk)

	def renderHTTP(self, ctx):
		request = inevow.IRequest(ctx)
		request.setHeader("content-type", "image/fits")
		return streaming.streamOut(self._writeStuffTo, request)
	
	def makePreview(self):
		img = imgtools.scaleNumpyArray(self._getCutoutHDU().data, PREVIEW_SIZE)
		return imgtools.jpegFromNumpyArray(img)


class ScaledFITSProduct(ProductBase):
	"""A class representing a scaled FITS file.

	Right now, this only works for local FITS files.  Still, the
	class is constructed with a full rAccref.
	"""
	def __init__(self, rAccref):
		ProductBase.__init__(self, rAccref)
		self.scale = rAccref.params["scale"]
		self.baseAccref = rAccref.accref
	
	def __str__(self):
		return "<%s scaled by %s>"%(self.name, self.scale)

	@classmethod
	def fromRAccref(cls, rAccref, grammar=None):
		if ("scale" in rAccref.params
				and rAccref.productsRow["mime"]=="image/fits"):
			return cls(rAccref)

	def _makeName(self):
		self.name = "scaled-"+os.path.basename(self.pr["accref"])

	def iterData(self):
		scale = int(self.scale)
		if scale<2:
			scale = 2
		
		with open(self.rAccref.localpath) as f:
			oldHdr = fitstools.readPrimaryHeaderQuick(f)
			newHdr = fitstools.shrinkWCSHeader(oldHdr, scale)
			newHdr.update("FULLURL", str(makeProductLink(self.baseAccref)))
			yield fitstools.serializeHeader(newHdr)

			for row in fitstools.iterScaledRows(f, scale, hdr=oldHdr):
				# Unfortunately, numpy's byte swapping for floats is broken in
				# many wide-spread revisions.  So, we cannot do the fast
				#	yield row.newbyteorder(">").tostring()
				# but rather, for now, have to try the slow:
				yield struct.pack("!%df"%len(row), *row)
			
	def _writeStuffTo(self, destF):
		for chunk in self.iterData():
			destF.write(chunk)

	def renderHTTP(self, ctx):
		request = inevow.IRequest(ctx)
		request.setHeader("content-type", "image/fits")
		return streaming.streamOut(self._writeStuffTo, request)


class DCCProduct(ProductBase):
	"""A class representing a product returned by a DC core.

	Do not use this any more.  It is superseded by datalink.  You can put
	datalink URLs into dc.product's accessPath.

	The source path of the rAccref's productsRow must have the form
	dcc://<rd.id>/<core id>?<coreAccref>; rd.id is the rd id with slashes
	replaced by dots.  This means this scheme doesn't work for RDs with ids
	containing dots, but you shouldn't do that in the first place.  coreAccref is
	just an opaque string that does not necessarily match the product's accref,
	but probably will in most cases.

	The context grammar receives a dictionary with the param dict, plus
	the coreAccref as accref.  The core must return an actual mime type 
	and a string.

	As a special service, iterData here can take a svcs.QueryMeta
	instance which, if given, is passed on to the core.
	
	See SDMCore for an example for how this can work.
	"""
	def __init__(self, rAccref):
		ProductBase.__init__(self, rAccref)
		self.params = rAccref.params
		self.name = os.path.basename(self.pr["accref"])
		self._parseAccessPath()

	_schemePat = re.compile("dcc://")

	@classmethod
	def fromRAccref(cls, rAccref, grammar=None):
		if cls._schemePat.match(rAccref.productsRow["accessPath"]):
			return cls(rAccref)

	def _makeName(self):
		self.name = "untitled"  # set in the constructor
	
	def _parseAccessPath(self):
		# The scheme is manually handled to shoehorn urlparse into supporting
		# queries (and, potentially, fragments)
		ap = self.pr["accessPath"]
		if not ap.startswith("dcc:"):
			raise svcs.UnknownURI("DCC products can only be generated for dcc"
				" URIs")
		res = urlparse.urlparse(ap[4:])
		self.core = base.caches.getRD(
			res.netloc.replace(".", "/")).getById(res.path.lstrip("/"))
		self.accref = res.query

	def iterData(self, queryMeta=svcs.emptyQueryMeta):
		inData = self.params.copy()
		inData["accref"] = self.accref
		inputTable = rsc.TableForDef(self.core.inputTable)
		inputTable.setParams(inData, raiseOnBadKeys=False)
		self.generatedContentType, data = self.core.run(
			self, inputTable, queryMeta)
		yield data
	
	def renderHTTP(self, ctx):
		return threads.deferToThread(self.iterData, 
			svcs.QueryMeta.fromContext(ctx)
		).addCallback(self._deliver, ctx)
	
	def _deliver(self, resultIterator, ctx):
		result = "".join(resultIterator)
		request = inevow.IRequest(ctx)
		request.setHeader("content-type", self.generatedContentType)
		request.setHeader("content-disposition", 'attachment; filename="%s"'%
			str(self.name))
		return result


# The following list is checked by getProductForRAccref in sequence.
# Each product is asked in turn, and the first that matches wins.
# So, ORDER IS ALL-IMPORTANT here.
PRODUCT_CLASSES = [
	RemotePreview,
	StaticPreview,
	NonExistingProduct,
	UnauthorizedProduct,
	RemoteProduct,
	DCCProduct,
	CutoutProduct,
	ScaledFITSProduct,
	FileProduct,
]

def getProductForRAccref(rAccref, grammar=None):
	"""returns a product for a RAccref.

	This tries, in sequence, to make a product using each element
	of PRODUCT_CLASSES' fromRAccref method.  If nothing succeeds,
	it will return an InvalidProduct.

	If rAccref is a string, the function makes a real RAccref through
	RAccref's fromString method from it.
	"""
	if not isinstance(rAccref, RAccref):
		rAccref = RAccref.fromString(rAccref)
	for prodClass in PRODUCT_CLASSES:
		res = prodClass.fromRAccref(rAccref, grammar)
		if res is not None:
			return res
	return InvalidProduct.fromRAccref(rAccref, grammar)


class ProductIterator(grammars.RowIterator):
	"""A RowIterator turning RAccrefs to instances of subclasses of
	ProductBase.

	The source key is a list of RAccrefs, as, e.g., produced by
	the ProductCore.
	"""
	def _iterRows(self):
		for rAccref in self.sourceToken:
			yield {
				"source": getProductForRAccref(rAccref, self.grammar)
			}
		del self.grammar


class ProductsGrammar(grammars.Grammar):
	"""A grammar for "parsing" annotated RAccref to Product
	objects.

	Product objects are instances of classes derived from ProductBase.
	"""
	rowIterator = ProductIterator

	_groups = base.StringSetAttribute("groups")

	def __init__(self, *args, **kwargs):
		self.now = datetime.date.today()
		grammars.Grammar.__init__(self, *args, **kwargs)


class ProductCore(svcs.DBCore):
	"""A core retrieving paths and/or data from the product table.

	You will not usually mention this core in your RDs.  It is mainly
	used internally to serve /getproduct queries.

	It is instanciated from within //products.rd and relies on
	tables within that RD.

	The input data consists of accref; you can use the string form
	of RAccrefs, and if you renderer wants, it can pass in ready-made
	RAccrefs.  You can pass accrefs in through both an accref 
	param and table rows.  
	
	The accref param is the normal way if you just want to retrieve a single
	image, the table case is for building tar files and such.  There is one core
	instance in //products for each case.

	The core returns a table containing rows with the single column source.
	Each contains a subclass of ProductBase above.

	All this is so complicated because special processing may take place
	(user autorisation, cutouts, ...) but primarily because we wanted
	the tar generation to use this core.  Looking at the mess that's caused
	suggests that probably was the wrong decision.
	"""
	name_ = "productCore"

	def _getRAccrefs(self, inputTable):
		"""returns a list of RAccref requested within inputTable.
		"""
		keysList = [RAccref.fromString(r["accref"])
			for r in inputTable.rows if "accref" in r]
		try:
			param = inputTable.getParam("accref")
			if param is not None:
				keysList.append(RAccref.fromString(param))
		except base.NotFoundError: # "tar case", accrefs in rows
			pass
		return keysList

	def _getGroups(self, user, password):
		if user is None:
			return set()
		else:
			return creds.getGroupsForUser(user, password)

	def run(self, service, inputTable, queryMeta):
		"""returns a data set containing product sources for the keys mentioned in
		inputTable.
		"""
		authGroups = self._getGroups(queryMeta["user"], queryMeta["password"])

		dd = MS(rscdef.DataDescriptor, grammar=MS(ProductsGrammar,
				groups=authGroups),
			make=[MS(rscdef.Make, table=self.outputTable)])

		return rsc.makeData(dd, forceSource=self._getRAccrefs(inputTable))


class RAccref(object):
	"""A product key including possible modifiers.

	The product key is in the accref attribute.

	The modifiers come in the params dictionary.  It contains (typed)
	values, the possible keys of which are given in _buildKeys.  The
	values in passed in the inputDict constructor argument are parsed,
	anything not in _buildKeys is discarded.

	In principle, these modifiers are just the query part of a URL,
	and they generally come from the arguments of a web request.  However,
	we don't want to carry around all request args, just those meant
	for product generation.
	
	One major reason for having this class is serialization into URL-parts.
	Basically, stringifying a RAccref yields something that can be pasted
	to <server root>/getproduct to yield the product URL.  For the
	path part, this means just percent-escaping blanks, plusses and percents
	in the file name.  The parameters are urlencoded and appended with
	a question mark.  This representation is be parsed by the fromString
	function.

	RAccrefs have a (read only) property productsRow attribute -- that's 
	a dictionary containing the row for accres from //products#products
	if that exists.  If it doesn't, accessing the property will raise
	an NotFoundError.
	"""
	_buildKeys = dict((
		("dm", str),    # data model, VOTable generation
		("ra", float),  # cutouts
		("dec", float), # cutouts
		("sra", float), # cutouts
		("sdec", float),# cutouts
		("scale", int), # FITS scaling
		("preview", base.parseBooleanLiteral), # return a preview?
	))

	def __init__(self, accref, inputDict={}):
		self.accref = accref
		self.params = self._parseInputDict(inputDict)
	
	@classmethod
	def fromPathAndArgs(cls, path, args):
		"""returns a rich accref from a path and a parse_qs-dictionary args.

		(it's mainly a helper for fromRequest and fromString).
		"""
		inputDict = {}
		for key, value in args.iteritems():
			if len(value)>0:
				inputDict[key] = value[-1]

		# Save old URLs: if no (real) path was passed, try to get it
		# from key.  Remove this ca. 2014, together with 
		# RaccrefTest.(testPathFromKey|testKeyMandatory)
		if not path.strip("/").strip():
			if "key" in inputDict:
				path = inputDict["key"]
			else:
				raise base.ValidationError(
					"Must give key when constructing RAccref",
					"accref")

		return cls(path, inputDict)

	@classmethod
	def fromRequest(cls, path, request):
		"""returns a rich accref from a nevow request.

		Basically, it raises an error if there's no key at all, it will return
		a (string) accref if no processing is desired, and it will return
		a RAccref if any processing is requested.
		"""
		return cls.fromPathAndArgs(path, request.args)

	@classmethod
	def fromString(cls, keyString):
		"""returns a fat product key from a string representation.

		As a convenience, if keyString already is a RAccref,
		it is returned unchanged.
		"""
		if isinstance(keyString, RAccref):
			return keyString

		qSep = keyString.rfind("?")
		if qSep!=-1:
			return cls.fromPathAndArgs(
				unquoteProductKey(keyString[:qSep]), 
				urlparse.parse_qs(keyString[qSep+1:]))

		return cls(unquoteProductKey(keyString))

	@property
	def productsRow(self):
		"""returns the row in dc.products corresponding to this RAccref's
		accref, or raises a NotFoundError.
		"""
		try:
			return self._productsRowCache
		except AttributeError:
			pt = getProductsTable()
			res = list(pt.iterQuery(pt.tableDef, "accref=%(accref)s", 
				{"accref": self.accref}))
			if not res:
				raise base.NotFoundError(self.accref, "accref", "product table",
					hint="Product URLs may disappear, though in general they should"
					" not.  If you have an IVORN (pubDID) for the file you are trying to"
					" locate, you may still find it by querying the ivoa.obscore table"
					" using TAP and ADQL.")
			self._productsRowCache = res[0]
		
			# make sure whatever can end up being written to something
			# file-like
			for key in ["mime", "accessPath", "accref"]:
				self._productsRowCache[key] = str(self._productsRowCache[key])

			return self._productsRowCache

	def __str__(self):
		# See the class docstring on quoting considerations.
		res = quoteProductKey(self.accref)
		args = urllib.urlencode(dict(
			(k,str(v)) for k, v in self.params.iteritems()))
		if args:
			res = res+"?"+args
		return res

	def __repr__(self):
		return str(self)

	def __eq__(self, other):
		return (isinstance(other, RAccref) 
			and self.accref==other.accref
			and self.params==other.params)

	def __ne__(self, other):
		return not self.__eq__(other)

	def _parseInputDict(self, inputDict):
		res = {}
		for key, val in inputDict.iteritems():
			if val is not None and key in self._buildKeys:
				try:
					res[key] = self._buildKeys[key](val)
				except (ValueError, TypeError):
					raise base.ValidationError(
						"Invalid value for constructor argument to %s:"
						" %s=%r"%(self.__class__.__name__, key, val), "accref")
		return res

	@property
	def localpath(self):
		try:
			return self._localpathCache
		except AttributeError:
			self._localpathCache = os.path.join(base.getConfig("inputsDir"), 
				self.productsRow["accessPath"])
		return self._localpathCache

	def previewIsCacheable(self):
		"""returns True if the a preview generated for this rAccref
		is representative for all representative rAccrefs.

		Basically, scaled versions all have the same preview, cutouts do not.
		"""
		if "ra" in self.params:
			return False
		return True


def unquoteProductKey(key):
	"""reverses quoteProductKey.
	"""
	return urllib.unquote(key)


@utils.document
def quoteProductKey(key):
	"""returns key as getproduct URL-part.

	if key is a string, it is quoted as a naked accref so it's usable
	as the path part of an URL.  If it's an RAccref, it is just stringified.
	The result is something that can be used after getproduct in URLs
	in any case.
	"""
	if isinstance(key, RAccref):
		return str(key)
	return urllib.quote(key)
rscdef.addProcDefObject("quoteProductKey", quoteProductKey)


@utils.document
def makeProductLink(key, withHost=True):
	"""returns the URL at which a product can be retrieved.

	key can be an accref string or an RAccref
	"""
	url = base.makeSitePath("/getproduct/%s"%RAccref.fromString(key))
	if withHost:
		url = urlparse.urljoin(base.getConfig("web", "serverURL"), url)
	return url
rscdef.addProcDefObject("makeProductLink", makeProductLink)


def _productMapperFactory(colDesc):
	"""A factory for accrefs.

	Within the DC, any column called accref, with a display hint of
	type=product, a UCD of VOX:Image_AccessReference, or a utype
	of Access.Reference may contain a key into the product table.
	Here, we map those to links to the get renderer unless they look
	like a URL to begin with.
	"""
	if not (
			colDesc["name"]=="accref"
			or colDesc["utype"]=="ssa:Access.Reference"
			or colDesc["ucd"]=="VOX:Image_AccessReference"
			or colDesc["displayHint"].get("type")=="product"):
		return
	
	looksLikeURLPat = re.compile("[a-z]{2,5}://")

	def mapper(val):
		if val:
			# type check to allow cut-out or scaled accrefs (which need 
			# makeProductLink in any case)
			if isinstance(val, basestring) and looksLikeURLPat.match(val):
				return val
			else:
				return makeProductLink(val, withHost=True)
	return mapper

valuemappers._registerDefaultMF(_productMapperFactory)
