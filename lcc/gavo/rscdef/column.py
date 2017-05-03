"""
Description of columns (and I/O fields).
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from gavo import base
from gavo import utils
from gavo.base import typesystems
from gavo.utils import codetricks

__docformat__ = "restructuredtext en"


# A set of database type names that need explicit null values when
# they are serialized into VOTables.  We don't check array types
# here at all, since that's another can of worms entirely.
EXPLICIT_NULL_TYPES = set([
	"smallint", "integer", "bigint", "char", "boolean", "bytea"])


class TypeNameAttribute(base.AtomicAttribute):
	"""An attribute with values constrained to types we understand.
	"""
	@property
	def typeDesc_(self):
		return ("a type name; the internal type system is similar to SQL's"
			" with some restrictions and extensions.  The known atomic types"
			" include: %s"%(", ".join(typesystems.ToPythonConverter.simpleMap)))

	def parse(self, value):
		try:
			typesystems.sqltypeToPython(value)
		except base.Error:
			raise base.ui.logOldExc(base.LiteralParseError(self.name_, value, 
				hint="A supported SQL type was expected here.  If in doubt,"
				" check base/typeconversions.py, in particular ToPythonCodeConverter."))
		return value
	
	def unparse(self, value):
		return value


class ColumnNameAttribute(base.UnicodeAttribute):
	"""An attribute containing a column name.

	Column names are special in that you can prefix them with "quoted/"
	and then get a delimited identifier.  This is something you probably
	shouldn't use.
	"""
	@property
	def typeDesc_(self):
		return ("a column name within an SQL table.  These have to match"
			" ``%s``.  In a desperate pinch, you can generate delimited identifiers"
			" (that can contain anything) by prefixing the name with 'quoted/' (but"
			" you cannot use rowmakers to fill such tables)."
			)%utils.identifierPattern.pattern
	
	def parse(self, value):
		if value.startswith("quoted/"):
			return utils.QuotedName(value[7:])
		if not utils.identifierPattern.match(value):
			raise base.StructureError("'%s' is not a valid column name"%value)
		return value
	
	def unparse(self, value):
		if isinstance(value, utils.QuotedName):
			return "quoted/"+value.name
		else:
			return value


class _AttBox(object):
	"""A helper for TableManagedAttribute.

	When a TableManagedAttribute ships off its value into an event
	it packs its value into an _AttBox.  That way, the receiver
	can tell whether the value comes from another TableManagedAttribute
	(which is ok) or comes from an XML parser (which is forbidden).
	"""
	def __init__(self, payload):
		self.payload = payload


class TableManagedAttribute(base.AttributeDef):
	"""An attribute not settable from XML for holding information
	managed by the parent table.
	
	That's stc and stcUtype here, currently.
	"""
	typeDesc_ = "non-settable internally used value"

	def feed(self, ctx, instance, value):
		if isinstance(value, _AttBox):
			# synthetic event during object copying, accept
			self.feedObject(instance, value.payload)
		else:
			# do not let people set that stuff directly
			raise base.StructureError("Cannot set %s attributes from XML"%self.name_)
	
	def feedObject(self, instance, value):
		setattr(instance, self.name_, value)

	def iterEvents(self, instance):
		val = getattr(instance, self.name_)
		if val!=self.default_:
			yield ("value", self.name_, _AttBox(val))

	def getCopy(self, instance, newParent):
		# these never get copied; the values are potentially shared 
		# between many objects, so the must not be changed anyway.
		return getattr(instance, self.name_)


class RoEmptyDict(dict):
	"""is a read-only standin for a dict.

	It's hashable, though, since it's always empty...  This is used here
	for a default for displayHint.
	"""
	def __setitem__(self, what, where):
		raise TypeError("RoEmptyDicts are immutable")

_roEmptyDict = RoEmptyDict()


class DisplayHintAttribute(base.AtomicAttribute):
	"""is a display hint.

	Display hint literals are comma-separated key=value sequences.
	Keys are up to the application and evaluated by htmltable, votable, etc.

	The parsed values are simply dictionaries mapping strings to strings, i.e.,
	value validation cannot be performed here (yet -- do we want this?
	A central repository of display hints would be kinda useful...)
	"""
	typeDesc_ = "Display hint"

	def __init__(self, name, description, **kwargs):
		base.AtomicAttribute.__init__(self, name, default=_roEmptyDict, 
			description=description, **kwargs)

	def parse(self, value):
		if not value.strip():
			return _roEmptyDict
		try:
			return dict([f.split("=") for f in value.split(",")])
		except (ValueError, TypeError):
			raise base.ui.logOldExc(base.LiteralParseError(self.name_, value, 
				hint="DisplayHints have a format like tag=value{,tag=value}"))

	def unparse(self, value):
		return ",".join(
			["%s=%s"%(k,v) for k,v in value.iteritems()])


class Option(base.Structure):
	"""A value for enumerated columns.

	For presentation purposes, an option can have a title, defaulting to
	the option's value.
	"""
	name_ = "option"

	_title = base.UnicodeAttribute("title", default=base.NotGiven,
		description="A Label for presentation purposes; defaults to val.", 
		copyable=True)
	_val = base.DataContent(copyable=True, description="The value of"
		" the option; this is what is used in, e.g., queries and the like.")

	def __repr__(self):
		# may occur in user messages from formal, so we use title.
		return self.title

	def completeElement(self, ctx):
		if self.title is base.NotGiven:
			self.title = self.content_
		self._completeElementNext(Option, ctx)


def makeOptions(*args):
	"""returns a list of Option instances with values given in args.
	"""
	return [base.makeStruct(Option, content_=arg) for arg in args]


class Values(base.Structure):
	"""Information on a column's values, in particular its domain.

	This is quite like the values element in a VOTable.  In particular,
	to accomodate VOTable usage, we require nullLiteral to be a valid literal
	for the parent's type.
	"""
	name_ = "values"

	_min = base.UnicodeAttribute("min", default=None, 
		description="Minimum acceptable"
		" value as a datatype literal", copyable=True)
	_max = base.UnicodeAttribute("max", default=None, 
	description="Maximum acceptable"
		" value as a datatype literal", copyable=True)
	_options = base.StructListAttribute("options", 
		childFactory=Option,
		description="List of acceptable values (if set)", copyable=True)
	_default = base.UnicodeAttribute("default", default=None, 
		description="A default"
		" value (currently only used for options).", copyable=True)
	_nullLiteral = base.UnicodeAttribute("nullLiteral", default=None, 
		description=
		"An appropriate value representing a NULL for this column in VOTables"
		" and similar places.  You usually should only set it for integer"
		" types and chars.  Note that rowmakers mak no use of this nullLiteral,"
		" i.e., you can and should choose null values independently of your"
		" your source.  Again, for reals, floats and (mostly) text you probably"
		" do not want to do this.", copyable=True)
	_multiOk = base.BooleanAttribute("multiOk", False, "Deprecated, use"
		" multiplicity=multiple instead.", copyable=True)
	_fromDB = base.ActionAttribute("fromdb", "_evaluateFromDB", description=
		"A query fragment returning just one column to fill options from (will"
		" add to options if some are given).  Do not write SELECT or anything,"
		" just the column name and the where clause.")
	_original = base.OriginalAttribute()

	validValues = None

	@classmethod
	def fromOptions(cls, labels):
		"""returns Values with the elements of labels as valid options.
		"""
		return base.makeStruct(cls, 
			options=[base.makeStruct(Option, content_=l) for l in labels])

	def makePythonVal(self, literal, sqltype):
		return typesystems.sqltypeToPython(sqltype)(literal)

	def _evaluateFromDB(self, ctx):
		if not getattr(ctx, "doQueries", True):
			return
		try:
			with base.getTableConn() as conn:
				for row in conn.query(self.parent.parent.expand(
						"SELECT DISTINCT %s"%(self.fromdb))):
					self._options.feedObject(self, base.makeStruct(Option,
						content_=row[0]))
		except base.DBError: # Table probably doesn't exist yet, ignore.
			base.ui.notifyWarning("Values fromdb '%s' failed, ignoring"%self.fromdb)

	def onParentComplete(self):
		"""converts min, max, and options from string literals to python
		objects.
		"""
		dataField = self.parent
		# It would be nicer if we could handle this in properties for min etc, but
		# unfortunately parent might not be complete then.  The only
		# way around that would have been delegations from Column, and that's
		# not very attractive either.
		if self.min:
			self.min = self.makePythonVal(self.min, dataField.type)
		if self.max:
			self.max = self.makePythonVal(self.max, dataField.type)

		if self.options:
			dbt = dataField.type
			for opt in self.options:
				opt.content_ = self.makePythonVal(opt.content_, dbt)
			self.validValues = set([o.content_ for o in self.options])

		if self.nullLiteral:
			try:
				self.makePythonVal(self.nullLiteral, dataField.type)
			except ValueError:
				raise base.LiteralParseError("nullLiteral", self.nullLiteral,
					hint="If you want to *parse* whatever you gave into a NULL,"
					" use the parseWithNull function in a rowmaker.  The null"
					" literal gives what value will be used for null values"
					" when serializing to VOTables and the like.")

	def validateOptions(self, value):
		"""returns false if value isn't either in options or doesn't consist of
		items in options.

		Various null values always validate here; non-null checking is done
		by the column on its required attribute.
		"""
		if value=="None":
			assert False, "Literal 'None' passed as a value to validateOptions"

		if self.validValues is None:
			return True
		if isinstance(value, (list, tuple, set)):
			for val in value:
				if val and not val in self.validValues:
					return False
		else:
			return value in self.validValues or value is None
		return True


class ColumnBase(base.Structure, base.MetaMixin):
	"""A base class for columns, parameters, output fields, etc.

	Actually, right now there's far too much cruft in here that 
	should go into Column proper or still somewhere else.  Hence:
	XXX TODO: Refactor.

	See also Column for a docstring that still applies to all we've in
	here.
	"""
	_name = ColumnNameAttribute("name", default=base.Undefined,
		description="Name of the column",
		copyable=True, before="type")
	_type = TypeNameAttribute("type", default="real", description=
		"datatype for the column (SQL-like type system)",
		copyable=True, before="unit")
	_unit = base.UnicodeAttribute("unit", default="", description=
		"Unit of the values", copyable=True, before="ucd")
	_ucd = base.UnicodeAttribute("ucd", default="", description=
		"UCD of the column", copyable=True, before="description")
	_description = base.NWUnicodeAttribute("description", 
		default="", copyable=True,
		description="A short (one-line) description of the values in this column.")
	_tablehead = base.UnicodeAttribute("tablehead", default=None,
		description="Terse phrase to put into table headers for this"
			" column", copyable=True)
	_utype = base.UnicodeAttribute("utype", default=None, description=
		"utype for this column", copyable=True)
	_required = base.BooleanAttribute("required", default=False,
		description="Record becomes invalid when this column is NULL", 
		copyable=True)
	_displayHint = DisplayHintAttribute("displayHint", 
		description="Suggested presentation; the format is "
			" <kw>=<value>{,<kw>=<value>}, where what is interpreted depends"
			" on the output format.  See, e.g., documentation on HTML renderers"
			" and the formatter child of outputFields.", copyable=True)
	_verbLevel = base.IntAttribute("verbLevel", default=20,
		description="Minimal verbosity level at which to include this column", 
		copyable=True)
	_values = base.StructAttribute("values", default=None,
		childFactory=Values, description="Specification of legal values", 
		copyable=True)
	_fixup = base.UnicodeAttribute("fixup", description=
		"A python expression the value of which will replace this column's"
		" value on database reads.  Write a ___ to access the original"
		' value.  You can use macros for the embedding table.'
		' This is for, e.g., simple URL generation'
		' (fixup="\'\\internallink{/this/svc}\'+___").'
		' It will *only* kick in when tuples are deserialized from the'
		" database, i.e., *not* for values taken from tables in memory.",
		default=None, copyable=True)
	_note = base.UnicodeAttribute("note", description="Reference to a note meta"
		" on this table explaining more about this column", default=None,
		copyable=True)
	_xtype = base.UnicodeAttribute("xtype", description="VOTable xtype giving"
		" the serialization form", default=None, copyable=True)
	_stc = TableManagedAttribute("stc", description="Internally used"
		" STC information for this column (do not assign to unless instructed"
		" to do so)",
		default=None, copyable=True)
	_stcUtype = TableManagedAttribute("stcUtype", description="Internally used"
		" STC information for this column (do not assign to)",
		default=None, copyable=True)
	_properties = base.PropertyAttribute(copyable=True)
	_original = base.OriginalAttribute()

	restrictedMode = False

	def __repr__(self):
		return "<Column %s>"%repr(self.name)

	def setMetaParent(self, parent):
		# columns should *not* take part in meta inheritance.  The reason is
		# that there are usually many columns to a table, and there's no
		# way I can see that any piece of metadata should be repeated in
		# all of them.  On the other hand, for votlinks (no name an example),
		# meta inheritance would have disastrous consequences.
		# So, we bend the rules a bit.
		raise base.StructureError("Columns may not have meta parents.",
			hint="The rationale for this is explained in rscdef/column.py,"
			" look for setMetaParent.")

	def onParentComplete(self):
		# we need to resolve note on construction since columns are routinely
		# copied to other tables and  meta info does not necessarily follow.
		if isinstance(self.note, basestring):
			try:
				self.note = self.parent.getNote(self.note)
			except base.NotFoundError: # non-existing notes silently ignored
				self.note = None

	def completeElement(self, ctx):
		self.restrictedMode = getattr(ctx, "restricted", False)
		if isinstance(self.name, utils.QuotedName):
			self.key = self.name.name
			if ')' in self.key:
				# No '()' allowed in key for that breaks the %()s syntax (sigh!).
				# Work around with the following quick hack that would break
				# if people carefully chose proper names.  Anyone using delim.
				# ids in SQL deserves a good spanking anyway.
				self.key = self.key.replace(')', "__").replace('(', "__")
		else:
			self.key = self.name
		self._completeElementNext(ColumnBase, ctx)

	def isEnumerated(self):
		return self.values and self.values.options

	def validate(self):
		self._validateNext(ColumnBase)
		if self.restrictedMode and self.fixup:
			raise base.RestrictedElement("fixup")

	def validateValue(self, value):
		"""raises a ValidationError if value does not match the constraints
		given here.
		"""
		if value is None:
			if self.required:
				raise base.ValidationError(
					"Field %s is empty but non-optional"%self.name, self.name)
			return

		vals = self.values
		if vals:
			if vals.options:
				if value and not vals.validateOptions(value):
					raise base.ValidationError("Value %s not consistent with"
						" legal values %s"%(value, vals.options), self.name)
			else:
				if vals.min and value<vals.min:
					raise base.ValidationError("%s too small (must be at least %s)"%(
						value, vals.min), self.name)
				if vals.max and value>vals.max:
					raise base.ValidationError("%s too large (must be less than %s)"%(
						value, vals.max), self.name)

	def isIndexed(self):
		"""returns a guess as to whether this column is part of an index.

		This may return True, False, or None (unknown).
		"""
		if self.parent and hasattr(self.parent, "indexedColumns"):
				# parent is something like a TableDef
			if self.name in self.parent.indexedColumns:
				return True
			else:
				return False

	def isPrimary(self):
		"""returns a guess as to whether this column is a primary key of the
		embedding table.

		This may return True, False, or None (unknown).
		"""
		if self.parent and hasattr(self.parent, "primary"):
				# parent is something like a TableDef
			if self.name in self.parent.primary:
				return True
			else:
				return False

	_indexedCleartext = {
		True: "indexed",
		False: "notIndexed",
		None: "unknown",
	}

	def asInfoDict(self):
		"""returns a dictionary of certain, "user-interesting" properties
		of the data field, in a dict of strings.
		"""
		return {
			"name": self.name,
			"description": self.description or "N/A",
			"tablehead": self.getLabel(),
			"unit": self.unit or "N/A",
			"ucd": self.ucd or "N/A",
			"verbLevel": self.verbLevel,
			"indexState": self._indexedCleartext[self.isIndexed()],
			"note": self.note,
		}
	
	def getDDL(self):
		"""returns an SQL fragment describing this column ready for 
		inclusion in a DDL statement.
		"""
		type = self.type
		# we have one "artificial" type, and it shouldn't become more than
		# one; so, a simple hack should do it.
		if type.upper()=="UNICODE":
			type = "TEXT"

		# The "str" does magic for delimited identifiers, so it's important.
		items = [str(self.name), type]
		if self.required:
			items.append("NOT NULL")
		return " ".join(items)

	def getDisplayHintAsString(self):
		return self._displayHint.unparse(self.displayHint)

	def getLabel(self):
		"""returns a short label for this column.

		The label is either the tablehead or, missing it, the capitalized
		column name.
		"""
		if self.tablehead is not None:
			return self.tablehead
		return self.name.capitalize()
		

class Column(ColumnBase):
	"""A database column.
	
	Columns contain almost all metadata to describe a column in a database
	table or a VOTable (the exceptions are for column properties that may
	span several columns, most notably indices).

	Note that the type system adopted by the DC software is a subset
	of postgres' type system.  Thus when defining types, you have to
	specify basically SQL types.  Types for other type systems (like
	VOTable, XSD, or the software-internal representation in python values)
	are inferred from them.

	Columns can have delimited identifiers as names.  Don't do this, it's
	no end of trouble.  For this reason, however, you should not use name
	but rather key to programmatially obtain field's values from rows.

	Properties evaluated:

	- std -- set to 1 to tell the tap schema importer to have the column's
	  std column in TAP_SCHEMA 1 (it's 0 otherwise).
	"""
	name_ = "column"

	def validate(self):
		self._validateNext(Column)
		# Now check if we can serialize the column safely in VOTables.
		# I only want to hear about this when the column may end up in
		# a VOTable; 
		if self.type in EXPLICIT_NULL_TYPES:
			if not self.required and not (
					self.values and self.values.nullLiteral):
				try:
					pos = codetricks.stealVar("context").pos
					base.ui.notifyWarning("Somwhere near %s: "
						" Column %s may be null but has no explicit"
						" null value."%(pos, self.name))
				except (ValueError, AttributeError):
					# This is stealVar's ValueError, we have no context in stack (or 
					# it's a context var not from our parsing code).
					# Seems we're not parsing from a file, so the user probably
					# can't help it anyway.  Don't complain.
					pass


class ParamBase(ColumnBase):
	"""A basic parameter.

	This is the base for both Param and InputKey.
	"""
	_value = base.DataContent(description="The value of parameter."
		" It is parsed according to the param's type using the default"
		" parser for the type as in rowmakers.", default=base.NotGiven,
		copyable=True, expand=True)

	_valueCache = base.Undefined

	# we need to fix null literal handling of params.  Meanwhile:
	nullLiteral = ""

	def __repr__(self):
		return "<%s %s=%s>"%(self.__class__.__name__, 
			repr(self.name), repr(self.content_))

	def expand(self, value):
		"""hands up macro expansion requests to a parent, if there is one
		and it can handle expansions.
		"""
		if hasattr(self.parent, "expand"):
			return self.parent.expand(value)
		return value

	def completeElement(self, ctx):
		if not self.values:
			self.values = base.makeStruct(Values, parent_=self)
		self._completeElementNext(ParamBase, ctx)
	
	def onElementComplete(self):
		self._onElementCompleteNext(ParamBase)
		if self.content_ is base.NotGiven:
			if self.values.default:
				self.set(self.values.default)
		else:
			self.set(self.content_)

	@property
	def value(self):
		"""returns a typed value for the parameter.

		Unset items give None here.
		"""
		if self._valueCache is base.Undefined:
			if self.content_ is base.NotGiven:
				self._valueCache = None
			else:
				self._valueCache = self._parse(self.content_)
		return self._valueCache
	
	def getStringValue(self):
		"""returns a string serialisation of the value.

		This is what would reproduce the value if embedded in an XML
		serialisation of the param.
		"""
		return self.content_

	def set(self, val):
		"""sets this parameter's value.

		val can be a python value, or string literal.  In the second
		case, this string literal will be preserved in string serializations
		of this param.

		If val is an invalid value for this item, a ValidationError is
		raised and the item's value will be Undefined.
		"""
		if isinstance(val, basestring):
			self._valueCache = base.Undefined
		else:
			self._valueCache = base.Undefined
			val = self._unparse(val)

		if not self.values.validateOptions(self._parse(val)):
			raise base.ValidationError("%s is not a valid value for %s"%(
				repr(val), self.name), self.name)

		self.content_ = val

	def _parse(self, literal):
		"""parses literal using the default value parser for this param's
		type.

		If literal is not a string, it will be returned unchanged.
		"""
		if not isinstance(literal, basestring):
			return literal
		try:
			if literal==self.values.nullLiteral:
				return None
			return base.sqltypeToPython(self.type)(literal)
		except ValueError:
			raise base.ValidationError("%s is not a valid literal for %s"%(
				repr(literal), self.name), self.name)

	def _unparse(self, value):
		"""returns a string representation of value appropriate for this
		type.

		Actually, for certain types only handled internally (like file or raw),
		this is not a string representation at all but just the python stuff.

		Plus, right now, for sequences we're not doing anything.  We probably
		should.
		"""
		if isinstance(value, (list, tuple, set)):
			return value
		if value is None:
			return self.values.nullLiteral
		else:
			return base.pythonToLiteral(self.type)(value)


class Param(ParamBase):
	"""A table parameter.

	This is like a column, except that it conceptually applies to all
	rows in the table.  In VOTables, params will be rendered as
	PARAMs.  
	
	While we validate the values passed using the DC default parsers,
	at least the VOTable params will be literal copies of the string
	passed in.

	You can obtain a parsed value from the value attribute.

	Null value handling is a bit tricky with params.  An empty param (like 
	``<param name="x"/>)`` will usually be NULL, except of strings, for which
	it is the empty string (as is, by the way, everything that contains
	whitespace exclusively).
	
	params also suppoert explicit null values via values, as in::

		<param name="x" type="integer"><values nullLiteral="-1"/>-1</params>
	
	The value attribute for NULL params is None.
	"""
	name_ = "param"

	def validate(self):
		self._validateNext(Param)
		if self.content_ is base.NotGiven:
			if self.type=="text" or self.type=="unicode":
				self.set("")
			else:
				self.set(None)

		if self.required and self.value is None:
			raise base.StructureError("Required value not given for param"
				" %s"%self.name)

		try:
			# the value property will bomb on malformed literals
			self.value
		except ValueError, msg:
			raise base.LiteralParseError(self.name, self.content_,
				hint="Param content must be parseable by the DC default parsers."
					"  The value you passed caused the error: %s"%msg)
	
	def set(self, val):
		"""sets the value of the parameter.

		Macros will be expanded if the parent object supports macro
		expansion.
		"""
		if (isinstance(val, basestring)
				and "\\" in val 
				and hasattr(self.parent, "expand")):
			val = self.parent.expand(val)
		return ParamBase.set(self, val)
