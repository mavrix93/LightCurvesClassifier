'''
Created on Jul 22, 2016

@author: martin
'''


from ttk import Frame, Label, Button, Style
from Tkinter import Tk, BOTH, Listbox, StringVar, END, RIGHT, BOTH, RAISED
import numpy as np
from conf.glo import OGLE_QSO_PATH
from db_tier.stars_provider import StarsProvider
from utils.stars import plotStarsPicture

class Example(Frame):
  
    def __init__(self, parent,stars):
        Frame.__init__(self, parent)   
         
        self.parent = parent
        self.stars = stars
        self.initUI()
        self.select_value = ""
        
        
    def initUI(self):
      
        self.parent.title("Listbox")          
        
        self.pack(fill=BOTH, expand=1)

        acts = np.linspace(0, 100, 100)

        lb = Listbox(self)
        for i in acts:
            lb.insert(END, i)
            
        lb.bind("<<ListboxSelect>>", self.onSelect)    
            
        lb.pack(pady=15)

        self.var = StringVar()
        self.label = Label(self, text=0, textvariable=self.var) 
               
        self.label.pack()

      
        self.parent.title("Buttons")
        self.style = Style()
        self.style.theme_use("default")
        
        frame = Frame(self, relief=RAISED, borderwidth=1)
        frame.pack(fill=BOTH, expand=True)
        
        self.pack(fill=BOTH, expand=True)
        
        closeButton = Button(self, text="Close")
        closeButton.pack(side=RIGHT, padx=5, pady=5)
        okButton = Button(self, text="OK", command=self.onClick())
        okButton.pack(side=RIGHT)
        
        
    def onSelect(self, val):
      
        sender = val.widget
        idx = sender.curselection()
        value = sender.get(idx)   
        self.var.set(value)
        self.select_value = value
        print self.select_value
        
    def onClick(self):
        print "jj"

def main():
    files_prov = StarsProvider().getProvider(path=OGLE_QSO_PATH,
                                         files_limit=15,
                                         obtain_method="file",
                                         star_class="quasar")
    quasars =  files_prov.getStarsWithCurves()
    root = Tk()
    ex = Example(root,quasars)
    root.geometry("300x250+300+300")
    root.mainloop()  


if __name__ == '__main__':
    main() 