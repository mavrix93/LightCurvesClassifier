"""
Meta information validation.

The idea is that you define certain assertions about the meta information
of a given object type.  Defined assertions are 

	- MetaExists -- a key is present
	- MetaIsAtomic -- a key is present and a "leaf", i.e., has a single value
	- MetaAtomicExistsOnSelf -- a key is present even without meta inheritance,
		and has a single value

Validators are usually built using model descriptions.  These are enumerations
of meta keys, separated by commata, with an optional code in parenteses.
Whitespace is ignored.  Codes allowed in parens are:

	- empty (default): plain existence
	- !: atomic existance on self
	- 1: atomic existance

An example for a valid model description: 
"publisher.name,creator.email(), identifier (!), dateUpdated(1)"

These model descriptions can come in metaModel attributes of structures.
If they are, you can use the validateStructure function below to validate
an entire structure tree.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from __future__ import with_statement

from gavo import utils
from gavo.base import meta


class MetaValidationError(meta.MetaError):
	def __init__(self, carrier, failures):
		self.failures = failures
		if getattr(carrier, "id", None):
			self.carrierRepr = carrier.id
		else:
			self.carrierRepr = repr(carrier)
		meta.MetaError.__init__(self, "Meta structure on %s did not validate"%
			self.carrierRepr, carrier)

	def __str__(self):
		return "Meta structure on %s did not validate: %s"%(
			self.carrierRepr, ", ".join(self.failures))


class MetaAssertion(object):
	"""An assertion about the meta content of an object.

	You must override the C{check} method.
		"""
	def __init__(self, key):
		self.key = key

	def check(self, metaCarrier):
		"""returns None if the assertion is true, a user-displayable string of 
		what failed otherwise.

		This must be overridden in derived classes.
		@param metaCarrier: an object mixing in L{MetaMixin}.
		"""

		return "Null assertion on %s always fails"%self.key


class MetaExists(MetaAssertion):
	"""An assertion that a meta item is present for key in whatever form.
	"""
	def check(self, metaCarrier):
		if metaCarrier.getMeta(self.key) is None:
			return "Meta key %s missing"%self.key


class MetaIsAtomic(MetaAssertion):
	"""An assertion that a meta item is present and contains a single value
	only.
	"""
	propagate = True
	def check(self, metaCarrier):
		val = metaCarrier.getMeta(self.key, propagate=self.propagate)
		if val is None:
			return "Meta key %s missing"%self.key
		if len(val.children)!=1:
			return "Meta key %s is not atomic"%self.key


class MetaAtomicExistsOnSelf(MetaIsAtomic):
	"""An assertion that a meta item is present and unique for key on 
	metaCarrier itself.
	"""
	propagate = False


class MetaValidator(object):
	"""A metadata model that can verify objects of compliance.

	The model is quite simple: it's a sequence of MetaAssertions.
	The validate(metaCarrier) -> None method raises a MetaNotValid
	exception with all failed assertions in its failedAssertions
	attribute.
	"""
	def __init__(self, model):
		self.model = model
	
	def validate(self, metaCarrier):
		failures = [msg for msg in (
			ass.check(metaCarrier) for ass in self.model) if msg]
		if failures:
			raise MetaValidationError(metaCarrier, failures)


_assertionCodes = {
	():        MetaExists,
	('!',):    MetaAtomicExistsOnSelf,
	('1',):    MetaIsAtomic,
}


@utils.memoized
def _getModelGrammar():
	from gavo.imp.pyparsing import (Literal, Optional, StringEnd, Suppress, 
		Word, ZeroOrMore, alphas)

	with utils.pyparsingWhitechars(" \t"):
		metaKey = Word(alphas+".")
		modChar = Literal('!') | '1'
		modifier = Suppress('(') + Optional(modChar) + Suppress(')')
		assertion = metaKey("key")+Optional(modifier)("mod")
		model = assertion + ZeroOrMore( 
			Suppress(',') + assertion ) + StringEnd()

	def _buildAssertion(s, p, toks):
		key = str(toks["key"])
		mod = tuple(toks.get("mod", ()))
		return _assertionCodes[mod](key)

	assertion.addParseAction(_buildAssertion)
	model.addParseAction(lambda s,p,toks: MetaValidator(toks))
	return model


def parseModel(modelDescr):
	"""returns a MetaValidator for a model description.

	model descriptions are covered in the module docstring.
	"""
	return utils.pyparseString(_getModelGrammar(), modelDescr)[0]


def _validateStructNode(aStruct):
	if hasattr(aStruct.__class__, "metaModel"):
		metaModel = aStruct.__class__.metaModel
		if metaModel is None:
			return
		if isinstance(metaModel, basestring):
			aStruct.__class__.metaModel = parseModel(metaModel)
			metaModel = aStruct.__class__.metaModel
		metaModel.validate(aStruct)


def validateStructure(aStruct):
	"""does a meta validation for a base.Structure.

	This works by traversing the children of the structure, looking for 
	nodes with a metaModel attribute.  For all these, a validation is
	carried out.  The first node failing the validation determines the
	return value.

	The function raises a MetaValidationError if aStruct is invalid.
	"""
	_validateStructNode(aStruct)
	for s in aStruct.iterChildren():
		_validateStructNode(s)

