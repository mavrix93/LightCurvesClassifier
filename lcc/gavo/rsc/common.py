"""
Helpers for resource creation.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import copy

from gavo import base


class DBTableError(base.Error):
	"""is raised when a manipulation of an on-disk table fails.

	It always has a qName attribute containing the qualified name of
	the table causing the trouble.
	"""
	def __init__(self, msg, qName, hint=None):
		base.Error.__init__(self, msg, hint=hint)
		self.qName = qName
		self.args = [msg, qName]


class FLUSH(object):
	"""A sentinel that grammars can yield to flush out records to the
	Database.

	This probably is only necessary in updating dispatched grammars to
	enforce dropping of rows dependent on some table.
	"""


class ParamMixin(object):
	"""A mixin providing param processing.

	This is for tables and data elements.  If you mix this in, you have
	to call _initParams(rscdefObject, params=None) 
	
	rscdefObject is a TableDef or DataDef, params, if given, a dictionary
	mapping param names to param values.
	"""
	def _initParams(self, paramsDef, params=None):
		self.paramsDef = paramsDef
		self._params = self.paramsDef.params.deepcopy(self.paramsDef)
		if self.paramsDef.id:
			self._params.withinId = "%s %s"%(
				self.paramsDef.__class__.__name__, self.paramsDef.id)
		else:
			self._params.withinId = "anonymous "+self.paramsDef.__class__.__name__
		if params is not None:
			self.setParams(params)
	
	def setParams(self, parDict, raiseOnBadKeys=True):
		for k, v in parDict.iteritems():
			try:
				self.setParam(k, v)
			except base.NotFoundError:
				if raiseOnBadKeys:
					raise

	def setParam(self, parName, value):
		"""sets a parameter to a value.

		String-typed values will be parsed, everything else is just entered
		directly.  Trying to write to non-existing params will raise a
		NotFoundError.

		Do now write to params directly, you'll break things.
		"""
		self._params.getColumnByName(parName).set(value)
	
	def getParam(self, parName):
		"""retrieves a parameter (python) value.
		"""
		return self._params.getColumnByName(parName).value

	def getParamByName(self, parName):
		return self._params.getColumnByName(parName)

	def iterParams(self):
		"""iterates over the parameters for this table.

		The items returned are rscdef.Param instances.
		"""
		return self._params

	def getParamDict(self):
		return dict((p.name, p.value) for p in self.iterParams())


class ParseOptions(object):
	"""see getParseOptions.
	"""
	def change(self, **kwargs):
		"""returns a copy of self with the keyword parameters changed.

		Trying to add attributes in this way will raise an AttributeError.

		>>> p = parseValidating.change(validateRows=False)
		>>> p.validateRows
		False
		>>> p.change(gulp=1)
		Traceback (most recent call last):
		AttributeError: ParseOptions instances have no gulp attributes
		"""
		newInstance = copy.copy(self)
		for key, val in kwargs.iteritems():
			if not hasattr(newInstance, key):
				raise AttributeError("%s instances have no %s attributes"%(
					newInstance.__class__.__name__, key))
			setattr(newInstance, key, val)
		return newInstance


def getParseOptions(validateRows=True, updateMode=False, doTableUpdates=False,
		batchSize=1024, maxRows=None, keepGoing=False, dropIndices=False,
		dumpRows=False, metaOnly=False, buildDependencies=True,
		systemImport=False, commitAfterMeta=False):
	"""returns an object with some attributes set.

	This object is used in the parsing code in dddef.  It's a standin
	for the the command line options for tables created internally and
	should have all attributes that the parsing infrastructure might want
	from the optparse object.

	So, just configure what you want via keyword arguments or use the
	prebuilt objects parseValidating and and parseNonValidating below.

	See commandline.py for the meaning of the attributes.

	The exception is buildDependencies.  This is true for most internal
	builds of data (and thus here), but false when we need to manually
	control when dependencies are built, as in user.importing and
	while building the dependencies themselves.
	"""
	po = ParseOptions()
	po.validateRows = validateRows
	po.systemImport = systemImport
	po.keepGoing = keepGoing
	po.updateMode = updateMode
	po.dumpRows = dumpRows
	po.doTableUpdates = doTableUpdates
	po.batchSize = batchSize
	po.maxRows = maxRows
	po.dropIndices = dropIndices
	po.metaOnly = metaOnly
	po.buildDependencies = buildDependencies
	po.commitAfterMeta = commitAfterMeta
	return po


parseValidating = getParseOptions(validateRows=True)
parseNonValidating = getParseOptions(validateRows=False)


def _test():
	import doctest, common
	doctest.testmod(common)


if __name__=="__main__":
	_test()
