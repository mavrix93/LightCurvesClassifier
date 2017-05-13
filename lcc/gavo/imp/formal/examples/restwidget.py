from gavo.imp import formal
from gavo.imp.formal.examples import main

# Let the examples run if docutils is not installed
try:
    import docutils
except ImportError:
    import warnings
    warnings.warn("docutils is not installed")
    docutilsAvailable = False
else:
    docutilsAvailable = True


if docutilsAvailable:

    from docutils.writers.html4css1 import Writer, HTMLTranslator
    from docutils import nodes

    class CustomisedHTMLTranslator(HTMLTranslator):
        def visit_newdirective_node(self, node):
            self.body.append('<div>Some HTML with a %s parameter</div>\n'%(node.attributes['parameter'],))

        def depart_newdirective_node(self, node):
            pass

    class newdirective_node(nodes.General, nodes.Inline, nodes.TextElement):
        pass

    def newdirective(name, arguments, options, content, lineno,
                     content_offset, block_text, state, state_machine):
        return [newdirective_node('', parameter=arguments[0])]

    newdirective.arguments = (1, 0, 0)
    newdirective.options = None

    from docutils.parsers.rst import directives
    directives.register_directive('newdirective', newdirective)


class ReSTWidgetFormPage(main.FormExamplePage):
    
    title = 'ReST widget'
    description = 'The ReST widget captures ReST and previews as HTML.'
    
    def form_example(self, ctx):
        form = formal.Form()
        form.addField('restString', formal.String(required=True),
                widgetFactory=formal.ReSTTextArea)
        if docutilsAvailable:
            w = Writer()
            w.translator_class = CustomisedHTMLTranslator
            form.addField('customRestString', formal.String(required=True),
                    formal.widgetFactory(formal.ReSTTextArea, restWriter=w))
        form.addAction(self.submitted)
        return form

    def submitted(self, ctx, form, data):
        print form, data
