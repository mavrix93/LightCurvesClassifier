try:
    import decimal
    haveDecimal = True
except ImportError:
    haveDecimal = False
from gavo.imp import formal
from gavo.imp.formal.examples import main

class TypesFormPage(main.FormExamplePage):

    title = 'Form Types'
    description = 'Example of using different typed fields.'

    def form_example(self, ctx):
        form = formal.Form()
        form.addField('aString', formal.String())
        form.addField('aInteger', formal.Integer())
        form.addField('aFloat', formal.Float())
        if haveDecimal:
            form.addField('aDecimal', formal.Decimal())
        form.addField('aBoolean', formal.Boolean())
        form.addField('aDate', formal.Date())
        form.addField('aTime', formal.Time())
        form.addAction(self.submitted)
        return form
    
    def submitted(self, ctx, form, data):
        print data

