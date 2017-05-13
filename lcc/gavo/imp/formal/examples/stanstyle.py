from gavo.imp.formal import Field, Form, Group, String
from gavo.imp.formal.examples import main

class StanStyleFormPage(main.FormExamplePage):
    
    title = 'Stan-Style Form'
    description = 'Building a Form in a stan style'
    
    def form_example(self, ctx):
        form = Form()[
            Group("me")[
                Field("firstNames", String()),
                Field("lastName", String()),
                ],
            Group("you")[
                Field("firstNames", String()),
                Field("lastName", String()),
                ],
            ]
        form.addAction(self.submitted)
        return form

    def submitted(self, ctx, form, data):
        print data
        
