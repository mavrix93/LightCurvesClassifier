from zope.interface import implements
from gavo.imp import formal
from gavo.imp.formal import iformal
from gavo.imp.formal.examples import main

# A not-too-good regex for matching an IP address.
IP_ADDRESS_PATTERN = '^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$'

class ValidatorFormPage(main.FormExamplePage):
    
    title = 'Custom form validation'
    description = 'Example of installing additional validators and writing a new one'
    
    def form_example(self, ctx):
        form = formal.Form()
        # This actually installs a RequiredValidator for you.
        form.addField('required', formal.String(required=True))
        # Exactly the same as above, only with a "manually" installed validator.
        form.addField('required2', formal.String(validators=[formal.RequiredValidator()]))
        # Check for a minimum length, if anything entered.
        form.addField('atLeastFiveChars', formal.String(validators=[formal.LengthValidator(min=5)]))
        # Check for a minimum length, if anything entered.
        form.addField('ipAddress', formal.String(strip=True, validators=[formal.PatternValidator(regex=IP_ADDRESS_PATTERN)]))
        # Check for the word 'silly'
        form.addField('silly', formal.String(validators=[SillyValidator()]))
        # Check age is between 18 and 30
        form.addField('ohToBeYoungAgain', formal.Integer(validators=[formal.RangeValidator(min=18, max=30)]))
        form.addAction(self.submitted)
        return form

    def submitted(self, ctx, form, data):
        print form, data
        
class SillyValidator(object):
    """
    A pointless example that checks a specific word, 'silly', is entered.
    """
    implements(iformal.IValidator)
    
    word = u'silly'
    
    def validate(self, field, value):
        if value is None:
            return
        if value.lower() != self.word.lower():
            raise formal.FieldValidationError(u'You must enter \'%s\''%self.word)
