"""
User-defined cores

XXX TODO: Revise this to have events before module replayed.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import os

from gavo import base
from gavo import utils
from gavo.svcs import core


class ModuleAttribute(base.UnicodeAttribute):
# XXX TODO: this is a bad hack since it assumes id on instance has already
# been set.  See above on improving all this using an event replay framework.
	typeDesc = "resdir-relative path to a module; no extension is allowed"

	def feed(self, ctx, instance, modName):
		modName = os.path.join(instance.rd.resdir, modName)
		userModule, _ = utils.loadPythonModule(modName)
		newCore = userModule.Core(instance.parent)
		ctx.idmap[instance.id] = newCore
		raise base.Replace(newCore)


class CustomCore(core.Core):
	"""A wrapper around a core defined in a module.

	This core lets you write your own cores in modules.

	The module must define a class Core.  When the custom core is
	encountered, this class will be instanciated and will be used
	instead of the CustomCore, so your code should probably inherit 
	core.Core.

	See `Writing Custom Cores`_ for details.
	"""
	name_ = "customCore"

	_module = ModuleAttribute("module", default=base.Undefined,
		description="Path to the module containing the core definition.")
