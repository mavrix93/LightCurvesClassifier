from gavo.imp import formal
from gavo.imp.formal.examples import main
from gavo.imp.formal.widgets.textareawithselect import TextAreaWithSelect

class TextAreaWithSelectFormPage(main.FormExamplePage):
    
    title = 'Text area with select'
    description = 'text area with a select box to append new info'
    
    def form_example(self, ctx):
        form = formal.Form()
        form.addField('myTextArea', formal.String(),
               formal.widgetFactory(TextAreaWithSelect,values=(('aval','alabel'),('bval','blabel'))  ))

        form.addAction(self.submitted)
        return form

    def submitted(self, ctx, form, data):
        print form, data


