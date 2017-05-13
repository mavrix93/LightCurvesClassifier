"""
Determining equivalence for STC systems.

Frequenently, one needs to decide if two systems are "close enough" to
work together, e.g., when building geometries or for ADQL geometry
predicates.  This code lets you define matching policies.
"""

#c Copyright 2008-2016, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import re

from gavo import utils


_identifierPat = re.compile("[a-zA-Z_][a-zA-Z_]*$")

@utils.memoized
def makeKeyGetter(key):
	"""returns a function getting key from an object.

	key is dot-seperated sequence of python identifiers (this is checked; a
	ValueError is raised at generation time for malformed keys).

	This function is used to generate functions accessing parts of
	STC trees.  If any attribute within key does not exist, the generated
	functions return None.
	"""
	if (not key.strip() 
			or None in (_identifierPat.match(p) for p in key.split("."))):
		raise ValueError("'%s' is no valid STC key."%key)
	getterSrc = "\n".join([
		"def get(ob):",
		"  try:",
		"    return ob.%s"%key,
		"  except AttributeError:",
		"    return None"])
	ns = {}
	exec getterSrc in ns
	return ns["get"]


class EquivalenceCondition(object):
	"""A base class for EquivalencePolicy elements.

	An EquivalenceCondition has a 
	check(sys1, sys2) -> boolean 
	method.  Everything else is up to the individual objects.
	"""
	def check(self, sys1, sys2):
		"""returns true when sys1 and sys2 are equivalent as far as this
		condition is concerned.

		sysN are dm.CoordSys instances.
		"""
		return False
	
	def _checkWithNone(self, val1, val2):
		"""returns True if val1 or val2 are None of if they are equal.

		This should be the default logic for Equ.Pols.
		"""
		if val1 is None or val2 is None:
			return True
		return val1==val2


class KeysEquivalent(EquivalenceCondition):
	"""An equivalence condition specifying a certain key being equal if
	non-None in both objects.

	key is a dot-seperated sequence of attribute names withing STC system
	objects.
	"""
	def __init__(self, key):
		self.getKey = makeKeyGetter(key)

	def check(self, sys1, sys2):
		return self._checkWithNone(
			self.getKey(sys1), self.getKey(sys2))


class RefFramesEquivalent(EquivalenceCondition):
	"""An equivalence condition tailored for reference frames.

	It considers ICRS and FK5 J2000 equivalent.
	"""
	def __init__(self):
		self.getFrame = makeKeyGetter("spaceFrame.refFrame")
		self.getEquinox = makeKeyGetter("spaceFrame.equinox")
	
	def check(self, sys1, sys2):
		frame1, frame2 = self.getFrame(sys1), self.getFrame(sys2)
		eq1, eq2 = self.getEquinox(sys1), self.getEquinox(sys2)
		if (self._checkWithNone(frame1, frame2) 
				and self._checkWithNone(eq1, eq2)):
			return True
		# Yikes.  If we get more cases like this, we need to think of something 
		if (set([frame1, frame2])==set(["ICRS", "FK5"])):
			# we should only have one equinox -- get it and check it.
			eq = [eq for eq in (eq1, eq2) if eq][0]
			if eq.startswith("J2000"):
				return True
		return False


class EquivalencePolicy(object):
	"""A policy specifying when two STC system objects are considered equivalent.

	checkedKeys is a sequence of EquivalenceConditions or strings.  If
	strings are passed, they are turned into KeysEquivalent conditions
	for the keys specified in the strings.

	You can also pass entire STC trees to match.
	"""
	def __init__(self, checkedKeys):
		self.conditions = []
		for cond in checkedKeys:
			if isinstance(cond, EquivalenceCondition):
				self.conditions.append(cond)
			else:
				self.conditions.append(KeysEquivalent(cond))
	
	def match(self, ast1, ast2):
		ast1 = getattr(ast1, "astroSystem", ast1)
		ast2 = getattr(ast2, "astroSystem", ast2)
		for cond in self.conditions:
			if not cond.check(ast1, ast2):
				return False
		return True


# The default equivalence policy.  Currently ignores refFrames on space and
# time.
defaultPolicy = EquivalencePolicy([
	RefFramesEquivalent(),
	"timeFrame.timeScale",
	"spaceFrame.flavor",
	"spaceFrame.nDim",
	"spectralFrame.refPos.standardOrigin",
	"redshiftFrame.refPos.standardOrigin",
	"redshiftFrame.type",
	"redshiftFrame.dopplerDef",])
