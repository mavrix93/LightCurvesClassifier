"""
Helpers for morphing modules
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from gavo.adql import nodes


class State(object):
	"""is a scratchpad for morphers to communicate state among
	themselves.

	Append to warnings a necessary.  Also, traverse keeps an attribute
	nodeStack in here letting elements look up its parent chain.
	"""
	def __init__(self):
		self.warnings = []
		self.nodeStack = []


_BOOLEANIZER_TABLE = {
	('=', '0'): "NOT ",
	('!=', '1'): "NOT ",
	('=', '1'): "",
	('!=', '0'): "",}

def addNotToBooleanized(expr, operator, operand):
	"""prepends a NOT to expr if operator and operand suggest there should
	be one for ADQL integerized boolean expressions.

	The function will return None for unknown combinatins of operator and
	operand, and it will simply hand through Nones for expr, so calling 
	functions can just return addNotToBooleanized(...).
	"""
	if expr is None:
		return expr

	prefix = _BOOLEANIZER_TABLE.get((operator, operand), None)
	if prefix is None:
		# weird non-boolean-looking condition
		return None
	
	return prefix+expr


# Handler functions for booleanizeComparisons
_BOOLEANOID_FUNCTIONS = {}

def registerBooleanizer(funcName, handler):
	"""registers handler as a booleanizer for ADQL functions called
	funcName.

	funcName must be for this to work all-uppercase.  handler(node,
	operand, operator) is a function that receive a function node
	and the operand and operator of the comparison and either returns
	None to say it can't handle it, or something else; that something
	else is what the entire comparison node is morphed into.

	You can call multiple booleanizers for the same function; they will
	be tried in sequence.  Hence, make sure you get your import sequences
	right if you do this.
	"""
	_BOOLEANOID_FUNCTIONS.setdefault(funcName, []).append(handler)


def booleanizeComparisons(node, state):
	"""turns a comparison expression that's really a boolean
	expression into a boolean expression.

	This is for things like the geometry predicates (CONTAINS,
	INTERSECTS) or stuff like ivo_hasword and such.  Embedding these
	as booleans helps the query planner a lot (though it might change
	semantics slightly in the presence of NULLs).

	The way this works is that morphing code can call
	registerBooleanizer with the function name and callable
	that receives the function node, the operator, and the operand.
	If that function returns non-None, that result is used instead
	of the current node.
	"""
	if isinstance(node.op1, nodes.FunctionNode):
		fCall, opd = node.op1, node.op2
	elif isinstance(node.op2, nodes.FunctionNode):
		fCall, opd = node.op2, node.op1
	else:
		# no function call, leave things alone
		return node

	for morpher in _BOOLEANOID_FUNCTIONS.get(fCall.funName, []):
		res = morpher(fCall, node.opr, nodes.flatten(opd))
		if res is not None:
			node = res
			break
	return node



class Morpher(object):
	"""A class managing the process of morphing an ADQL expression.

	It is constructed with a a dictionary of morphers; the keys are node
	types, the values morphing functions.

	Morphing functions have the signature m(node, state) -> node.  They
	should return the node if they do not with to change it.
	state is a State instance.

	The main entry point is morph(origTree) -> state, tree.  origTree is not 
	modified, the return value can be flattened but can otherwise be severely 
	damaged.

	For special effects, there's also earlyMorphers.  These will be called
	when traversal reaches the node for the first time.  If these return
	None, traversal continues as usual, if not, their result will be
	added to the tree and *not* further traversed.
	"""
	def __init__(self, morphers, earlyMorphers={}):
		self.morphers = morphers
		self.earlyMorphers = earlyMorphers

	def _getChangedForSeq(self, value, state):
		newVal, changed = [], False
		for child in value:
			if isinstance(child, nodes.ADQLNode):
				newVal.append(self._traverse(child, state))
			else:
				newVal.append(child)
			if newVal[-1]!=child:
				changed = True
		if changed:
			return tuple(newVal)
	
	def _getChangedForNode(self, value, state):
		newVal = self._traverse(value, state)
		if not newVal is value:
			return newVal

	def _getChanges(self, name, value, state):
		"""iterates over key/value pairs changed by morphing value under
		the key name.
		"""
		if isinstance(value, (list, tuple)):
			meth = self._getChangedForSeq
		elif isinstance(value, nodes.ADQLNode):
			meth = self._getChangedForNode
		else:
			return
		newVal = meth(value, state)
		if newVal is not None:
			yield name, newVal

	def _traverse(self, node, state):
		if node.type in self.earlyMorphers:
			res = self.earlyMorphers[node.type](node, state)
			if res is not None:
				return res

		state.nodeStack.append(node)
		changes = []
		for name, value in node.iterAttributes():
			changes.extend(self._getChanges(name, value, state))
		if changes:
			newNode = node.change(**dict(changes))
		else:
			newNode = node
		popped = state.nodeStack.pop()
		assert popped==node, "ADQL morphing node stack corruption"

		if node.type in self.morphers:
			handlerResult = self.morphers[node.type](newNode, state)
			assert handlerResult is not None, "ADQL morph handler returned None"
			return handlerResult
		return newNode

	def morph(self, tree):
		state = State()
		res = self._traverse(tree, state)
		return state, res
