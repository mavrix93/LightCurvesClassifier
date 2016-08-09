'''
Created on Feb 18, 2016

@author: Martin Vo
'''
import abc
import numpy as np

#TODO: Merge coordinate classes into one

class AbstractCoordinate(object):
    __metaclass__ = abc.ABCMeta
    '''
    This is abstract class for all astro coordinate type classes
    '''
    
    HOURS_DESIG = ["hours","hour","h"]
    RADIANS_DESIG = ["radians","rad"]

    def __init__(self, degrees,coo_format,MIN_VALUE,MAX_VALUE,HOUR_TO_DEGREE_VALUE):
        
        '''
        @param degrees:    Coordinate value in degrees or tuple in (deg/hour,min,sec)
        @param MIN_VALUE:  Minimal value of degree
        @param MAX_VALUE:  Maximal value of degree
        @param HOUR_TO_DEGREE_VALUE: Transfer constant (for hours representation)
        '''
        
        if coo_format in self.RADIANS_DESIG: degrees =degrees*180/np.pi
        elif coo_format in self.HOURS_DESIG: degrees= degrees*15
        
        self.MIN_VALUE = MIN_VALUE
        self.MAX_VALUE = MAX_VALUE
        self.HOUR_TO_DEGREE_VALUE = HOUR_TO_DEGREE_VALUE
        
        self.degrees = self._verificate_value(degrees)
    
    def __str__(self):
        if self.degrees: return "%.4f degrees" %(self.degrees)
        return ""
    
    '''
    @return: Degree value if it is valid
    '''
    def _verificate_value(self,value):
            MAX_ANGLE = 60
            
            #Case of None coordinate value
            if (value == None):
                return None
            
            elif (type(value)==int or type(value)==float):
                value = float(value)
                
            #If deg value is string, convert it into float (if it is possible)    
            elif (type(value) == str):
                try:
                    value = float(value)
                except ValueError:
                    raise ValueError("Invalid coordinate value (it is not number)",value) 
                
            #Case of tuple 
            elif(type(value)==tuple):
                #Try to convert items of tuple 
                try:
                    hours = int(value[0])
                    minutes = int(value[1])
                    seconds = float(value[2])
                except ValueError:
                    raise ValueError("Invalid coordinate value",value)
                
                #Check validity of deg/hour, min and sec
                if (np.abs(hours)>self.MAX_VALUE/float(self.HOUR_TO_DEGREE_VALUE) or np.abs(minutes)>MAX_ANGLE or np.abs(seconds) > MAX_ANGLE):
                    raise ValueError("Invalid coordinate value",value)
                
                #Case of positive value
                if (hours >= 0 and minutes >= 0 and seconds >= 0):
                    value = self.HOUR_TO_DEGREE_VALUE*(hours + minutes/60.0 + seconds/3600.0)
                
                #Case of negative value    
                else:
                    if (hours < 0 and minutes >=0 and seconds >= 0):
                        value = self.HOUR_TO_DEGREE_VALUE*(hours - minutes/60.0 - seconds/3600.0)
                    elif (hours == 0 and minutes < 0 and seconds >= 0):
                        value = self.HOUR_TO_DEGREE_VALUE*(minutes/60.0 - seconds/3600.0)
                    elif (hours ==0 and minutes == 0 and seconds <0):
                        value = self.HOUR_TO_DEGREE_VALUE*(seconds/3600.0)    
                    else:
                        raise ValueError("Invalid coordinate value",value)
                        
            else:
                raise ValueError("Invalid coordinate value",value)
    
            if (value >=self.MIN_VALUE and value <= self.MAX_VALUE):
                return value
            else:
                raise ValueError("Coordinate value %s is not in range <%i;%i> "%(value,self.MIN_VALUE,self.MAX_VALUE))
        
    
    def getDegrees(self):        
        return self.degrees
        