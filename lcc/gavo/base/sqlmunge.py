"""
Helpers for building SQL expressions.

Some of this code is concerned with SQL factories.  These are functions
with the signature::

	func(field, val, outPars) -> fragment

outPars is a dictionary that is used to transmit literal values into SQL.
The result must be an SQL boolean expression for embedding into a WHERE clause
(use None to signal no constraint).  Field is the field for which the
expression is being generated.

The factories currently are never called when val is a sequence; there's
special hard-coded behaviour for that in getSQLFactory.

To enter values in outPars, use getSQLKey.  Its docstring contains
an example that shows how that would look like.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from __future__ import with_statement


def joinOperatorExpr(operator, operands):
	"""filters empty operands and joins the rest using operator.

	The function returns an expression string or None for the empty expression.
	"""
	operands = filter(None, operands)
	if not operands:
		return None
	elif len(operands)==1:
		return operands[0]
	else:
		return operator.join([" (%s) "%op for op in operands]).strip()


def getSQLKey(key, value, sqlPars):
	"""adds value to sqlPars and returns a key for inclusion in a SQL query.

	This function is used to build parameter dictionaries for SQL queries, 
	avoiding overwriting parameters with accidental name clashes.
	It works like this:

	>>> sqlPars = {}
	>>> getSQLKey("foo", 13, sqlPars)
	'foo0'
	>>> getSQLKey("foo", 14, sqlPars)
	'foo1'
	>>> getSQLKey("foo", 13, sqlPars)
	'foo0'
	>>> sqlPars["foo0"], sqlPars["foo1"]; sqlPars = {}
	(13, 14)
	>>> "WHERE foo<%%(%s)s OR foo>%%(%s)s"%(getSQLKey("foo", 1, sqlPars),
	...   getSQLKey("foo", 15, sqlPars))
	'WHERE foo<%(foo0)s OR foo>%(foo1)s'
	"""
	ct = 0
	while True:
		dataKey = "%s%d"%(key, ct)
		if not sqlPars.has_key(dataKey) or sqlPars[dataKey]==value:
			break
		ct += 1
	sqlPars[dataKey] = value
	return dataKey


_REGISTRED_SQL_FACTORIES = {}
def registerSQLFactory(type, factory):
	"""registers factory as an SQL factory for the type type (a string).
	"""
	_REGISTRED_SQL_FACTORIES[type] = factory


def _getSQLForSequence(field, val, sqlPars):
	if len(val)==0 or (len(val)==1 and val[0] is None):
		return ""
	return "%s IN %%(%s)s"%(field.name, getSQLKey(field.name,
		set(val), sqlPars))


def _getSQLForSimple(field, val, sqlPars):
	return "%s=%%(%s)s"%(field.name, getSQLKey(field.name,
		val, sqlPars))


def _getSQLFactory(type, value):
	"""returns an SQL factory for matching columns of type against value.
	"""
	if isinstance(value, (list, tuple)):
		return _getSQLForSequence
	elif type in _REGISTRED_SQL_FACTORIES:
		return _REGISTRED_SQL_FACTORIES[type]
	else:
		return _getSQLForSimple


def getSQLForField(field, inPars, sqlPars):
	"""returns an SQL fragment for a column-like thing.

	This will be empty if no input in inPars is present.  If it is, (a) new
	key(s) will be left in sqlPars.

	getSQLForField defines the default behaviour; in DBCore condDescs,
	it can be overridden using phrase makers.

	inPars is supposed to be "typed"; we do not catch general parse errors
	here.
	"""
	val = inPars.get(field.name)
	if val is None:
		return None
	if isinstance(val, (list, set, tuple)) and len(val)==1:
		val = val[0]

	factory = _getSQLFactory(field.type, val)
	return factory(field, val, sqlPars)


def _test():
	import doctest, sqlmunge
	doctest.testmod(sqlmunge)


if __name__=="__main__":
	_test()
