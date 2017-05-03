from gavo.imp import formal
from gavo.imp.formal.examples import main

class DatesTimesFormPage(main.FormExamplePage):

    title = 'Dates'
    description = 'Date entry examples'
    
    def form_example(self, ctx):
        form = formal.Form()
        form.addField('isoFormatDate', formal.Date(), formal.TextInput)
        form.addField('datePartsSelect', formal.Date(), formal.widgetFactory(formal.DatePartsSelect, dayFirst=True))
        form.addField('monthFirstDate', formal.Date(), formal.DatePartsInput)
        form.addField('dayFirstDate', formal.Date(), formal.widgetFactory(formal.DatePartsInput, dayFirst=True))
        form.addField('monthYearDate', formal.Date(), formal.MMYYDatePartsInput)
        form.addField('twoCharYearDate', formal.Date(), formal.widgetFactory(formal.DatePartsInput, twoCharCutoffYear=70))
        form.addField('time', formal.Time())
        form.addAction(self.submitted)
        return form
    
    def submitted(self, ctx, form, data):
        print form, data
