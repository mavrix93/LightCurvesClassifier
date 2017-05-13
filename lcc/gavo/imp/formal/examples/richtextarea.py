from gavo.imp import formal
from gavo.imp.formal.examples import main
from gavo.imp.formal import RichText



class RichTextAreaFormPage(main.FormExamplePage):
    
    title = 'Rich Text widget'
    description = 'The Rich widget captures a textarea value and a type.'
    
    def form_example(self, ctx):
        form = formal.Form()
        form.addField('RichTextString', formal.RichTextType(required=True),
                widgetFactory = formal.widgetFactory(formal.RichTextArea, parsers=[('plain','Plain Text'),('reverseplain','Reversed Plain Text')]))
        form.addField('RichTextStringNotRequired', formal.RichTextType(),
                widgetFactory = formal.widgetFactory(formal.RichTextArea, parsers=[('plain','Plain Text'),('reverseplain','Reversed Plain Text'),('html','XHTML')]))
        form.addField('RichTextStringOnlyOneParser', formal.RichTextType(required=True),
                widgetFactory = formal.widgetFactory(formal.RichTextArea, parsers=[('markdown','MarkDown')]))
        form.addAction(self.submitted)
        return form

    def submitted(self, ctx, form, data):
        print form,data
