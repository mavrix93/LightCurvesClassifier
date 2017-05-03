"""
Resource mixins.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import threading

from gavo import base
from gavo.base import activetags
from gavo.rscdef import procdef


__docformat__ = "restructuredtext en"


class ProcessEarly(procdef.ProcApp):
	"""A code fragment run by the mixin machinery when the structure
	being worked on is being finished.

	Within processEarly, you can access:

	- Access the structure the mixin is applied to as "substrate"
	- The mixin parameters as "mixinPars"
	- The parse context as "context"

	(the context is particularly handy for context.resolveId)
	"""
	name_ = "processEarly"
	formalArgs = "context, substrate, mixinPars"


class ProcessLate(procdef.ProcApp):
	"""A code fragment run by the mixin machinery when the parser parsing
	everything exits.

	Access the structure mixed in as "substrate", the root structure of
	the whole parse tree as root, and the context that is just about
	finishing as context.
	"""
	name_ = "processLate"
	formalArgs = "substrate, root, context"


class MixinPar(procdef.RDParameter):
	"""A parameter definition for mixins.  
	
	The (optional) body provides a default for the parameter.
	"""
	name_ = "mixinPar"

	_expr = base.DataContent(description="The default for the parameter."
		" A __NULL__ here does not directly mean None/NULL, but since the"
		" content will frequently end up in attributes, it will ususally work"
		" as presetting None."
		" An empty content means a non-preset parameter, which must be filled"
		" in applications.  The magic value __EMPTY__ allows presetting an"
		" empty string.",
		# mixinPars must not evaluate __NULL__; this stuff ends up in
		# macro expansions, where an actual None is not desirable.
		null=None,
		copyable=True, strip=True, default=base.NotGiven)

	def validate(self):
		self._validateNext(MixinPar)
		if len(self.key)<2:
			raise base.LiteralParseError("name", self.key, hint="Names of"
				" mixin parameters must have at least two characters (since"
				" they are exposed as macros")


class LateEvents(activetags.EmbeddedStream):
	"""An event stream played back by a mixin when the substrate is being
	finalised (but before the early processing).
	"""
	name_ = "lateEvents"


class MixinDef(activetags.ReplayBase):
	"""A definition for a resource mixin.

	Resource mixins are resource descriptor fragments typically rooted
	in tables (though it's conceivable that other structures could
	grow mixin attributes as well).

	They are used to define and implement certain behaviours components of
	the DC software want to see:

	- products want to be added into their table, and certain fields are required
		within tables describing products
	- tables containing positions need some basic machinery to support scs.
	- siap needs quite a bunch of fields

	Mixins consist of events that are played back on the structure
	mixing in before anything else happens (much like original) and
	two procedure definitions, viz, processEarly and processLate.
	These can access the structure that has the mixin as substrate.

	processEarly is called as part of the substrate's completeElement
	method.  processLate is executed just before the parser exits.  This
	is the place to fix up anything that uses the table mixed in.  Note,
	however, that you should be as conservative as possible here -- you
	should think of DC structures as immutable as long as possible.

	Programmatically, you can check if a certain table mixes in 
	something by calling its mixesIn method.

	Recursive application of mixins, even to seperate objects, will deadlock.
	"""
	name_ = "mixinDef"

	_doc = base.UnicodeAttribute("doc", description="Documentation for"
		" this mixin", strip=False)
	_events = base.StructAttribute("events", 
		childFactory=activetags.EmbeddedStream,
		description="Events to be played back into the structure mixing"
		" this in at mixin time.", copyable=True,
		default=base.NotGiven)
	_lateEvents = base.StructAttribute("lateEvents", 
		childFactory=LateEvents,
		description="Events to be played back into the structure mixing"
		" this in at completion time.", copyable=True,
		default=base.NotGiven)
	_processEarly = base.StructAttribute("processEarly", 
		default=None, 
		childFactory=ProcessEarly,
		description="Code executed at element fixup.",
		copyable=True)
	_processLate = base.StructAttribute("processLate", 
		default=None, 
		childFactory=ProcessLate,
		description="Code executed resource fixup.",
		copyable=True)
	_pars = base.StructListAttribute("pars",
		childFactory=MixinPar,
		description="Parameters available for this mixin.",
		copyable=True)
	_original = base.OriginalAttribute()

	def completeElement(self, ctx):
		# we want to double-expand macros in mixins.  Thus, reset all
		# value/expanded events to plain values
		if self.events:
			self.events.unexpandMacros()
		if self.lateEvents:
			self.lateEvents.unexpandMacros()

		# This lock protects against multiple uses of applyTo.  This is
		# necessary because during replay, we have macroExpansions and
		# macroParent reflect a concrete application's context.
		self.applicationLock = threading.Lock()
		self._completeElementNext(MixinDef, ctx)

	def _defineMacros(self, fillers, destination):
		"""creates attributes macroExpansions and parentMacroPackage used by
		execMacros.

		Within mixins, you can use macros filled by mixin parameters or
		expanded by the substrate.  This information is local to a concrete
		mixin application.  Hence, applyTo calls this method, and the
		attributes created are invalid for any subsequent or parallel applyTo
		calls.  Therefore, applyTo acquires the applicationLock before
		calling this.
		"""
		self.parentMacroPackage = None
		if hasattr(destination, "execMacro"):
			self.parentMacroPackage = destination

		self.macroExpansions = {}
		for p in self.pars:
			if p.key in fillers:
				self.macroExpansions[p.key] = fillers.pop(p.key)
			elif p.isDefaulted():
				self.macroExpansions[p.key] = p.content_
			else:
				raise base.StructureError("Mixin parameter %s mandatory"%p.key)
		if fillers:
			raise base.StructureError("The attribute(s) %s is/are not allowed"
				" on this mixin"%(",".join(fillers)))

	def execMacro(self, macName, args):
		if macName in self.macroExpansions:
			return self.macroExpansions[macName]
		try:
			if self.parentMacroPackage:
				return self.parentMacroPackage.execMacro(macName, args)
		except base.MacroError:
			raise base.MacroError(
				"No macro \\%s available in this mixin or substrate."%(macName), 
				macName)

	def applyTo(self, destination, ctx, fillers={}):
		"""replays the stored events on destination and arranges for processEarly
		and processLate to be run.
		"""
		with self.applicationLock:
			self._defineMacros(fillers.copy(), destination)
			if self.events:
				self.replay(self.events.events_, destination, ctx)

			if self.processEarly is not None:
				self.processEarly.compile(destination)(ctx, destination, 
					self.macroExpansions)

			if self.processLate is not None:
				def procLate(rootStruct, parseContext):
					self.processLate.compile(destination)(
						destination, rootStruct, parseContext)
				ctx.addExitFunc(procLate)

		if self.lateEvents:
			origComplete = destination.completeElement
			def newComplete(ctx):
				with self.applicationLock:
					self._defineMacros(fillers.copy(), destination)
					self.replay(self.lateEvents.events_, destination, ctx)
				origComplete(ctx)
			destination.completeElement = newComplete

	def applyToFinished(self, destination):
		"""applies the mixin to an object already parsed.

		Late callbacks will only be executed if destination has an rd
		attribute; if that is the case, this rd's idmap will be amended
		with anything the mixin comes up with.
		"""
		rd = None
		if hasattr(destination, "rd"):
			rd = destination.rd

		ctx = base.ParseContext()
		if rd is not None:
			ctx.idmap = destination.rd.idmap
		self.applyTo(destination, ctx)

		# we don't keep the application lock for this; applyToFinished
		# is more of a debugging thing, so we don't worry too much.
		if self.lateEvents:
			self.replay(self.lateEvents.events_, destination, ctx)

		if rd is not None:
			ctx.runExitFuncs(rd)


class _MixinParser(base.Parser):
	"""A parser for structured mixin references.

	These can contain attribute definitions for any parameter of the
	mixin referenced.
	"""
	def __init__(self, parent, parentAttr):
		self.parent, self.parentAttr = parent, parentAttr
		self.fillers = {}
		self.curName = None  # this is non-None while parsing a child element
	
	def start_(self, ctx, name, value):
		if self.curName is not None:
			raise base.StructureError("%s elements cannot have %s children in"
				" mixins."%(self.curName, name))
		self.curName = name
		return self
	
	def value_(self, ctx, name, value):
		if name=="content_":
			if self.curName:
				self.fillers[self.curName] = value
			else:
				self.fillers["mixin name"] = value.strip()
		else:
			self.fillers[name] = value
		return self
	
	def end_(self, ctx, name, value):
		if self.curName:  # end parsing parameter binding
			self.curName = None
			return self
		else: # end of mixin application, run the mixin and hand control back to
		      # mixin parent
			if "mixin name" not in self.fillers:
				raise base.StructureError("Empty mixin children not allowed")
			mixinRef = self.fillers.pop("mixin name")
			self.parentAttr.feed(ctx, self.parent, mixinRef, fillers=self.fillers)
			return self.parent


class MixinAttribute(base.SetOfAtomsAttribute):
	"""An attribute defining a mixin.

	This currently is only offered on tables, though in principle we could
	have it anywhere now, but we'd want some compatibility checking
	then.

	This is never copyable since this would meaning playing the same
	stuff into an object twice.

	This means trouble for magic scripts (in particular processLate); e.g.,
	if you copy a table mixing in products, the data element for that table
	will not receive the product table.  Goes to show the whole product
	mess is ugly and needs a good idea.
	"""
	def __init__(self, **kwargs):
		kwargs["itemAttD"] = base.UnicodeAttribute("mixin", strip=True)
		kwargs["description"] = kwargs.get("description", 
			"Reference to a mixin this table should contain; you can"
			" give mixin parameters as attributes or children.")
		kwargs["copyable"] = False
		base.SetOfAtomsAttribute.__init__(self, "mixin", **kwargs)

	def _insertCompleter(self, instance, completerFunc):
		"""arranges completerFunc to be called as part of instance's 
		completeElement callbacks.
		"""
		origComplete = instance.completeElement
		def mixinCompleter(ctx):
			completerFunc()
			origComplete(ctx)
		instance.completeElement = mixinCompleter

	def feed(self, ctx, instance, mixinRef, fillers={}):
		"""feeds the immediate elements and schedules the rest of
		actions to be taken in time.
		"""
		mixin = ctx.resolveId(mixinRef, instance=instance, forceType=MixinDef)
		base.SetOfAtomsAttribute.feed(self, ctx, instance, mixinRef)
		mixin.applyTo(instance, ctx, fillers)

	# no need to override feedObject: On copy and such, replay has already
	# happened.

	def iterParentMethods(self):
		def mixesIn(instance, mixinRef):
			return mixinRef in instance.mixins
		yield "mixesIn", mixesIn
	
	def makeUserDoc(self):
		return ("A mixin reference, typically to support certain protocol."
			"  See Mixins_.")
	
	def create(self, parent, ctx, name):
		# since mixins may contain parameters, we need a custom parser
		# when mixin is a child.
		return _MixinParser(parent, self)
