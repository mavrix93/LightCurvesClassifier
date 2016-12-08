'''
Created on Jan 7, 2016

@author: Martin Vo
'''


import numpy as np
import matplotlib.pyplot as plt
from entities.exceptions import InvalidFile, InvalidFilesPath

#TODO: Move more "load lc from file" logic into FileManager


class LightCurve:
    BAD_VALUES = -99   
    TIME_COL = 0        #Order of columns in the light curve file
    MAG_COL = 1
    ERR_COL = 2
    MIN_LENGHT = 20     #Minimal amount of observations in light curve in order to be accepted

    def __init__(self, param, meta):
        '''
        Parameters:
        -----------
            param : list, array, string
                Light curve data or path to the file of light curve.
                
                   Option I:
                        List (numpy array) of 3 lists(time, mag, err) 
                        
                    Option II:                    
                        List (numpy array) of N lists (time, mag  and err) one per obs
                        
                    Option III:
                        Name of file (with path) where columns times, magnitudes, errors
                        
            meta : dict
                Optional metadata of the light curve. Recommended are these keys:
                
                    xlabel - name of the first array
                    
                    xlabel_unit - unit of the first array
                    
                    ylabel - name of the second array
                    
                    ylabel_unit - unit of the second array
                    
                    color - filter name of the light curve
        '''

        if (type(param) is list or type(param) is tuple):
            param = np.array(param)
        
        # Light curve could be made from:
        # OPTION 1:    Name of the file (in this case default path will be used) or whole path contains file name
        if (type(param) is str or type(param) is unicode): 
            self.openLC(param)
            
        # OPTION 2:    List of three lists (time,mag,err)    
        elif (type(param) is np.ndarray):
            #T ranspose if there are list of tuples (time, mag,err)
            if (len(param) > 3):
                param = param.transpose()

            param[0] = np.array(param[0])
            param[1] = np.array(param[1])
                
            if (len(param)==2):
                param=np.concatenate([param,[np.zeros(len(param[0]))]])
            else:                
                param[2] = np.array(param[2])
            

            self.time = param[0]
            self.mag = param[1]
            self.err = param[2]
        else:
            raise Exception("Wrong object parameters\nLightCurve object is not created")
            
        # Delete all bad values in light curve
        bad_values_postions = np.where(self.mag == self.BAD_VALUES)
        self.mag = np.delete(self.mag,bad_values_postions) 
        self.time = np.delete(self.time,bad_values_postions) 
        self.err = np.delete(self.err,bad_values_postions)
        self.meta = meta
     
    def __str__(self):
        txt = "Time\tMag\tErr\n"
        txt += "-"*(len(txt)+6) + "\n"
        for i in range(0,len(self.time)):
            txt += "%.02f\t%.02f\t%.02f\n" % ( self.time[i], self.mag[i], self.err[i])
            
        return txt       
    
    
    def openLC(self,fileWithPath):
        '''In case of string param in constructor --> open light curve file''' 
           
        
        # Try to open the file
        try:
            a = np.loadtxt(fileWithPath,usecols=(self.TIME_COL,self.MAG_COL,self.ERR_COL),skiprows=0)
        except IndexError:
            a = np.loadtxt(fileWithPath,usecols=(self.TIME_COL,self.MAG_COL,self.ERR_COL),skiprows=2)
        except IOError,Argument:
            raise InvalidFilesPath("\nCannot open light curve file\n %s" %Argument)
            
        if (len(a)>= self.MIN_LENGHT):  
            self.mag = a[:,1]
            self.time = a[:,0]
            self.err = a[:,2]
            if not (len(self.mag) == len(self.time) == len(self.err)):
                raise InvalidFile("Length of columns in light curve file is not the same")
            
        else:
            print "Star curve file is empty or too short!"
            self.mag = []
            self.time = []
            
    
        
    def plotLC(self):
        '''Plot light curve'''
        
        plt.errorbar(self.time,self.mag, self.err,fmt='o', ecolor='r')
        plt.show()
        
    def getMeanMag(self):
        return np.mean(self.mag)
    
    def getStdMag(self):
        return np.std(self.mag)

    
    
        
        



        
        