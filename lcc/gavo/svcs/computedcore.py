"""
Cores wrapping some external program.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import os
import subprocess
import threading
from cStringIO import StringIO

from gavo import base
from gavo import rsc
from gavo import rscdef
from gavo.svcs import core
from gavo.svcs import outputdef


argMFRegistry = base.ValueMapperFactoryRegistry()
_registerArgMF = argMFRegistry.registerFactory

def _defaultMapperFactory(colProps):
	def coder(val):
		return str(val)
	return coder
_registerArgMF(_defaultMapperFactory)

datetimeDbTypes = set(["timestamp", "date", "time"])
def _datetimeMapperFactory(colProps):
	if colProps["dbtype"] not in datetimeDbTypes:
		return
	def coder(val):
		if val:
			return val.strftime("%Y-%m-%dT%H:%M:%S")
		return "None"
	return coder
_registerArgMF(_datetimeMapperFactory)


class ComputedCore(core.Core):
	"""A core wrapping external applications.
	
	ComputedCores wrap command line tools taking command line arguments,
	reading from stdin, and outputting to stdout.

	The command line arguments are taken from the inputTable's parameters,
	stdin is created by serializing the inputTable's rows like they are 
	serialized for with the TSV output, except only whitespace is entered 
	between the values.
	
	The output is the primary table of parsing the program's output with
	the data child.
	"""
	name_ = "computedCore"

	_computer = rscdef.ResdirRelativeAttribute("computer",
		default=base.Undefined, description="Resdir-relative basename of"
			" the binary doing the computation.  The standard rules for"
			" cross-platform binary name determination apply.",
			copyable=True)
	_resultParse = base.StructAttribute("resultParse",
		description="Data descriptor to parse the computer's output.",
		childFactory=rscdef.DataDescriptor, copyable=True)

	def start_(self, ctx, name, value):
		if name=="outputTable":
			raise base.StructureError("Cannot define a computed core's"
				" output table.", hint="Computed cores have their output"
				" defined by the primary table of resultParse.")
		return core.Core.start_(self, ctx, name, value)

	def completeElement(self, ctx):
		if self.resultParse:
			self._outputTable.feedObject(self,
				outputdef.OutputTableDef.fromTableDef(
					self.resultParse.getPrimary(), ctx))
		self._completeElementNext(ComputedCore, ctx)

	def _feedInto(self, data, destFile):
		"""writes data into destFile from a thread.

		This is done to cheaply avoid deadlocks.  Ok, I'll to a select loop
		piping directly into the grammar one of these days.
		"""
		def writeFile():
			destFile.write(data)
			destFile.close()
		writeThread = threading.Thread(target=writeFile)
		writeThread.setDaemon(True)
		writeThread.start()
		return writeThread

	def _getArgs(self, inputTable):
		args = [base.getBinaryName(self.computer)]
		for par in inputTable.iterParams():
			if par.content_ is base.NotGiven:
				raise base.ValidationError("Command line argument %s must not"
					" be undefined"%par.name, par.name, base.NotGiven)
			args.append(par.content_)
		return args

	def _getInput(self, inputTable):
		t = inputTable
		names = [c.name for c in t.tableDef]
		res = []
		for row in base.SerManager(t, mfRegistry=argMFRegistry).getMappedValues():
			res.append(" ".join([row[name] for name in names]))
		return str("\n".join(res))

	def _runAndCapture(self, inputTable):
# if we wanted to get really fancy, it shouldn't be hard to pipe that stuff
# directly into the grammar.
		pipe = subprocess.Popen(self._getArgs(inputTable), 2**16, 
			stdin=subprocess.PIPE, stdout=subprocess.PIPE, close_fds=True,
			cwd=os.path.dirname(self.computer))
		writeThread = self._feedInto(self._getInput(inputTable), pipe.stdin)
		data = pipe.stdout.read()
		pipe.stdout.close()
		writeThread.join(0.1)
		retcode = pipe.wait()
		if retcode!=0:
			raise base.ValidationError("The subprocess %s returned %s.  This"
				" indicates an external executable could not be run or failed"
				" with your parameters.  You should probably report this to the"
				" operators."%(os.path.basename(self.computer), retcode),
				"query")
		return data

	def run(self, service, inputTable, queryMeta):
		"""starts the computing process if this is a computed data set.
		"""
		res = rsc.makeData(self.resultParse,
			forceSource=StringIO(self._runAndCapture(inputTable)))
		return res.getPrimaryTable()
