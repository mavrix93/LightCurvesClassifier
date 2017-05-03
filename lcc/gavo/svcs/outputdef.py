"""
Output tables and their components.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import fnmatch

from gavo import base 
from gavo import rscdef 
from gavo import utils 

_EMPTY_TABLE = base.makeStruct(rscdef.TableDef, id="<builtin empty table>")
_EMPTY_TABLE.getFullId = lambda: None


class OutputField(rscdef.Column):
	"""A column for defining the output of a service.

	It adds some attributes useful for rendering results, plus functionality
	specific to certain cores.

	The optional formatter overrides the standard formatting code in HTML
	(which is based on units, ucds, and displayHints).  You receive
	the item from the database as data and must return a string or
	nevow stan.  In addition to the standard `Functions available for
	row makers`_ you have queryMeta and nevow's tags in T.

	Here's an example for generating a link to another service using this
	facility::

	  <outputField name="more" 
	      select="array[centerAlpha,centerDelta] as more" tablehead="More"
	      description="More exposures near the center of this plate">
	    <formatter><![CDATA[
	      return T.a(href=base.makeSitePath("/lswscans/res/positions/q/form?"
	        	"POS=%s,%s&SIZE=1&INTERSECT=OVERLAPS&cutoutSize=0.5"
		      	"&__nevow_form__=genForm"%tuple(data)
		      	))["More"] ]]>
	    </formatter>
	  </outputField>
	"""
	name_ = "outputField"


	_formatter = base.UnicodeAttribute("formatter", description="Function"
		" body to render this item to HTML.", copyable=True, expand=True)
	_wantsRow = base.BooleanAttribute("wantsRow", description="Does"
		" formatter expect the entire row rather than the colum value only?",
		copyable="True")
	_select = base.UnicodeAttribute("select", description="Use this SQL"
		" fragment rather than field name in the select list of a DB based"
		" core.", default=base.Undefined, copyable=True, expand=True)
	_sets = base.StringSetAttribute("sets", description=
		"Output sets this field should be included in; ALL includes the field"
		" in all output sets.",
		copyable=True)

	def __repr__(self):
		return "<OutputField %s>"%repr(self.name)

	def completeElement(self, ctx):
		if self.restrictedMode and (
				self.formatter
				or self.select):
			raise base.RestrictedElement(self.name_, hint="formatter and select"
				" attributes on output fields are not allowed in restricted mode.")
		if self.select is base.Undefined:
			self.select = self.name
		self._completeElementNext(OutputField, ctx)

	@classmethod
	def fromColumn(cls, col):
		res = cls(None, **col.getAttributes(rscdef.Column))
		res.stc = col.stc
		return res.finishElement()

	def expand(self, *args, **kwargs):
		return self.parent.expand(*args, **kwargs)


class OutputTableDef(rscdef.TableDef):
	"""A table that has outputFields for columns.
	"""
	name_ = "outputTable"

	# Don't validate meta for these -- while they are children
	# of validated structures (services), they don't need any
	# meta at all.  This should go as soon as we have a sane
	# inheritance hierarchy for tables.
	metaModel = None

	_cols = rscdef.ColumnListAttribute("columns", 
		childFactory=OutputField,
		description="Output fields for this table.", 
		aliases=["column"],
		copyable=True)

	_verbLevel = base.IntAttribute("verbLevel", 
		default=None,
		description="Copy over columns from fromTable not"
			" more verbose than this.")

	_autocols = base.StringListAttribute("autoCols", 
		description="Column names obtained from fromTable; you can use"
			" shell patterns into the output table's parent table (in a table"
			" core, that's the queried table; in a service, it's the core's"
			" output table) here.")

	def __init__(self, parent, **kwargs):
		rscdef.TableDef.__init__(self, parent, **kwargs)
		self.parentTable = None
		try:
			# am I in a table-based core?
			self.parentTable = self.parent.queriedTable
		except (AttributeError, base.StructureError):
			# no.
			pass

		if not self.parentTable:
			try:
				# am I in a service with a core with output table?
				self.parentTable = self.parent.core.outputTable
			except (AttributeError, base.StructureError):
				# no.
				pass

		if not self.parentTable:
			# no suitable column source, use an empty table:
			self.parentTable = _EMPTY_TABLE

		self.namePath = None

	def _adoptColumn(self, sourceColumn):
		# Do not overwrite existing fields here to let the user
		# override individually
		try:
			self.getColumnByName(sourceColumn.name)
		except base.NotFoundError:
			self.feedObject("outputField", OutputField.fromColumn(sourceColumn))

	def _addNames(self, ctx, names):
		# since autoCols is not copyable, we can require
		# that _addNames only be called when there's a real parse context.
		if ctx is None:
			raise base.StructureError("outputTable autocols is"
				" only available with a parse context")
		for name in names:
			self._addName(ctx, name)
	
	def _addName(self, ctx, name):
		"""adopts a param or column name into the outputTable.

		name may be a reference or a param or column name in the parent
		table (as determined in the constructor, i.e., the queried table
		of a core or the output table of a service's core.

		You can also use shell patterns into parent columns.
		"""
		if utils.identifierPattern.match(name):
			refOb = ctx.resolveId(name, self)
			if refOb.name_=="param":
				self.feedObject("param", refOb.copy(self))
			else:
				self._adoptColumn(refOb)
		
		else:
			# it's a shell pattern into parent table
			for col in self.parentTable:
				if fnmatch.fnmatch(col.name, name):
					self._adoptColumn(col)

	def completeElement(self, ctx):
		if self.autoCols:
			self._addNames(ctx, self.autoCols)

		if self.verbLevel:
			table = self.parentTable
			for col in table.columns:
				if col.verbLevel<=self.verbLevel:
					self._adoptColumn(col)
			for par in table.params:
				if par.verbLevel<=self.verbLevel:
					self.feedObject("param", par.copy(self))

		self._completeElementNext(OutputTableDef, ctx)

	@classmethod
	def fromColumns(cls, columns, **kwargs):
		return rscdef.TableDef.fromColumns([OutputField.fromColumn(c)
			for c in columns])

	@classmethod
	def fromTableDef(cls, tableDef, ctx):
		return cls(None, columns=[OutputField.fromColumn(c) for c in tableDef],
			forceUnique=tableDef.forceUnique, dupePolicy=tableDef.dupePolicy,
			primary=tableDef.primary, params=tableDef.params).finishElement(ctx)
