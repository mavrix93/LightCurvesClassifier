from twisted.internet import defer
from datetime import date
from gavo.imp import formal
from gavo.imp.formal.examples import main

# A boring list of (value, label) pairs.
strings = [
    ('foo', 'Foo'),
    ('bar', 'Bar'),
    ]

# A list of dates with meaningful names.
dates = [
    (date(2005, 01, 01), 'New Year Day'),
    (date(2005, 11, 06), 'My Birthday'),
    (date(2005, 12, 25), 'Christmas Day'),
    ]

tuples = [
         (('a',1), 'a1'),
         (('b',1), 'b1'),
         (('c',1), 'c1'),
         ]
        
def data_strings(ctx, data):
    # Let's defer it, just for fun.
    return defer.succeed(strings)

# A different "none" option tuple
differentNone = ('none value', '- select -')
    
class SelectionFormPage(main.FormExamplePage):

    title = 'Selection widgets'
    description = 'Example of the various selection widgets'
    
    def form_example(self, ctx):
        form = formal.Form()
        form.addField('required', formal.String(required=True))
        form.addField('oneString', formal.String(),
                formal.widgetFactory(formal.SelectChoice, options=strings))
        form.addField('anotherString', formal.String(),
                formal.widgetFactory(formal.SelectChoice, options=data_strings))
        form.addField('oneMoreString', formal.String(required=True),
                formal.widgetFactory(formal.RadioChoice, options=data_strings))
        form.addField('oneDate', formal.Date(),
                formal.widgetFactory(formal.SelectChoice, options=dates))
        form.addField('multipleStrings', formal.Sequence(formal.String()),
                formal.widgetFactory(formal.CheckboxMultiChoice,
                    options=data_strings))
        form.addField('multipleDates', formal.Sequence(formal.Date()),
                formal.widgetFactory(formal.CheckboxMultiChoice, options=dates))

        form.addField('multipleTuples', formal.Sequence(formal.Sequence()),
                formal.widgetFactory(formal.CheckboxMultiChoice,
                    options=tuples))
        
        form.addField('differentNoneSelect', formal.String(),
                formal.widgetFactory(formal.SelectChoice, options=strings,
                    noneOption=differentNone))
        form.addField('differentNoneRadios', formal.String(),
                formal.widgetFactory(formal.RadioChoice, options=data_strings,
                    noneOption=differentNone))
        form.addField('selectOther', formal.String(),
                formal.widgetFactory(formal.SelectOtherChoice, options=['Mr',
                    'Mrs']))
        form.addField('selectOtherCustomOther', formal.String(),
                formal.widgetFactory(formal.SelectOtherChoice, options=['Mr',
                    'Mrs'], otherOption=('...','Other (Please Enter)')))
        form.addField('selectOtherRequired', formal.String(required=True),
                formal.widgetFactory(formal.SelectOtherChoice, options=['Mr',
                    'Mrs']))
        form.addField('multiselect', formal.String(),
                formal.widgetFactory(formal.MultiselectChoice, options=strings))
        form.addAction(self.submitted)
        return form
    
    def submitted(self, ctx, form, data):
        print form, data
