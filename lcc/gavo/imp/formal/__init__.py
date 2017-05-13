"""A package (for Nevow) for defining the schema, validation and rendering of
HTML forms.
"""


version_info = (0, 12, 0)
version = '.'.join([str(i) for i in version_info])


from nevow import static
from gavo.imp.formal.types import *
from gavo.imp.formal.validation import *
from gavo.imp.formal.widget import *
from gavo.imp.formal.widgets.restwidget import *
from gavo.imp.formal.widgets.multiselect import *
from gavo.imp.formal.widgets.richtextarea import *
from gavo.imp.formal.form import (
	Form, Field, Group, ResourceMixin, renderForm, FORMS_KEY)
from gavo.imp.formal import iformal

def widgetFactory(widgetClass, *a, **k):
    def _(original):
        return widgetClass(original, *a, **k)
    return _

try:
    import pkg_resources
except ImportError:
		# this is broken from within DaCHS
    import os.path
    defaultCSS = static.File(os.path.join(os.path.split(__file__)[0], 'formal.css'))
    formsJS = static.File(os.path.join(os.path.split(__file__)[0], 'js'))
else:
    from gavo.imp.formal.util import LazyResource
    defaultCSS = LazyResource(lambda: static.File(pkg_resources.resource_filename('gavo', 'resources/web/css/formal.css')))
    formsJS = LazyResource(lambda: static.File(pkg_resources.resource_filename('gavo', 'resources/web/js/formal.js')))

# Register standard adapters
from twisted.python.components import registerAdapter
from gavo.imp.formal import converters
from gavo.imp.formal.util import SequenceKeyLabelAdapter
registerAdapter(TextInput, String, iformal.IWidget)
registerAdapter(TextInput, Integer, iformal.IWidget)
registerAdapter(TextInput, Float, iformal.IWidget)
registerAdapter(Checkbox, Boolean, iformal.IWidget)
registerAdapter(DatePartsInput, Date, iformal.IWidget)
registerAdapter(TextInput, Time, iformal.IWidget)
registerAdapter(FileUploadRaw, File, iformal.IWidget)
registerAdapter(TextAreaList, Sequence, iformal.IWidget)
registerAdapter(SequenceKeyLabelAdapter, tuple, iformal.IKey)
registerAdapter(SequenceKeyLabelAdapter, tuple, iformal.ILabel)
registerAdapter(converters.NullConverter, String, iformal.IStringConvertible)
registerAdapter(converters.DateToDateTupleConverter, Date, iformal.IDateTupleConvertible)
registerAdapter(converters.BooleanToStringConverter, Boolean, iformal.IBooleanConvertible)
registerAdapter(converters.BooleanToStringConverter, Boolean, iformal.IStringConvertible)
registerAdapter(converters.IntegerToStringConverter, Integer, iformal.IStringConvertible)
registerAdapter(converters.FloatToStringConverter, Float, iformal.IStringConvertible)
registerAdapter(converters.DateToStringConverter, Date, iformal.IStringConvertible)
registerAdapter(converters.TimeToStringConverter, Time, iformal.IStringConvertible)
registerAdapter(converters.NullConverter, File, iformal.IFileConvertible)
registerAdapter(converters.NullConverter, Sequence, iformal.ISequenceConvertible)
registerAdapter(converters.SequenceToStringConverter, Sequence, iformal.IStringConvertible)
try:
    Decimal
except NameError:
    pass
else:
    registerAdapter(TextInput, Decimal, iformal.IWidget)
    registerAdapter(converters.DecimalToStringConverter, Decimal, iformal.IStringConvertible)
del SequenceKeyLabelAdapter
del registerAdapter
