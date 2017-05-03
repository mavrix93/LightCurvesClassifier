"""
Common error handling facilities for user interface components.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import re
import sys
import textwrap
import traceback

from gavo import base
from gavo import grammars
from gavo import rsc
from gavo import utils


class _Reformatter(object):
	"""A helper class for reformatMessage.
	"""
	verbatimRE = re.compile("\s")

	def __init__(self):
		self.inBuffer, self.outBuffer = [], []

	def flush(self):
		if self.inBuffer:
			self.outBuffer.append(textwrap.fill("\n".join(self.inBuffer), 
				break_long_words=False))
			self.inBuffer = []

	def feed(self, line):
		if self.verbatimRE.match(line):
			self.flush()
			self.outBuffer.append(line)
		elif not line.strip():
			self.flush()
			self.outBuffer.append("")
		else:
			self.inBuffer.append(line)
	
	def get(self):
		self.flush()
		return "\n".join(self.outBuffer)

	def feedLines(self, lines):
		for l in lines:
			self.feed(l)


def reformatMessage(msg):
	"""reflows message using textwrap.fill.

	Lines starting with whitespace will not be wrapped.
	"""
	r = _Reformatter()
	r.feedLines(msg.split("\n"))
	return r.get()


def outputError(message):
	sys.stderr.write(message.encode(
		base.getConfig("ui", "outputEncoding"), "replace"))


def raiseAndCatch(opts=None, output=outputError):
	"""raises the current exception and tries write a good error message 
	for it.

	opts can be an object with some attribute (read the source); this
	usually comes from user.cli's main.

	output must be a function accepting a single string, defaulting to
	something just encoding the string for the output found and dumping
	it to stderr.

	The function returns a suggested return value for the whole program.
	"""
# Messages are reformatted by reformatMessage (though it's probably ok
# to just call output(someString) to write to the user directly.
#
# To write messages, append strings to the messages list.  An empty string
# would produce a paragraph.  Append unicode or ASCII.
	retval = 1
	messages = []
	try:
		raise
	except SystemExit, msg:
		retval = msg.code
	except KeyboardInterrupt:
		retval = 2
	except grammars.ParseError, msg:
		if msg.location:
			messages.append("Parse error at %s: %s"%(msg.location, 
				utils.safe_str(msg)))
		else:
			messages.append("Parse error: %s"%utils.safe_str(msg))
		if msg.record:
			messages.append("")
			messages.append("Offending input was:\n")
			messages.append(repr(msg.record)+"\n")

	except base.SourceParseError, msg:
		messages.append("While parsing source %s, near %s:\n"%(
			msg.source, msg.location))
		messages.append((msg.msg+"\n").decode("iso-8859-1", "ignore"))
		if msg.offending:
			messages.append("Offending literal: %s\n"%repr(msg.offending))

	except base.BadCode, msg:
		messages.append("Bad user %s:\n"%msg.codeType)
		messages.append(msg.code)
		messages.append("User %s caused an error: %s\n"%(
			msg.codeType, str(msg.origExc)))
		if msg.pos:
			messages.append("(At %s)"%msg.pos)

	except rsc.DBTableError, msg:
		messages.append("While building table %s: %s"%(msg.qName,
			msg))
	
	except base.MetaError, msg:
		messages.append("While working on metadata of '%s': %s"%(
			str(msg.carrier),
			str(msg.__class__.__name__)))
		if msg.key is not None:
			messages.append("-- key %s --"%msg.key)
		messages.append(utils.safe_str(msg))

	except (base.ValidationError, base.ReportableError, 
			base.LiteralParseError, base.StructureError, base.NotFoundError,
			base.MetaValidationError), msg:
	
		if not getattr(msg, "posInMsg", False):
			if getattr(msg, "inFile", None):
				messages.append("In %s:"%msg.inFile)
			elif getattr(msg, "pos", None):
				messages.append("At or near %s:"%msg.pos)

		if getattr(msg, "row", None):
			messages.append("Row %s"%str(msg.row))
		messages.append(str(msg).decode("iso-8859-1", "ignore"))

	except Exception, msg:
		if hasattr(msg, "excRow"):
			messages.append("Snafu in %s, %s\n"%(msg.excRow, msg.excCol))
			messages.append("")
		messages.append("Oops.  Unhandled exception %s.\n"%msg.__class__.__name__)
		messages.append("Exception payload: %s"%utils.safe_str(msg))
		base.ui.notifyError("Uncaught exception at toplevel")

	if getattr(opts, "enablePDB", False):
		raise
	elif getattr(opts, "alwaysTracebacks", False):
			traceback.print_exc()
	if messages:
		errTx = utils.safe_str("*** Error: "+"\n".join(messages))
		output(reformatMessage(errTx)+"\n")
	if getattr(opts, "showHints", True) and getattr(msg, "hint", None):
		output(reformatMessage("Hint: "+msg.hint)+"\n")

	return retval


def bailOut():
	"""A fake cli operation just raising exceptions.

	This is mainly for testing and development.
	"""
	if len(sys.argv)<2:
		raise ValueError("Too short")
	arg = sys.argv[0]
	if arg=="--help":
		raise base.Error("Hands off this.  For Developers only")
