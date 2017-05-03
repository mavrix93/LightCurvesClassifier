"""
Helper functions for producing tar files from tables containing
a product column.

Everything in this module expects the product interface, i.e., tables
must at least contain accref, owner, embargo, and accsize fields.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


# XXX TODO: this should eventually become a renderer on the product core,
# redirected to from the current TarResponse.

from cStringIO import StringIO
import os
import tarfile
import time

from gavo import base
from gavo import grammars
from gavo import rsc
from gavo import utils
from gavo.protocols import products
from gavo.svcs import streaming


MS = base.makeStruct


class UniqueNameGenerator(object):
	"""A factory to build unique names from possibly ambiguous ones.

	If the lower case of a name is not known to an instance, it just returns
	that name.  Otherwise, it disambiguates by adding characters in front
	of the extension.
	"""
	def __init__(self):
		self.knownNames = set()

	def _buildNames(self, baseName):
		base, ext = os.path.splitext(baseName)
		yield "dc_data/%s%s"%(base, ext)
		i = 1
		while True:
			yield "dc_data/%s-%03d%s"%(base, i, ext)
			i += 1

	def makeName(self, baseName):
		for name in self._buildNames(baseName):
			if name.lower() not in self.knownNames:
				self.knownNames.add(name.lower())
				return str(name)


class ColToRowIterator(grammars.RowIterator):
	"""A RowIterator yielding several columns of a row as separate rows.

	A hacky feature is that a ColToRowIterator will not return the same
	row twice.  This is a convenience for TarMakers to keep them from
	tarring in identical files that somehow manage to be mentioned more
	than once in a result table.
	"""
	def __init__(self, *args, **kwargs):
		grammars.RowIterator.__init__(self, *args, **kwargs)
		self.seenKeys = set()

	def _iterRows(self):
		for row in self.sourceToken:
			for key in self.grammar.sourceKeys:
				if row.get(key):
					accref = row[key]
					# this is a service for "rich" product displays that
					# select more than one row: if we have a list (SQL array)
					# extract the first element and use that as access key
					if isinstance(accref, list):
						accref = accref[0]
					# The str below is for product.RAccrefs
					if str(accref) not in self.seenKeys:
						yield {self.grammar.targetKey: accref}
						self.seenKeys.add(str(accref))


class ColToRowGrammar(grammars.Grammar):
	"""is a grammar that selects some columns and returns each of them
	as a row with a specified key.

	This is useful to extract all products from tables that can have
	multiple columns carrying products.

	The input is a sequence of dictionaries (i.e., Table rows).
	"""

	rowIterator = ColToRowIterator

	_targetKey = base.UnicodeAttribute("targetKey", default=base.Undefined,
		description="Name of the target column")
	_sourceKeys = base.ListOfAtomsAttribute("sourceKeys",
		description="Names of the source columns.", 
		itemAttD=base.UnicodeAttribute("sourceKey"))


class ProductTarMaker(object):
	"""A factory for tar files.

	You probably don't want to instanciate it directly but instead get a copy
	through the getProductMaker function below.

	The main entry point to this class is deliverProductTar.
	"""
	def __init__(self):
		self.rd = base.caches.getRD("__system__/products")
		self.core = self.rd.getById("forTar")

	def _getEmbargoedFile(self, name):
		stuff = StringIO("This file is embargoed.  Sorry.\n")
		b = tarfile.TarInfo(name)
		b.size = len(stuff.getvalue())
		b.mtime = time.time()
		return b, stuff

	def _getTarInfoFromProduct(self, prod, name):
		"""returns a tar info from a general products.PlainProduct instance
		prod.

		This is relatively inefficient for data that's actually on disk,
		so you should only use it when data is being computed on the fly.
		"""
		assert not isinstance(prod, products.UnauthorizedProduct)
		data = "".join(prod.iterData())
		b = tarfile.TarInfo(name)
		b.size = len(data)
		b.mtime = time.time()
		return b, StringIO(data)

	def _getHeaderVals(self, queryMeta):
		if queryMeta.get("Overflow"):
			return "truncated_data.tar", "application/x-tar"
		else:
			return "data.tar", "application/x-tar"

	def _productsToTar(self, productData, destination):
		"""actually writes the tar.
		"""
		nameGen = UniqueNameGenerator()
		outputTar = tarfile.TarFile.open("data.tar", "w|", destination)
		for prodRec in productData.getPrimaryTable():
			src = prodRec["source"]
			if isinstance(src, products.NonExistingProduct):
				continue # just skip files that somehow don't exist any more

			elif isinstance(src, products.UnauthorizedProduct):
				outputTar.addfile(*self._getEmbargoedFile(src.name))

			elif isinstance(src, products.FileProduct):
				# actual file in the file system
				targetName = nameGen.makeName(src.name)
				outputTar.add(str(src.rAccref.localpath), targetName)

			else: # anything else is read from the src
				outputTar.addfile(*self._getTarInfoFromProduct(src,
					nameGen.makeName(src.name)))
		outputTar.close()
		return ""  # finish off request if necessary.

	def _streamOutTar(self, productData, request, queryMeta):
		name, mime = self._getHeaderVals(queryMeta)
		request.setHeader('content-disposition', 
			'attachment; filename=%s'%name)
		request.setHeader("content-type", mime)

		def writeTar(dest):
			self._productsToTar(productData, dest)
		return streaming.streamOut(writeTar, request)

	def deliverProductTar(self, coreResult, request, queryMeta):
		"""causes a tar containing all accrefs mentioned in coreResult
		to be streamed out via request.
		"""
		table = coreResult.original.getPrimaryTable()
		productColumns = table.tableDef.getProductColumns()
		if not productColumns:
			raise base.ValidationError("This query does not select any"
				" columns with access references", "_OUTPUT")
		
		inputTableRows = []
		for row in table:
			for colName in productColumns:
				inputTableRows.append({"accref": row[colName]})
		inputTable = rsc.TableForDef(self.rd.getById("forTar").inputTable, 
			rows=inputTableRows)

		prods = self.core.run(coreResult.service, inputTable, queryMeta)
		return self._streamOutTar(prods, request, queryMeta)


@utils.memoized
def getTarMaker():
	return ProductTarMaker()
