from gavo.imp import formal
from gavo.imp.formal.examples import main

class RequiredFormPage(main.FormExamplePage):

    title = 'Required Fields'
    description = 'Demonstration of required fields'

    def form_example(self, ctx):
        form = formal.Form()
        form.addField('name', formal.String(required=True))
        form.addField('age', formal.Integer())
        form.addAction(self.submitted)
        return form
    
    def submitted(self, ctx, form, data):
        print data
