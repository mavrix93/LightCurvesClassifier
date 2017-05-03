"""
A manual registry of renderers.

Renderers are the glue between a core and some output.  A service is the
combination of a subset of renderers and a core.

Renderers are actually defined in web.grend, but we need some way to
get at them from svcs and above, so the registry is kept here.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from gavo import base
from gavo import utils


RENDERER_REGISTRY = {
	'admin': ("web.adminrender", "AdminRenderer"),
	'api': ("web.vodal", "APIRenderer"),
	'availability': ("web.vosi", "VOSIAvailabilityRenderer"),
	'capabilities': ("web.vosi", "VOSICapabilityRenderer"),
	'custom': ("web.customrender", "CustomRenderer"),
	'dlasync': ("web.vodal", "DatalinkAsyncRenderer"),
	'dlget': ("web.vodal", "DatalinkGetDataRenderer"),
	'dlmeta': ("web.vodal", "DatalinkGetMetaRenderer"),
	'docform': ("web.formrender", "DocFormRenderer"),
	'examples': ("web.examplesrender", "Examples"),
	'external': ("web.metarender", "ExternalRenderer"),
	'fixed': ("web.constantrender", "FixedPageRenderer"),
	'form': ("web.formrender", "Form"),
	'get': ("web.productrender", "ProductRenderer"),
	'img.jpeg': ("web.oddrender", "JpegRenderer"),
	'info': ("web.metarender", "ServiceInfoRenderer"),
	'logout': ("web.metarender", "LogoutRenderer"),
	'mimg.jpeg': ("web.oddrender", "MachineJpegRenderer"),
	'mupload': ("web.uploadservice", "MachineUploader"),
	'pubreg.xml': ("web.vodal", "RegistryRenderer"),
	'qp': ("web.qprenderer", "QPRenderer"),
	'rdinfo': ("web.metarender", "RDInfoRenderer"),
	'scs.xml': ("web.vodal", "SCSRenderer"),
	'siap.xml': ("web.vodal", "SIAPRenderer"),
	'soap': ("web.soaprender", "SOAPRenderer"),
	'ssap.xml': ("web.vodal", "SSAPRenderer"),
	'static': ("web.constantrender", "StaticRenderer"),
	'tableinfo': ("web.metarender", "TableInfoRenderer"),
	'tableMetadata': ("web.vosi", "VOSITablesetRenderer"),
	'tablenote': ("web.metarender", "TableNoteRenderer"),
	'tap': ("web.taprender", "TAPRenderer"),
	'upload': ("web.uploadservice", "Uploader"),
}


@utils.memoized
def getRenderer(name):
	if name not in RENDERER_REGISTRY:
		raise base.NotFoundError(name, "renderer", "registred renderers")
	cls = utils.loadInternalObject(*RENDERER_REGISTRY[name])
	if cls.name!=name:
		raise base.ReportableError("Internal Error: Renderer %s is registred"
			" under the wrong name."%name,
			hint="This is probably a typo in svcs.renderers; it needs"
			" to be fixed there")
	return cls

