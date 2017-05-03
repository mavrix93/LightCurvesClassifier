"""
A grammars defined by code embedded in the RD.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from gavo import base
from gavo import rscdef
from gavo.grammars import common


class EmbeddedIterator(rscdef.ProcApp):
	"""A definition of an iterator of a grammar.

	The code defined here becomes the _iterRows method of a 
	grammar.common.RowIterator class.  This means that you can
	access self.grammar (the parent grammar; you can use this to transmit
	properties from the RD to your function) and self.sourceToken (whatever
	gets passed to parse()).
	"""
	name_ = "iterator"
	requiredType = "iterator"
	formalArgs = "self"


class EmbeddedGrammar(common.Grammar, base.RestrictionMixin):
	"""A Grammar defined by a code application.

	To define this grammar, write a ProcApp iterator leading to code yielding
	row dictionaries.  The grammar input is available as self.sourceToken;
	for normal grammars within data elements, that would be a fully
	qualified file name.

	The proc app body actually is the iterRows method of a row iterator
	(see API docs).

	This could look like this, when the grammar input is some iterable::

		<embeddedGrammar>
	  	<iterator>
	    	<setup>
	      	<code>
	        	testData = "a"*1024
	      	</code>
	    	</setup>
	    	<code>
	      	for i in self.sourceToken:
	        	yield {'index': i, 'data': testData}
	    	</code>
	  	</iterator>
		</embeddedGrammar>
	"""
	name_ = "embeddedGrammar"
	_iterator = base.StructAttribute("iterator", default=base.Undefined,
		childFactory=EmbeddedIterator,
		description="Code yielding row dictionaries", copyable=True)
	_isDispatching = base.BooleanAttribute("isDispatching", default=False,
		description="Is this a dispatching grammar (i.e., does the row iterator"
		" return pairs of role, row rather than only rows)?", copyable=True)

	def onElementComplete(self):
		self._onElementCompleteNext(EmbeddedGrammar)
		class RowIterator(common.RowIterator):
			_iterRows = self.iterator.compile()
			notify = False
		self.rowIterator = RowIterator
