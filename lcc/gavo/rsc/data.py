"""
Making data out of descriptors and sources.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import itertools
import operator
import sys

from gavo import base
from gavo import rscdef
from gavo import utils
from gavo.base import sqlsupport
from gavo.rsc import common
from gavo.rsc import table
from gavo.rsc import tables


MS = base.makeStruct


class _DataFeeder(table._Feeder):
	"""is a feeder for data (i.e., table collections).

	This is basically a collection of all feeders of the tables belonging
	to data, except it will also call the table's mappers, i.e., add
	expects source rows from data's grammars.

	Feeders can be dispatched; this only works if the grammar returns
	pairs of role and row rather than only the row.  Dispatched
	feeders only pass rows to the makes corresponding to the role.

	If you pass in a connection, the data feeder will manage it (i.e.
	commit if all went well, rollback otherwise).
	"""
	def __init__(self, data, batchSize=1024, dispatched=False,
			runCommit=True, connection=None):
		self.data, self.batchSize = data, batchSize
		self.runCommit = runCommit
		self.nAffected = 0
		self.connection = connection
		if dispatched:
			makeAdders = self._makeFeedsDispatched
		else:
			makeAdders = self._makeFeedsNonDispatched

		addersDict, parAddersDict, self.feeders = self._getAdders()
		self.add, self.addParameters = makeAdders(addersDict, parAddersDict)

	def _getAdders(self):
		"""returns a triple of (rowAdders, parAdders, feeds) for the data we
		feed to.

		rowAdders contains functions to add raw rows returned from a grammar,
		parAdders the same for parameters returned by the grammar, and
		feeds is a list containing all feeds the adders add to (this
		is necessary to let us exit all of them.
		"""
		adders, parAdders, feeders = {}, {}, []
		for make in self.data.dd.makes:
			table = self.data.tables[make.table.id]
			feeder = table.getFeeder(batchSize=self.batchSize)
			makeRow = make.rowmaker.compileForTableDef(table.tableDef)
			def addRow(srcRow, feeder=feeder, makeRow=makeRow):
				try:
					procRow = makeRow(srcRow, table)
					feeder.add(procRow)
				except rscdef.IgnoreThisRow:
					pass
			if make.rowSource=="parameters":
				parAdders.setdefault(make.role, []).append(addRow)
			else:
				adders.setdefault(make.role, []).append(addRow)
			feeders.append(feeder)
		return adders, parAdders, feeders

	def _makeFeedsNonDispatched(self, addersDict, parAddersDict):
		adders = reduce(operator.add, addersDict.values(), [])
		parAdders = reduce(operator.add, parAddersDict.values(), [])
		def add(row):
			for adder in adders:
				adder(row)
		def addParameters(row):
			for adder in parAdders:
				adder(row)
		return add, addParameters

	def _makeFeedsDispatched(self, addersDict, parAddersDict):
		def add(roleRow):
			role, row = roleRow
			if role not in addersDict:
				raise base.ReportableError("Grammar tries to feed to role '%s',"
					" but there is no corresponding make"%role)
			for adder in addersDict[role]:
				adder(row)

		# for parameters, allow broadcast
		def addParameters(roleRow):
			try:
				role, row = roleRow
			except ValueError:
				# assume we only got a row, broadcast it
				for adder in itertools.chain(*parAddersDict.values()):
					adder(roleRow)
			else:
				for adder in parAddersDict[role]:
					adder(row)

		return add, addParameters

	def flush(self):
		for feeder in self.feeders:
			feeder.flush()
	
	def reset(self):
		for feeder in self.feeders:
			feeder.reset()

	def __enter__(self):
		for feeder in self.feeders:
			feeder.__enter__()
		return self

	def _exitFailing(self, *excInfo):
		"""calls all subordinate exit methods when there was an error in
		the controlled block.

		This ignores any additional exceptions that might come out of
		the exit methods.

		The condition is rolled back, and we unconditionally propagate
		the exception.
		"""
		for feeder in self.feeders:
			try:
				feeder.__exit__(*excInfo)
			except:
				base.ui.notifyError("Ignored exception while exiting data feeder"
					" on error.")
		if self.connection and self.runCommit:
			self.connection.rollback()
	
	def _exitSuccess(self):
		"""calls all subordinate exit methods when the controlled block
		exited successfully.

		If one of the exit methods fails, we run _exitFailing and re-raise
		the exception.

		If all went well and we control a connection, we commit it (unless
		clients explicitely forbid it).
		"""
		affected = []
		for feeder in self.feeders:
			try:
				feeder.__exit__(None, None, None)
			except:
				self._exitFailing(*sys.exc_info())
				raise
			affected.append(feeder.getAffected())

		if self.connection and self.runCommit:
			self.connection.commit()

		if affected:
			self.nAffected = max(affected)

	def __exit__(self, *excInfo):
		if excInfo and excInfo[0]:
			return self._exitFailing(*excInfo)
		else:
			self._exitSuccess()
	
	def getAffected(self):
		return self.nAffected


class Data(base.MetaMixin, common.ParamMixin):
	"""is a collection of data parsed from a consistent set of sources.

	That is, Data is the instanciation of a DataDescriptor.  In consists
	of a couple of tables which may have certain roles.
	"""
	def __init__(self, dd, tables, parseOptions=common.parseNonValidating):
		base.MetaMixin.__init__(self)  # we're not a structure
		self.dd, self.parseOptions = dd, parseOptions
		self.tables = tables
		self.setMetaParent(self.dd)
		self._initParams(self.dd)

	def __iter__(self):
		for make in self.dd.makes:
			yield self.tables[make.table.id]

	@classmethod 	
	def create(cls, dd, parseOptions=common.parseNonValidating,
			connection=None):
		"""returns a new data instance for dd.

		Existing tables on the database are not touched.  To actually
		re-create them, call recrateTables.
		"""
		controlledTables = {}
		for make in dd.makes:
			controlledTables[make.table.id
				] = make.create(connection, parseOptions, tables.TableForDef)
		return cls(dd, controlledTables, parseOptions)

	@classmethod
	def drop(cls, dd, parseOptions=common.parseNonValidating, connection=None):
		"""drops all tables made by dd if necessary.
		"""
		controlledTables = {}
		for make in dd.makes:
			controlledTables[make.table.id
				] = tables.TableForDef(make.table, create=False, connection=connection)
			# The next line is necessary to have the table's beforeDrop scripts
			# exectued -- this is all far too ugly to be the right way.  I guess
			# beforeDrop really is a property of the table rather than of the
			# make, and makes and tables should have different runners...
			controlledTables[make.table.id]._runScripts = make.getRunner()
		data = cls(dd, controlledTables, parseOptions)
		data.dropTables(parseOptions)

	def dropTables(self, parseOptions):
		for t in self:
			if t.tableDef.onDisk:
				if not parseOptions.systemImport and t.tableDef.system:
					continue
				t.drop()

	def updateMeta(self, updateIndices=False):
		"""updates meta information kept in the DB on the contained tables.
		"""
		for t in self:
			if hasattr(t, "updateMeta"):
				t.updateMeta()
				if updateIndices:
					t.dropIndices()
					t.makeIndices()
		return self

	def recreateTables(self, connection):
		"""drops and recreates all table that are onDisk.

		System tables are only recreated when the systemImport parseOption
		is true.
		"""
		if self.parseOptions.updateMode or self.dd.updating:
			if self.parseOptions.dropIndices:
				for t in self:
					if t.tableDef.onDisk:
						t.dropIndices()
			return

		for t in self:
			if t.tableDef.system and not self.parseOptions.systemImport:
				continue
			if t.tableDef.onDisk:
				t.runScripts("preImport")
				t.recreate()

	def commitAll(self):
		"""commits all dependent tables.

		You only need to do this if you let the DBTables get their own
		connections, i.e., didn't create them with a connection argument.

		The method returns the data itself in order to let you do a
		commitAll().closeAll().
		"""
		for t in self:
			if t.tableDef.onDisk:
				t.commit()
		return self

	def closeAll(self):
		"""closes the connections of all dependent tables.

		No implicit commit will be done, so this implies a rollback unless
		you committed before.

		You only need to do this if you let the DBTables get their own
		connections, i.e., didn't create them with a connection argument.
		"""
		for t in self:
			if t.tableDef.onDisk:
				try:
					t.close()
				except sqlsupport.InterfaceError: # probably shared connection
					pass                            # was already closed.

	def getPrimaryTable(self):
		"""returns the table contained if there is only one, or the one
		with the role primary.

		If no matching table can be found, raise a DataError.
		"""
		if len(self.tables)==1:
			return self.tables.values()[0]
		else:
			try:
				return self.getTableWithRole("primary")
			except base.DataError: # raise more telling message
				pass
		raise base.DataError("Ambiguous request for primary table")

	def getTableWithRole(self, role):
		try:
			for t in self.tables.values():
				if t.role==role:
					return t
		except base.StructureError:
			pass
		raise base.DataError("No table with role '%s'"%role)

	def feedGrammarParameters(self, grammarParameters):
		"""feeds grammarParameters to the parmakers of all makes that have one.
		"""
# XXX TODO: remove this, it's a misfeature.  _pipeRows does all we want here
		for m in self.dd.makes:
			m.runParmakerFor(grammarParameters, self.tables[m.table.id])

	def getFeeder(self, **kwargs):
		return _DataFeeder(self, **kwargs)

	def runScripts(self, phase, **kwargs):
		for make in self.dd.makes:
			make.getRunner()(self.tables[make.table.id], phase, **kwargs)


class _EnoughRows(base.ExecutiveAction):
	"""is an internal exception that allows processSource to tell makeData
	to stop handling more sources.
	"""


def _pipeRows(srcIter, feeder, opts):
	feeder.addParameters(srcIter.getParameters())
	for srcRow in srcIter:

		if srcRow is common.FLUSH:
			feeder.flush()
			continue

		if srcIter.notify:
			base.ui.notifyIncomingRow(srcRow)
		if opts.dumpRows:
			print srcRow

		feeder.add(srcRow)
		if opts.maxRows:
			if base.ui.totalRead>=opts.maxRows:
				raise _EnoughRows


def _processSourceReal(data, source, feeder, opts):
	"""helps processSource.
	"""
	if data.dd.grammar is None:
		raise base.ReportableError("The data descriptor %s cannot be used"
			" to make data since it has no defined grammar."%data.dd.id)
	data.runScripts("newSource", sourceToken=source)
	srcIter = data.dd.grammar.parse(source, data)
	if hasattr(srcIter, "getParameters"):  # is a "normal" grammar
		data.feedGrammarParameters(srcIter.getParameters())
		try:
			_pipeRows(srcIter, feeder, opts)
		except (base.Error,base.ExecutiveAction):
			raise
		except Exception, msg:
			raise base.ui.logOldExc(
				base.SourceParseError(str(msg),
					source=utils.makeEllipsis(unicode(source), 80),
					location=srcIter.getLocator()))
	else:  # magic grammars (like those of boosters) return a callable
		srcIter(data)
	data.runScripts("sourceDone", sourceToken=source)


def processSource(data, source, feeder, opts, connection=None):
	"""ingests source into the Data instance data.

	If you pass in a connection, you can set opts.keepGoing to true
	and make the system continue importing even if a particular source 
	has caused an error.  In that case, everything contributed by
	the bad source is rolled back.
	"""
	if not opts.keepGoing:
		# simple shortcut if we don't want to recover from bad sources
		_processSourceReal(data, source, feeder, opts)
	
	else: # recover from bad sources, be more careful
		if connection is None:
			raise base.ReportableError("Can only ignore source errors"
				" with an explicit connection", hint="This is a programming error.")
		try:
			with base.savepointOn(connection):
				_processSourceReal(data, source, feeder, opts)
			feeder.flush()
		except Exception, ex:
			feeder.reset()
			if not isinstance(ex, base.ExecutiveAction):
				base.ui.notifyError("Error while importing source; changes from"
					" this source will be rolled back, processing will continue."
					" (%s)"%utils.safe_str(ex))


def makeData(dd, parseOptions=common.parseNonValidating,
		forceSource=None, connection=None, data=None, runCommit=True):
	"""returns a data instance built from dd.

	It will arrange for the parsing of all tables generated from dd's grammar.
	If connection is passed in, the the entire operation will run within a 
	single transaction within this connection.  The connection will be
	rolled back or committed depending on the success of the operation
	(unless you pass runCommit=False, in which case a successful
	import will not be committed)..

	You can pass in a data instance created by yourself in data.  This
	makes sense if you want to, e.g., add some meta information up front.
	"""
	if connection is None:
		connection = base.getDBConnection("admin")
	if data is None:
		res = Data.create(dd, parseOptions, connection=connection)
	else:
		res = data
	res.recreateTables(connection)
	
	feederOpts = {"batchSize": parseOptions.batchSize, "runCommit": runCommit}
	if dd.grammar and dd.grammar.isDispatching:
		feederOpts["dispatched"] = True

	with res.getFeeder(connection=connection, **feederOpts) as feeder:
		if forceSource is None:
			for source in dd.iterSources(connection):
				try:
					processSource(res, source, feeder, parseOptions, connection)
				except _EnoughRows:
					base.ui.notifyWarning("Source hit import limit, import aborted.")
					break
				except base.SkipThis:
					continue
		else:
			processSource(res, forceSource, feeder, parseOptions, connection)

	if runCommit:
		res.commitAll()
	res.nAffected = feeder.getAffected()

	if parseOptions.buildDependencies:
		makeDependentsFor([dd], parseOptions, connection)

	return res


def makeDependentsFor(dds, parseOptions, connection):
	"""rebuilds all data dependent on one of the DDs in the dds sequence.
	"""
	edges, seen = set(), set()

	def gatherDependents(dd):
		for dependentId in dd.dependents:
			try:
				dependentDD = base.resolveId(dd.rd, dependentId)
				edges.add((dd, dependentDD))
				if dependentDD not in seen:
					seen.add(dependentDD)
					gatherDependents(dependentDD)
			except (base.StructureError, base.NotFoundError), msg:
				base.ui.notifyWarning("Ignoring dependent %s of %s (%s)"%(
					dependentId, dd.id, unicode(msg)))

	for dd in dds:
		gatherDependents(dd)

	if parseOptions.buildDependencies:
		parseOptions = parseOptions.change(buildDependencies=False)
	
	try:
		buildSequence = utils.topoSort(edges)
	except ValueError, ex:
		raise utils.logOldExc(base.ReportableError("Could not sort"
			" dependent DDs topologically (use  --hints to learn more)", 
			hint="This is most likely because there's a cyclic dependency."
			" Please check your dependency structure.  The original message"
			" is: %s"%utils.safe_str(ex)))

	# note that the original DD is the first item in the build sequence,
	# and we don't want to re-make it here
	for dd in buildSequence[1:]:
		makeData(dd, parseOptions=parseOptions, connection=connection)


def makeDataById(ddId, parseOptions=common.parseNonValidating,
		connection=None, inRD=None):
	"""returns the data set built from the DD with ddId (which must be
	fully qualified).
	"""
	dd = base.resolveId(inRD, ddId)
	return makeData(dd, parseOptions=parseOptions, connection=connection)


def wrapTable(table, rdSource=None):
	"""returns a Data instance containing only table (or table if it's already
	a data instance).

	If table has no rd, you must pass rdSource, which must be an object having
	and rd attribute (rds, tabledefs, etc, work).
	"""
	if isinstance(table, Data):
		return table
	if rdSource is None:
		rd = table.tableDef.rd
	elif hasattr(rdSource, "rd"):
		rd = rdSource.rd
	else:
		raise TypeError("Invalid RD source: %s"%rdSource)
	newDD = MS(rscdef.DataDescriptor, makes=[
		MS(rscdef.Make, table=table.tableDef, rowmaker=None)], parent_=rd)
	if rdSource:
		newDD.adopt(table.tableDef)
	res = Data(newDD, tables={table.tableDef.id: table})
	res.meta_ = table.meta_
	return res
