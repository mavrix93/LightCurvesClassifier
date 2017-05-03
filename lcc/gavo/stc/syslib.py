"""
Arnold Rots' "library" of standard systems.

There's a dictionary of STC-S definitions of the systems that are compiled
and memoized on demand.  Thus, use the getLibrarySystem function below 
exclusively to access this content.

If and when there are additional library systems, you need to amend sysdefs.
"""

#c Copyright 2008-2016, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from gavo import utils


STC_IVOID = "ivo://STClib/CoordSys"


SYSDEFS = {
"TT-ICRS-TOPO": 
	"Time TT TOPOCENTER Position ICRS TOPOCENTER",
"TT-FK5-TOPO":
	"Time TT TOPOCENTER Position FK5 TOPOCENTER",
"UTC-ICRS-TOPO":
	"Time UTC TOPOCENTER Position ICRS TOPOCENTER",
"UTC-FK5-TOPO":
	"Time UTC TOPOCENTER Position FK5 TOPOCENTER",
"TT-ICRS-GEO":
	"Time TT GEOCENTER Position ICRS GEOCENTER",
"TT-FK5-GEO":
	"Time TT GEOCENTER Position FK5 GEOCENTER",
"UTC-ICRS-GEO":
	"Time UTC GEOCENTER Position ICRS GEOCENTER",
"UTC-ICRS-HELIO":
	"Time UTC GEOCENTER Position ICRS HELIOCENTER",
"UTC-FK5-GEO":
	"Time UTC GEOCENTER Position FK5 GEOCENTER",
"TDB-ICRS-BARY":
	"Time TDB BARYCENTER Position ICRS BARYCENTER",
"TDB-FK5-BARY":
	"Time TDB BARYCENTER Position FK5 BARYCENTER",
"TT-ICRS-BARY":
	"Time TT BARYCENTER Position ICRS BARYCENTER",
"UTC-HPC-TOPO":
	"Time UTC TOPOCENTER Position HPC TOPOCENTER CART2",
"UTC-HPR-TOPO":
	"Time UTC TOPOCENTER Position HPR TOPOCENTER SPHER2",
"UTC-HGS-TOPO":                                      
	"Time UTC TOPOCENTER Position HGS TOPOCENTER SPHER2",
"UTC-HGC-TOPO":                                      
	"Time UTC TOPOCENTER Position HGC TOPOCENTER SPHER2",
"TT-ICRS-HZ-TOPO":
	"Time TT TOPOCENTER Position ICRS TOPOCENTER SPHER2 Spectral"
	" TOPOCENTER unit Hz",
"TT-ICRS-OPT-BARY-TOPO":  
	"Time TT TOPOCENTER Position ICRS TOPOCENTER Redshift BARYCENTER OPTICAL",
"TT-ICRS-RADIO-LSR-TOPO": 
	"Time TT TOPOCENTER Position ICRS TOPOCENTER Redshift LSR RADIO",
}

@utils.memoized
def getLibrarySystem(sysId):
	"""returns a dm.CoordSys instance for sysId.

	sysId may be the full IVOID or just the fragment.
	Unknown sysIds result in NotFoundErrors.  Results are memoized, so
	make sure you do not mess with what you are returned.
	"""
	sysId = stripIVOID(sysId)
	try:
		sDef = SYSDEFS[sysId]
	except KeyError:
		raise utils.NotFoundError(sysId, "STC library system",
			"IVOA defined systems", hint="The systems available are defined"
			" in an appendix of the STC recommendation")
	from gavo.stc import stcsast
	system = stcsast.parseSTCS(sDef).astroSystem
	system.libraryId = "%s#%s"%(STC_IVOID, sysId)
	return system


def stripIVOID(sysId):
	"""returns sysId with the STC IVOID root removed.

	If sysId does not start with the STC IVOID, it is returned unchanged.
	"""
	if sysId.startswith(STC_IVOID):
		sysId = sysId[len(STC_IVOID)+1:]
	return sysId
