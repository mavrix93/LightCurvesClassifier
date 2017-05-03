"""
Helper classes for the DaCHS' unit tests.

WARNING: This messes up some global state.  DO NOT import into modules
doing regular work.  testtricks is the module for that kind for stuff.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from __future__ import with_statement

import BaseHTTPServer
import contextlib
import gc
import os
import re
import subprocess
import sys
import threading
import traceback
import unittest
import warnings
from cStringIO import StringIO


# This sets up a test environment of the DaCHS software.
#
# To make this work, the current user must be allowed to run
# createdb (in practice, you should have done something like
#
# sudo -u postgres -s `id -nu`
#
# You should be able to tear both ~/_gavo_test and the database 
# down, and this should automatically recreate everything.  That's 
# an integration test for DaCHS, too.
#
# This must be run before anything else from gavo is imported because
# it manipulates the config stuff; this, in turn, runs as soon as
# base is imported.

# The following forces tests to be run from the tests directory.  
# Reasonable, I'd say.
#
# All the custom setup can be suppressed by setting a GAVO_OOTTEST
# env var before importing this.  That's for "out of tree test"
# and is used by the relational registry "unit" tests (and possibly
# others later).
if "GAVO_OOTTEST" in os.environ:
	from gavo import base

else:
	TEST_BASE = os.getcwd()
	originalEnvironment = os.environ.copy()
	os.environ["GAVOCUSTOM"] = "/invalid"
	os.environ["GAVOSETTINGS"] = os.path.join(TEST_BASE, 
		"test_data", "test-gavorc")
	if not os.path.exists(os.environ["GAVOSETTINGS"]):
		warnings.warn("testhelpers imported from non-test directory.  This"
			" is almost certainly not what you want (or set GAVO_OOTTEST).")

	from gavo import base #noflake: import above is conditional
	dbname = "dachstest"
	if not os.path.exists(base.getConfig("rootDir")):
		from gavo.user import initdachs
		try:
			dsn = initdachs.DSN(dbname)
			subprocess.call(["createdb", "--template=template0", 
				"--encoding=UTF-8", "--locale=C", dbname])
			initdachs.createFSHierarchy(dsn, "test")

			with open(os.path.join(base.getConfig("configDir"), "defaultmeta.txt"),
					"a") as f:
				f.write("!organization.description: Mein w\xc3\xbcster Club\n")
				f.write("!contact.email: invalid@whereever.else\n")
			from gavo.base import config
			config.makeFallbackMeta(reload=True)

			os.symlink(os.path.join(TEST_BASE, "test_data"),
				os.path.join(base.getConfig("inputsDir"), "data"))
			os.rmdir(os.path.join(base.getConfig("inputsDir"), "__system"))
			os.symlink(os.path.join(TEST_BASE, "test_data", "__system"),
				os.path.join(base.getConfig("inputsDir"), "__system"))
			os.mkdir(os.path.join(base.getConfig("inputsDir"), "test"))
			initdachs.initDB(dsn)

			from gavo.registry import publication
			from gavo import rsc
			from gavo import rscdesc #noflake: caches registration
			from gavo import base
			publication.updateServiceList([base.caches.getRD("//services")])

			# Import some resources necessary in trial tests
			rsc.makeData(
				base.caches.getRD("data/ssatest").getById("test_import"))
		except:
			traceback.print_exc()
			sys.stderr.write("Creation of test environment failed.  Remove %s\n"
				" before trying again.\n"%(base.getConfig("rootDir")))
			sys.exit(1)

	else:
		# run any pending upgrades (that's a test for them, too... of sorts)
		from gavo.user import upgrade
		upgrade.upgrade()

	# the following only needs to be set correctly if you run 
	# twisted trial-based tests
	testsDir = TEST_BASE



from gavo.imp import testresources
from gavo.imp.testresources import TestResource  #noflake: exported name
from gavo.helpers.testtricks import XSDTestMixin, testFile #noflake: exp. name

# Here's the deal on TestResource: When setting up complicated stuff for
# tests (like, a DB table), define a TestResource for it.  Override
# the make(dependents) method returning something and the clean(res) 
# method to destroy whatever you created in make().
#
# Then, in VerboseTests, have a class attribute
# resource = [(name1, res1), (name2, res2)]
# giving attribute names and resource *instances*.
# There's an example in adqltest.py
# 
# If you use this and you have a setUp of your own, you *must* call 
# the superclass's setUp method.


class ForkingSubprocess(subprocess.Popen):
	"""A subprocess that doesn't exec but fork.
	"""
	def _execute_child(self, args, executable, preexec_fn, close_fds,
						   cwd, env, universal_newlines,
						   startupinfo, creationflags, shell,
						   p2cread, p2cwrite,
						   c2pread, c2pwrite,
						   errread, errwrite):
# stolen from 2.5 subprocess.  Unfortunately, I can't just override the
# exec action.
			"""Execute program (POSIX version)"""

			if isinstance(args, basestring):
				args = [args]
			else:
				args = list(args)

			if shell:
				args = ["/bin/sh", "-c"] + args

			if executable is None:
				executable = args[0]

			gc_was_enabled = gc.isenabled()
			# Disable gc to avoid bug where gc -> file_dealloc ->
			# write to stderr -> hang.  http://bugs.python.org/issue1336
			gc.disable()
			try:
				self.pid = os.fork()
			except:
				if gc_was_enabled:
					gc.enable()
				raise
			self._child_created = True
			if self.pid == 0:
				# Child
				try:
					# Close parent's pipe ends
					if p2cwrite:
						os.close(p2cwrite)
					if c2pread:
						os.close(c2pread)
					if errread:
						os.close(errread)

					# Dup fds for child
					if p2cread:
						os.dup2(p2cread, 0)
					if c2pwrite:
						os.dup2(c2pwrite, 1)
					if errwrite:
						os.dup2(errwrite, 2)

					# Close pipe fds.  Make sure we don't close the same
					# fd more than once, or standard fds.
					if p2cread and p2cread not in (0,):
						os.close(p2cread)
					if c2pwrite and c2pwrite not in (p2cread, 1):
						os.close(c2pwrite)
					if errwrite and errwrite not in (p2cread, c2pwrite, 2):
						os.close(errwrite)

					# Close all other fds, if asked for
					if close_fds:
						self._close_fds()

					if cwd is not None:
						os.chdir(cwd)

					if preexec_fn:
						apply(preexec_fn)
				
					exitcode = 0
					sys.argv = args
					try:
						executable()
					except SystemExit, ex:
						exitcode = ex.code
					sys.stderr.close()
					sys.stdout.close()
					os._exit(exitcode)

				except:
					traceback.print_exc()
				# This exitcode won't be reported to applications, so it
				# really doesn't matter what we return.
				os._exit(255)

			# Parent
			if gc_was_enabled:
				gc.enable()
			if p2cread and p2cwrite:
				os.close(p2cread)
			if c2pwrite and c2pread:
				os.close(c2pwrite)
			if errwrite and errread:
				os.close(errwrite)


class VerboseTest(testresources.ResourcedTestCase):
	"""A TestCase with a couple of convenient assert methods.
	"""
	def assertEqualForArgs(self, callable, result, *args):
		self.assertEqual(callable(*args), result, 
			"Failed for arguments %s.  Expected result is: %s, result found"
			" was: %s"%(str(args), repr(result), repr(callable(*args))))

	def assertRaisesVerbose(self, exception, callable, args, msg):
		try:
			callable(*args)
		except exception:
			return
		except:
			raise
		else:
			raise self.failureException(msg)

	def assertRaisesWithMsg(self, exception, errMsg, callable, args, msg=None,
			**kwargs):
		try:
			callable(*args, **kwargs)
		except exception, ex:
			if str(ex)!=errMsg:
				raise self.failureException(
					"Expected %r, got %r as exception message"%(errMsg, str(ex)))
		except:
			raise
		else:
			raise self.failureException(msg or "%s not raised"%exception)

	def assertRuns(self, callable, args, msg=None):
		try:
			callable(*args)
		except Exception, ex:
			raise self.failureException("Should run, but raises %s (%s) exception"%(
				ex.__class__.__name__, str(ex)))

	def assertAlmostEqualVector(self, first, second, places=7, msg=None):
		try:
			for f, s in zip(first, second):
				self.assertAlmostEqual(f, s, places)
		except AssertionError:
			if msg:
				raise AssertionError(msg)
			else:
				raise AssertionError("%s != %s within %d places"%(
					first, second, places))

	def assertEqualToWithin(self, a, b, ratio=1e-7, msg=None):
		"""asserts that abs(a-b/(a+b))<ratio.
		
		If a+b are an underflow, we error out right now.
		"""
		if msg is None:
			msg = "%s != %s to within %s of the sum"%(a, b, ratio)
		denom = abs(a+b)
		self.failUnless(abs(a-b)/denom<ratio, msg)

	def assertOutput(self, toExec, argList, expectedStdout=None, 
			expectedStderr="", expectedRetcode=0, input=None,
			stdoutStrings=None):
		"""checks that execName called with argList has the given output and return
		value.

		expectedStdout and expectedStderr can be functions.  In that case,
		the output is passed to the function, and an assertionError is raised
		if the functions do not return true.

		The 0th argument in argList is automatically added, only pass "real"
		command line arguments.

		toExec may also be a zero-argument python function.  In that case, the
		process is forked and the function is called, with sys.argv according to
		argList.  This helps to save startup time for python main functions.
		"""
		for name in ["output.stderr", "output.stdout"]:
			try:
				if os.path.exists(name) and os.path.getsize(name)>0:
					print open(name).read()
				os.unlink(name)
			except os.error:
				pass

		if isinstance(toExec, basestring):
			p = subprocess.Popen([toExec]+argList, executable=toExec, 
				stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
		else:
			p = ForkingSubprocess(["test harness"]+argList, executable=toExec, 
				stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
		out, err = p.communicate(input=input)
		retcode = p.wait()

		try:
			self.assertEqual(expectedRetcode, retcode)

			if isinstance(expectedStderr, basestring):
				self.assertEqual(err, expectedStderr)
			else:
				self.failUnless(expectedStderr(err))
		except AssertionError:
			with open("output.stdout", "w") as f:
				f.write(out)
			with open("output.stderr", "w") as f:
				f.write(err)
			raise

		try:
			if isinstance(expectedStdout, basestring):
				self.assertEqual(out, expectedStdout)
			elif expectedStdout is not None:
				self.failUnless(expectedStdout(out))
			if stdoutStrings:
				for s in stdoutStrings:
					self.failIf(s not in out, "%s missing"%s)
		except AssertionError:
			with open("output.stdout", "w") as f:
				f.write(out)
			raise


_xmlJunkPat = re.compile("|".join([
	'(xmlns(:[a-z0-9]+)?="[^"]*"\s*)',
	'((frame_|coord_system_)?id="[^"]*")',
	'(xsi:schemaLocation="[^"]*"\s*)']))


def cleanXML(aString):
	"""removes IDs and some other detritus from XML literals.

	The result will be invalid XML, and all this assumes the fixed-prefix
	logic of the DC software.

	For new tests, you should just getXMLTree and XPath tests.
	"""
	return re.sub("\s+", " ", _xmlJunkPat.sub('', aString)).strip(
		).replace(" />", "/>").replace(" >", ">")


def _nukeNamespaces(xmlString):
	nsCleaner = re.compile('^(</?)(?:[a-z0-9]+:)')
	return re.sub("(?s)<[^>]*>", 
		lambda mat: nsCleaner.sub(r"\1", mat.group()),
		re.sub('xmlns="[^"]*"', "", xmlString))


def getXMLTree(xmlString, debug=False):
	"""returns an libxml2 etree for xmlString, where, for convenience,
	all namespaces on elements are nuked.

	The libxml2 etree lets you do xpath searching using the xpath method.
	"""
	from lxml import etree as lxtree
	tree = lxtree.fromstring(_nukeNamespaces(xmlString))
	if debug:
		lxtree.dump(tree)
	return tree


def printFormattedXML(xmlString):
	"""pipes xmlString through xmlstarlet fo, pretty-printing it.
	"""
	p = subprocess.Popen("xmlstarlet fo".split(), stdin=subprocess.PIPE)
	p.stdin.write(xmlString)
	p.stdin.close()
	p.wait()


class SamplesBasedAutoTest(type):
	"""A metaclass that builds tests out of a samples attribute of a class.

	To use this, give the class a samples attribute containing a sequence
	of anything, and a _runTest(sample) method receiving one item of
	that sequence.

	The metaclass will create one test<n> method for each sample.
	"""
	def __new__(cls, name, bases, dict):
		for sampInd, sample in enumerate(dict.get("samples", ())):
			def testFun(self, sample=sample):
				self._runTest(sample)
			dict["test%02d"%sampInd] = testFun
		return type.__new__(cls, name, bases, dict)


def getTestRD(id="test.rd"):
	from gavo import rscdesc  #noflake: import above is conditional
	from gavo import base
	return base.caches.getRD("data/%s"%id)


def getTestTable(tableName, id="test.rd"):
	return getTestRD(id).getTableDefById(tableName)


def getTestData(dataId):
	return getTestRD().getDataById(dataId)


def captureOutput(callable, args=(), kwargs={}):
	"""runs callable(*args, **kwargs) and captures the output.

	The function returns a tuple of return value, stdout output, stderr output.
	"""
	realOut, realErr = sys.stdout, sys.stderr
	sys.stdout, sys.stderr = StringIO(), StringIO()
	try:
		retVal = 2 # in case the callable sys.exits
		try:
			retVal = callable(*args, **kwargs)
		except SystemExit:
			# don't terminate just because someone thinks it's a good idea
			pass
	finally:
		outCont, errCont = sys.stdout.getvalue(), sys.stderr.getvalue()
		sys.stdout, sys.stderr = realOut, realErr
	return retVal, outCont, errCont


def trialMain(testClass):
	from twisted.trial import runner
	from twisted.scripts import trial as script
	config = script.Options()
	config.parseOptions()
	trialRunner = script._makeRunner(config)
	if len(sys.argv)>1:
		suite = runner.TestSuite()
		for t in sys.argv[1:]:
			suite.addTest(testClass(t))
	else:
		sys.argv.append(sys.argv[0])
		config.parseOptions()
		suite = script._getSuite(config)
	trialRunner.run(suite)


def getServerInThread(data, onlyOnce=False):
	"""runs a server in a thread and returns  thread and base url.

	onlyOnce will configure the server such that it destroys itself
	after having handled one request.  The thread would still need
	to be joined.

	So, better use the DataServer context manager.
	"""
	class Handler(BaseHTTPServer.BaseHTTPRequestHandler):
		def do_GET(self):
			self.wfile.write(data)
		do_POST = do_GET
	
	port = 34000
	httpd = BaseHTTPServer.HTTPServer(('', port), Handler)

	if onlyOnce:
		serve = httpd.handle_request
	else:
		serve = httpd.serve_forever

	t = threading.Thread(target=serve)
	t.setDaemon(True)
	t.start()
	return httpd, t, "http://localhost:%s"%port


@contextlib.contextmanager
def DataServer(data):
	"""a context manager for briefly running a web server returning data.

	This yields the base URL the server is listening on.
	"""
	httpd, t, baseURL = getServerInThread(data)

	yield baseURL

	httpd.shutdown()
	t.join(10)


def main(testClass, methodPrefix=None):
	from gavo import base
	
	if os.environ.get("GAVO_LOG")!="no":
		base.DEBUG = True
		from gavo.user import logui
		logui.LoggingUI(base.ui)

	try:
		# two args: first one is class name, locate it in caller's globals
		# and ignore anything before any dot for cut'n'paste convenience
		if len(sys.argv)>2:
			className = sys.argv[-2].split(".")[-1]
			testClass = getattr(sys.modules["__main__"], className)
		
		# one arg: test method prefix on testClass
		if len(sys.argv)>1:
			suite = unittest.makeSuite(testClass, methodPrefix or sys.argv[-1],
				suiteClass=testresources.OptimisingTestSuite)
		else:  # Zero args, emulate unittest.run behaviour
			suite = testresources.TestLoader().loadTestsFromModule(
				sys.modules["__main__"])

		runner = unittest.TextTestRunner(
			verbosity=int(os.environ.get("TEST_VERBOSITY", 1)))
		runner.run(suite)
	except (SystemExit, KeyboardInterrupt):
		raise
	except:
		base.showHints = True
		from gavo.user import errhandle
		traceback.print_exc()
		errhandle.raiseAndCatch(base)
