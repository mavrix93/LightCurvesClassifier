from datetime import date
from gavo.imp import formal
from gavo.imp.formal.examples import main

class MissingFormPage(main.FormExamplePage):

    title = 'Missing Values'
    description = 'Providing default values when missing'
    
    def form_example(self, ctx):
        form = formal.Form()
        form.addField('aString', formal.String(missing='<nothing>'))
        form.addField('aDate', formal.Date(missing=date(2005, 8, 1)))
        form.addAction(self.submitted)
        return form
    
    def submitted(self, ctx, form, data):
        print data
