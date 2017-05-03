from datetime import datetime
from gavo.imp import formal
from gavo.imp.formal.examples import main

class PrepopulateFormPage(main.FormExamplePage):

    title = 'Prepopulate'
    description = 'Example of prepopulating form fields'
    
    def form_example(self, ctx):
        form = formal.Form()
        form.addField('aString', formal.String())
        form.addField('aTime', formal.Time())
        form.addAction(self.submitted)
        form.data = {
            'aTime': datetime.utcnow().time(),
            }
        return form
    
    def submitted(self, ctx, form, data):
        print data

