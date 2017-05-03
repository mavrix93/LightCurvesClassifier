from gavo.imp import formal
from gavo.imp.formal.examples import main

class FileUploadFormPage(main.FormExamplePage):

    title = 'File Upload'
    description = 'Uploading a file'
    
    def form_example(self, ctx):
        form = formal.Form()
        form.addField('file', formal.File())
        form.addAction(self.submitted)
        return form
    
    def submitted(self, ctx, form, data):
        print form, data
