import warnings

warnings.warn(
        "The htmleditor module is deprecated. To use an HTML editor with " \
        "formal, render your field as a formal.TextArea and use JavaScript " \
        "to turn the textarea into a HTML editor.",
        DeprecationWarning,
        stacklevel=2)

from nevow import tags as T, util
from gavo.imp.formal import iformal
from zope.interface import implements


tinyMCEGlue = T.xml("""
    <!-- tinyMCE -->
    <script language="javascript" type="text/javascript" src="/tiny_mce/tiny_mce.js"></script>
    <script language="javascript" type="text/javascript">
       tinyMCE.init({
          mode : "specific_textareas"
          theme: 'advanced',
          theme_advanced_toolbar_location: 'top',
          theme_advanced_toolbar_align: 'left'
       });
    </script>
    <!-- /tinyMCE -->
    """ )
    

class TinyMCE(object):
    implements( iformal.IWidget )
    
    def __init__(self, original):
        self.original = original
    
    def render(self, ctx, key, args, errors):
        if errors:
            value = args.get(key, [''])[0]
        else:
            value = iformal.IStringConvertible(self.original).fromType(args.get(key))
        return T.textarea(name=key, id=key, mce_editable='true')[value or '']

    def renderImmutable(self, ctx, key, args, errors):
        value = iformal.IStringConvertible(self.original).fromType(args.get(key))
        if value:
            value=T.xml(value)
        else:
            value=''
        return T.div(id=key, class_="readonly-textarea-container") [
            T.div(class_='readonly-textarea readonly')[value]
        ]
        
    def processInput(self, ctx, key, args, default=''):
        value = args.get(key, [default])[0].decode(util.getPOSTCharset(ctx))
        value = iformal.IStringConvertible(self.original).toType(value)
        return self.original.validate(value)

