'''
Created on Jan 9, 2016

@author: Martin Vo
'''
from entities.right_ascension import RightAscension as Ra
from entities.declination import Declination as Dec
from entities.light_curve import LightCurve
from warnings import warn
import numpy as np
from utils.data_analysis import  to_ekvi_PAA,abbe, histogram, variogram,\
    compute_bins, cart_distance
from utils.helpers import check_path
from entities.exceptions import FailToParseName


#TODO: Get rid of sax attributes and put sax words, scores and matches into more dict  

class Star(object):
    '''
    Star is base object in astronomy. This class is responsible for keeping 
    basic informations about stellar objects. It's possible to create empty star
    and add parameters additionally
    '''    
    
    EPS = 0.000138              #Max distance in degrees to consider two stars the equal
    DEF_DAYS_PER_BIN = 25       #Default value for histogram and variogram transformation
    DEF_SMOOTH_RATIO = 0.5      #Default smooth ratio for abbe transformation
    
               
    def __init__(self, ident = {},ra=None,dec=None,more = {}):
        '''
        @param ident: Dictionary of identificators for the star 
        @param ra:        Right Ascension of star (value or RA object)
        @param dec:       Declination of star (value or DEC object)
        @param star_info: Another informations about the star in dictionary

        EXAMPLE:
        Identificator for OGLE db would be:
            ident = {"ogle":{"field":1,"starid":1,"target":"lmc"},...}
        '''
        
        if (ra.__class__.__name__  != "RightAscension"  ):
            ra = Ra(ra)
        if (dec.__class__.__name__  != "Declination" ):                        
            dec = Dec(dec) 
        self.ident = ident
        self.ra = ra
        self.dec = dec 
        self.more = more
        
        self.lightCurve = None
        self.curveWord = ""
        self.histWord = ""
        self.varioWord = ""
        self.matchStar = None
        self.matchScore = None
        self.starClass = None
        self.scoreList = []
        
        self.name = self.getIdentName()
        
        
    def __len__(self):
        return 1
    
    def __eq__(self, other):
        if not (isinstance(other, Star)):
            return False
        if (other == None):
            return False
        elif self.ident:
            for db_key in self.ident.keys():
                if db_key in other.ident:
                    if self.ident[db_key] == other.ident[db_key]:
                        return True
        return self.getInRange(other, self.EPS)        
    
    def __str__(self):  
        star_text = ""
        for db_key in self.ident:
            star_text += "%s identifier:\t" % db_key
            for key in self.ident[db_key]:
                star_text += "%s: %s\t" % (key, self.ident[db_key][key])
            star_text += "\n" 
                 
        if self.ra and self.dec: star_text += "\tCoordinates: %s %s" % (self.ra,self.dec)
        return star_text
    

    def getInRange(self,other,eps):
        '''
        This method decides whether other star is in eps range of this star
        according to coordinates
        
        @param other-->Star object: Star to compare with
        @param eps-->float: Range in degrees
        @return-->bool: Is in range? 
        '''     
        
        if (self.ra == None or self.dec == None):
            warn("Star {0} has no coordinates".format(self.field+self.starid))
            
        dist = self.getDistance(other)
                
        if (dist < eps):return True
        return False     
        
    def getDistance(self,other):
        '''
        Compute distance between this and other star in degrees
        
        @param other: Another star object to compare with        
        @return: Distance of stars in degrees
        '''
        x = self.ra.degrees - other.ra.degrees
        y = self.dec.degrees-  other.dec.degrees 
        
        return cart_distance(x,y)
    
    
    def getHistogram(self,days_per_bin=None,centred=True,normed=True):
        '''
        @param bins_num: Number of values in histogram
        @param centred: If True values will be shifted (mean value into the zero)
        @param normed: If True values will be normed (according to standart deviation)        
        @return: Tuple of counts and bins (ranges) or None if there are no light curve
        '''
        if not self.lightCurve:
            warn("Star {0} has no light curve".format(self.ident))
            return None
        if days_per_bin==None:
            warn("Days per bin ratio was not specified. Setting default value: %i" % self.DEF_DAYS_PER_BIN)
            bins = self.DEF_DAYS_PER_BIN
        else:
            bins = compute_bins(self.lightCurve.time,days_per_bin)
        
        return histogram(self.lightCurve.time,self.lightCurve.mag,bins,centred,normed)
        
        
    def getVariogram(self,days_per_bin = None,log_opt=True):
        '''
        Variogram is function which shows variability of time series in different lags
        
        @return: Tuple of two numpy arrays - time lags and magnitude slope for the certain lag 
        '''
        
        if (self.lightCurve == None):
            warn("Star {0} has no light curve".format(self.ident))
            return None
        if days_per_bin==None:
            warn("Days per bin ratio was not specified. Setting default value: %i" % self.DEF_DAYS_PER_BIN)
            bins = self.DEF_DAYS_PER_BIN
        else:
            bins = compute_bins(self.lightCurve.time,days_per_bin)
        
        return variogram(self.lightCurve.time,self.lightCurve.mag,bins=bins,log_opt=True)
        
    def getAbbe(self, smooth_ratio = None, normalize_abbe=True):
        '''
        Compute Abbe value of light curve
        
        @param bins: Number of items of light curve which will be taken to computing
        @param normalize_abbe: Normalizing time series
        @return: Abbe value of star (light curve)
        '''
        if (self.lightCurve == None):
            warn("Star {0} has no light curve".format(self.field+self.starid))
            return None
        if (smooth_ratio == None):
            warn("Smooth ratio was not specified. Setting default value: %f" % self.DEF_SMOOTH_RATIO)
            smooth_ratio = self.DEF_SMOOTH_RATIO
 
        x = to_ekvi_PAA(self.lightCurve.time, self.lightCurve.mag)[1]
        return abbe(x,smooth_ratio)
    
 
                
    def saveStar(self,path=".", ident_convention = None):
        '''
        Save star's light curve into file and name (field+starid) as a name of the file
        
        @param path: Path to the folder where light curves will be saved (from 
        '''
        if path == "":
            path = "."
            
        if ident_convention != None:
            try:
                id_name = self.ident[ident_convention]["name"]
            except:
                FailToParseName("The star does not contain desired indentificator %s, but %s"%(ident_convention,self.ident))
        else:
            try:
                id_name = self.ident[self.ident.keys()[0]]
            except:
                FailToParseName("The star does not contain any identificator")
                
        if self.lightCurve != None:
            fi_path = "%s/%s.dat" %(path,id_name)
            np.savetxt(check_path(fi_path), np.c_[self.lightCurve.time,self.lightCurve.mag,self.lightCurve.err])
        else:
            warn("Star {0} has no light curve".format(self.ident))
    
    def getIdentName(self, db_key = None):
        if db_key == None:
            if len(self.ident.keys()) == 0:
                return "Unknown"
            db_key = self.ident.keys()[0] 
        
        if "name" in self.ident[db_key]:
            return self.ident[db_key]["name"]
        star_name = db_key
        for key in self.ident[db_key]:
            star_name += "_%s_%s" % (key, self.ident[db_key][key])
        return star_name
    
    #TODO: Decide resolver according to db (issue with loop imports)
    def resolveIdent(self, db):
        self.ident[db]["name"]
    
    
    def putLightCurve(self,lc):
        '''Add light curve to the star'''
        
        #It's possible to give non light curve object and create it additionally
        if (lc.__class__.__name__  != "LightCurve" and lc != None):  
            lc = LightCurve(lc)
        self.lightCurve = lc
        
    def putLettersCurve(self,lc):
        '''Put string curve (word) to the star''' 
        self.curveWord = lc    
        
    def putLettersHist(self,hist):
        self.histWord = hist
        
    def putLettersVario(self,vario):
        self.varioWord = vario
        
    def putMatchStar(self,star):
        '''Put match star'''
        self.matchStar=star
        
    def putScore(self,score):
        '''Put score of match'''
        self.matchScore = score
        
    def putIntoScoreList(self,score):
        self.scoreList.append(score)
    
  
    

        
        