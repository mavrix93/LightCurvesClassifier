"""
File- and directory related helpers for resource utilites.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import os
import re
import warnings

from gavo import base
from gavo import rscdef
from gavo.base import parsecontext

class Error(base.Error):
	pass


fnamePat = re.compile(r"([^.]*)(\..*)")
def stingySplitext(fName):
	"""returns name, extension for fName.

	The main difference to os.path.splitext is that the main name is not allowed
	to contain dots and the extension can contain more than one dot.

	fName is supposed to be a single file name without any path specifier
	(you might get aways with it if your directores do not contain dots, though).
	"""
	mat = fnamePat.match(fName)
	if mat:
		return mat.group(1), mat.group(2)
	else:
		return fName, ""


class FileRenamer(object):
	"""is a name mapper for file rename operations and the like.

	Warning: This whole thing more or less pretends there are no
	symlinks.
	"""
	def __init__(self, map, showOnly=False):
		self.map, self.showOnly = map, showOnly

	@classmethod
	def loadFromFile(cls, inF, **kwargs):
		"""returns a name map for whatever is serialized in the file inF.

		The format of fName is line-base, with each line being one of
		
			- empty -- ignored
			- beginning with a hash -- ignored
			- <old> -> <new> -- introducing a map
		"""
		map = {}
		try:
			for ln in inF:
				if not ln.strip() or ln.strip().startswith("#"):
					continue
				old, new = [s.strip() for s in ln.split("->", 2)]
				if map.has_key(old):
					raise Error("Two mappings for %s"%old)
				map[old] = new
		except ValueError:
			raise base.ui.logOldExc(Error("Invalid mapping line: %s"%repr(ln)))
		return cls(map, **kwargs)

	def getFileMap(self, path):
		"""returns a dictionary old->new of renames within path.
		"""
		fileMap = {}
		for dir, subdirs, fNames in os.walk(path):
			for fName in fNames:
				stem, ext = stingySplitext(fName)
				if stem in self.map:
					fileMap[os.path.join(dir, fName)] = os.path.join(dir,
						self.map[stem]+ext)
		return fileMap
	
	def makeRenameProc(self, fileMap):
		"""returns a sequence of (old,new) pairs that, when executed, keep
		any new from clobbering any existing old.

		The function will raise an Error if there's a cycle in fileMap.  fileMap
		will be destroyed by this procedure
		"""
		proc = []
		def addOp(src, dest, sources=None):
			if sources is None:
				sources = set()
			if dest in sources:
				raise Error("Rename cycle involving %s"%sources)
			if dest in fileMap:
				sources.add(src)
				addOp(dest, fileMap.pop(dest), sources)
			proc.append((src, dest))
		while fileMap:
			addOp(*fileMap.popitem())
		return proc

	def renameInPath(self, path):
		"""performs a name map below path.

		The rules are:

			- extensions are ignored -- if we map foo to bar, foo.txt and foo.asc
				will be renamed bar.txt and foo.txt respectively
			- the order of statements in the source is irrelevant.  However, we try
				not to clobber anything we've just renamed and will complain about
				cycles.  Also, each file will be renamed not more than once.
		"""
		fileMap = self.getFileMap(path)
		for src, dest in self.makeRenameProc(fileMap):
			if os.path.exists(dest):
				raise Error("Request to clobber %s"%repr(dest))
			if os.path.exists(src):
				if self.showOnly:
					print "%s -> %s"%(src, dest)
				else:
					os.rename(src, dest)
			else:
				if not os.path.exists(dest):
					warnings.warn("Neither source nor dest found in pair %s, %s"%(src,
						dest))

	def renameInPaths(self, pathList):
		for path in pathList:
			self.renameInPath(path)


def iterSources(ddId, args=[]):
	"""iterates over the current sources of the data descriptor ddId (which is
	qualified like rdId#id

	If you pass something nonempty to args, an iterator over its values
	will be returned.  This is for convenient implementation of scripts
	that work on CL arguments if given, on all files otherwise.
	"""
	if args:
		return iter(args)
	else:
		if ddId.count("#")!=1:
			raise base.ReportableError("iterSources must get a fully qualified id"
				" (i.e., one with exactly one hash).")
		dd = parsecontext.resolveCrossId(ddId, rscdef.DataDescriptor)
		return dd.sources.iterSources()

