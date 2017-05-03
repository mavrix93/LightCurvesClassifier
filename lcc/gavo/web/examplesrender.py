"""
The renderer for VOSI examples, plus the docutils extensions provided for
them.

If you have a renderer that needs custom text roles or directives, read the
docstring of RSTExtensions and add whatever roles you need below, more or less
like this::

	examplesrender.RSTExtensions.makeTextRole("niceRole")

Only go through RSTExtensions, as these will make sure HTML postprocessing
happens as required.

The reason we keep the roles here and not in the renderer modules where they'd
logically belong (and where they should be documented in the renderer
docstrings) is that we don't want docutils imports all over the place.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.

import re

from docutils import nodes
from docutils.parsers import rst
from docutils.parsers.rst import directives
from docutils.parsers.rst import roles

from lxml import etree

from nevow import rend

from .. import base
from .. import svcs
from . import grend


class RSTExtensions(object):
	"""a register for local RST extensions.

	This is for both directives and interpreted text roles.  

	We need these as additional markup in examples; these always
	introduce local rst interpreted text roles, which always
	add some class to the node in question (modifications are possible).

	These classes are then changed to properties as the HTML fragments
	from RST translation are processed by the _Example nevow data factory.

	To add a new text role, say::

		RSTExtensions.addRole(roleName, roleFunc=None)

	You can pass in a full role function as discussed in
	/usr/share/doc/python-docutils/docs/howto/rst-roles.html (Debian systems).
	It must, however, add a dachs-ex-<roleName> class to the node. The
	default funtion produces a nodes.emphasis item with the proper class.

	To add a directive, say::

		RSTExtensions.addDirective(dirName, dirClass)

	In HTML, these classes become properties named like the role name.
	"""
	classToProperty = {}

	@classmethod
	def addDirective(cls, name, implementingClass):
		directives.register_directive(name, implementingClass)
		cls.classToProperty["dachs-ex-"+name] = name

	@classmethod
	def makeTextRole(cls, roleName, roleFunc=None):
		"""creates a new text role for roleName.

		See class docstring.
		"""
		if roleFunc is None:
			roleFunc = cls._makeDefaultRoleFunc(roleName)
		roles.register_local_role(roleName, roleFunc)
		cls.classToProperty["dachs-ex-"+roleName] = roleName
	
	@classmethod
	def _makeDefaultRoleFunc(cls, roleName):
		"""returns an RST interpeted text role parser function returning
		an emphasis node with a dachs-ex-roleName class.
		"""
		def roleFunc(name, rawText, text, lineno, inliner, 
				options={}, content=[]):
			node = nodes.emphasis(rawText, text)
			node["classes"] = ["dachs-ex-"+roleName]
			return [node], []

		return roleFunc


class _Example(rend.DataFactory, base.MetaMixin):
	"""A formatted example.

	These get constructed with example meta items and glue these
	together with the nevow rendering system.

	An important role of this is the translation from the HTML class
	attribute values we use in ReStructuredText to the RDFa properties
	in the output.  The first class that has a matching property wins.

	There's the special exmeta render function that works like metahtml,
	except it's using the example's meta.
	"""
	def __init__(self, exMeta):
		base.MetaMixin.__init__(self)
		self.setMetaParent(exMeta)
		self.original = exMeta
		self.htmlId = re.sub("\W", "", base.getMetaText(
			self.original, "title", propagate=False))

	def data_id(self, ctx, data):
		return self.htmlId

	def _getTranslatedHTML(self):
		rawHTML = self.original.getContent("html")
		parsed = etree.fromstring("<container>%s</container>"%rawHTML)
		actOnClasses = set(RSTExtensions.classToProperty)

		for node in parsed.iterfind(".//*[@class]"):
			nodeClasses = set(node.attrib["class"].split())
			properties = " ".join(RSTExtensions.classToProperty[c] 
				for c in actOnClasses & nodeClasses)
			if properties:
				node.set("property", properties)

			# For now, I assume element content always is intended to
			# be the relation object (rather than a href that might\
			# be present and would take predence by RDFa
			if "href" in node.attrib or "src" in node.attrib:
				node.set("content", node.text)
		
		return etree.tostring(parsed, encoding="utf-8").decode("utf-8")

	def data_renderedDescription(self, ctx, data):
		if not hasattr(self.original, "renderedDescription"):
			self.original.renderedDescription = self._getTranslatedHTML()
		return self.original.renderedDescription
	

class Examples(grend.CustomTemplateMixin, grend.ServiceBasedPage):
	"""A renderer for examples for service usage.

	This renderer formats _example meta items in its service.  Its output
	is XHTML compliant to VOSI examples; clients can parse it to, 
	for instance, fill forms for service operation or display examples
	to users.

	The examples make use of RDFa to convey semantic markup.  To see
	what kind of semantics is contained, try 
	http://www.w3.org/2012/pyRdfa/Overview.html and feed it the
	example URL of your service.

	The default content of _example is ReStructuredText, and really, not much
	else  makes sense.  An example for such a meta item can be viewed by
	executing ``gavo admin dumpDF //userconfig``, in the tapexamples STREAM.

	To support annotation of things within the example text, DaCHS
	defines several RST extensions, both interpreted text roles (used like
	``:role-name:`content with blanks```) and custom directives (used
	to mark up blocks introduced by a single line like
	``.. directive-name ::`` (the blanks before and after the
	directive name are significant).

	Here's a the custom interpreted text roles:

	* *dl-id*: An publisher DID a service returns data for (used in 
	  datalink examples)
	* *table*: A (fully qualified) table name a TAP example query is
	  (particularly) relevant for; in HTML, this is also a link
	  to the table description.
	
	These are the custom directives:

	* *query*: The query discussed in a TAP example.
	"""
	name = "examples"
	checkedRenderer = False
	customTemplate = svcs.loadSystemTemplate("examples.html")

	@classmethod
	def isCacheable(self, segments, request):
		return True

	def render_title(self, ctx, data):
		return ctx.tag["Examples for %s"%base.getMetaText(
			self.service, "title")]

	def data_examples(self, ctx, data):
		"""returns _Example instances from the service metadata.
		"""
		for ex in self.service.iterMeta("_example"):
			yield _Example(ex)


################## RST extensions
# When you add anything here, be sure to update the Examples docstring
# above.

### ...for TAP

def _taptableRoleFunc(name, rawText, text, lineno, inliner,
		options={}, content=[]):
	node = nodes.reference(rawText, text,
		refuri="/tableinfo/%s"%text) 
	node["classes"] = ["dachs-ex-table"]
	return [node], []

RSTExtensions.makeTextRole("table", _taptableRoleFunc)
del _taptableRoleFunc

class _TAPQuery(rst.Directive):
	has_content = True

	def run(self):
		body = "\n".join(self.content)
		res = nodes.literal_block(body, body)
		res["classes"] = ["dachs-ex-query"]
		return [res]

RSTExtensions.addDirective("query", _TAPQuery)
del _TAPQuery


### ...for datalink

RSTExtensions.makeTextRole("dl-id")
