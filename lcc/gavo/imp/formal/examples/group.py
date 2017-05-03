from gavo.imp import formal
from gavo.imp.formal.examples import main

class GroupFormPage(main.FormExamplePage):
    
    title = 'Field Group Form'
    description = 'Groups of fields on a form'
    
    def form_example(self, ctx):

        def makeAddressGroup(name):
            address = formal.Group(name)
            address.add(formal.Field('address', formal.String()))
            address.add(formal.Field('city', formal.String()))
            address.add(formal.Field('postalCode', formal.String()))
            return address

        def makePersonGroup(name):
            person = formal.Group(name, cssClass=name)
            person.add(formal.Field('name', formal.String(required=True)))
            person.add(formal.Field('dateOfBirth', formal.Date(required=True)))
            person.add(makeAddressGroup('address'))
            return person

        form = formal.Form()
        form.add(formal.Field('before', formal.String()))
        form.add(makePersonGroup('me'))
        form.add(makePersonGroup('you'))
        form.add(formal.Field('after', formal.String()))
        form.addAction(self.submitted)

        return form

    def submitted(self, ctx, form, data):
        print form, data
