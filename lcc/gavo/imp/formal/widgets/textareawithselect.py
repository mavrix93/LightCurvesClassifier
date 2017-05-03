from zope.interface import implements
from nevow import tags as T, util
from gavo.imp.formal import iformal
from gavo.imp.formal.util import render_cssid


class TextAreaWithSelect(object):
    """
    A large text entry area that accepts newline characters.

    <textarea>...</textarea>
    """
    implements( iformal.IWidget )

    cols = 48
    rows = 6

    def __init__(self, original, cols=None, rows=None, values=None):
        self.original = original
        self.values = values
        if cols is not None:
            self.cols = cols
        if rows is not None:
            self.rows = rows

    def _renderTag(self, ctx, key, value, readonly):
        html = []
        tag=T.textarea(name=key, id=render_cssid(key), cols=self.cols, rows=self.rows)[value or '']
        if readonly:
            tag(class_='readonly', readonly='readonly')
        html.append(tag)
        if self.values is None:
            return html
        
        def renderOptions(ctx,options):
            for value,label in options:
                yield T.option(value=value)[label] 

            
        selecttrigger = T.select(name='%s__selecttrigger'%key, data=self.values)[ renderOptions ]


            
        form = iformal.IForm( ctx )
        js = T.xml("var x = document.getElementById('%(form)s');x.%(key)s.value += x.%(key)s__selecttrigger.options[x.%(key)s__selecttrigger.options.selectedIndex].value + &quot;\\n&quot;;"%{'key':key,'form':form.name})
        aonclick = T.a(onclick=js)[ 'add' ]
        html.append(T.div(class_="add")[selecttrigger,aonclick])
        return html

    def render(self, ctx, key, args, errors):
        if errors:
            value = args.get(key, [''])[0]
        else:
            value = iformal.IStringConvertible(self.original).fromType(args.get(key))
        return self._renderTag(ctx, key, value, False)

    def renderImmutable(self, ctx, key, args, errors):
        value = iformal.IStringConvertible(self.original).fromType(args.get(key))
        return self._renderTag(ctx, key, value, True)

    def processInput(self, ctx, key, args, default=None):
			# default is ignored here
        value = args.get(key, [''])[0].decode(util.getPOSTCharset(ctx))
        value = iformal.IStringConvertible(self.original).fromType(value)
        return self.original.validate(value)
