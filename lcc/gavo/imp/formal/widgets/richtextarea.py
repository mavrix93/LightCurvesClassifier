"""
Rich text area widget.
"""

from nevow import inevow, loaders, rend, tags as T, util
from gavo.imp.formal import iformal, widget, types
from gavo.imp.formal.util import render_cssid
from zope.interface import Interface

class RichTextArea(widget.TextArea):
    """
    A large text entry area that can be used for different formats of formatted text (rest, html, markdown, texy)
    """
    def __init__(self, original, **kwds):
        parsers = kwds.pop('parsers', None)
        super(RichTextArea, self).__init__(original, **kwds)
        self.parsers = parsers

    def _namer(self, prefix):
        def _(part):
            return '%s__%s' % (prefix,part)
        return _

    def _renderTag(self, ctx, tparser, tvalue, namer, readonly):
        tag=T.invisible()
        if len(self.parsers) > 1:
            tp = T.select(name=namer('tparser'),id=render_cssid(namer('tparser')))
            if readonly:
                tp(class_='disabled', disabled='disabled')        
            
            for k,v in self.parsers:
                if k == tparser:
                    tp[T.option(selected='selected',value=k)[ v ]]
                else:
                    tp[T.option(value=k)[ v ]]
        else:
            tp = T.input(type='hidden',name=namer('tparser'),id=render_cssid(namer('tparser')),value=self.parsers[0][0])
        ta=T.textarea(name=namer('tvalue'), id=render_cssid(namer('tvalue')), cols=self.cols, rows=self.rows)[tvalue or '']
        if readonly:
            ta(class_='readonly', readonly='readonly')
        tag[tp,T.br,ta]
        return tag


    def render(self, ctx, key, args, errors):
        namer = self._namer(key)
        if errors:
            tparser = args.get(namer('tparser'), [''])[0]
            tvalue = args.get(namer('tvalue'), [''])[0]
        else:
            value = args.get(key)
            if value is not None:
                tparser = value.type
                tvalue = value.value
            else:
                tparser = None
                tvalue = ''
        
        return self._renderTag(ctx, tparser, tvalue, namer, False)
        
    def renderImmutable(self, ctx, key, args, errors):
        namer = self._namer(key)
        if errors:
            tparser = args.get(namer('tparser'), [''])[0]
            tvalue = args.get(namer('tvalue'), [''])[0]
        else:
            value = args.get(key)
            if value is not None:
                tparser = value.type
                tvalue = value.value
            else:
                tparser = None
                tvalue = ''
        
        return self._renderTag(ctx, tparser, tvalue, namer, True)
    
    def processInput(self, ctx, key, args, default=None):
				# default is ignored here
        namer = self._namer(key)
        value = [args.get(namer(part), [''])[0].strip().decode(util.getPOSTCharset(ctx)) for part in ('tparser', 'tvalue')]
        return self.original.validate(types.RichText(*value))


__all__ = ["RichTextArea"]
