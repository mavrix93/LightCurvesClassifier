import gavo.imp.formal
from gavo.imp.formal.examples import main

class HiddenFieldsFormPage(main.FormExamplePage):
    
    title = 'Hidden Fields Form'
    description = 'A form with a hidden field.'
    
    def form_example(self, ctx):
        form = formal.Form()
        form.addField('hiddenString', formal.String(), widgetFactory=formal.Hidden)
        form.addField('hiddenInt', formal.Integer(), widgetFactory=formal.Hidden)
        form.addField('visibleString', formal.String())
        form.addAction(self.submitted)
        form.data = {
            'hiddenString': 'foo',
            'hiddenInt': 1,
        }
        return form

    def submitted(self, ctx, form, data):
        print data
