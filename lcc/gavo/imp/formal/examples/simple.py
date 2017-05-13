from gavo.imp import formal
from gavo.imp.formal.examples import main

class SimpleFormPage(main.FormExamplePage):
    
    title = 'Simple Form'
    description = 'Probably the simplest form possible.'
    
    def form_example(self, ctx):
        form = formal.Form()
        form.addField('aString', formal.String())
        form.addAction(self.submitted)
        return form

    def submitted(self, ctx, form, data):
        print form, data
