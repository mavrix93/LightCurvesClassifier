from nevow import url
from formal.examples import main

from gavo.imp import formal


class ActionButtonsPage(main.FormExamplePage):

    title = 'Action Button'
    description = 'Example of non-validating button, buttons with non-default labels, etc'
    
    def form_example(self, ctx):
        form = formal.Form()
        form.addField('aString', formal.String(required=True))
        form.addAction(self.submitted, label="Click, click, clickety-click!")
        form.addAction(self.redirect, 'back', validate=False)
        return form
    
    def submitted(self, ctx, form, data):
        print form, data
    
    def redirect(self, ctx, form, data):
        return url.rootaccessor(ctx)
