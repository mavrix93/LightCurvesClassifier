'''
Created on Jan 9, 2016

@author: Martin Vo
'''

from __future__ import division

from entities.right_ascension import RightAscension as Ra
from entities.declination import Declination as Dec
from entities.light_curve import LightCurve
from warnings import warn
import numpy as np
from utils.data_analysis import  to_ekvi_PAA,abbe, histogram, variogram,\
    compute_bins, cart_distance
from entities.exceptions import FailToParseName
import os


# TODO: Get rid of sax attributes and put sax words, scores and matches into more dict  
# TODO: Think more about getting rid of methods for computing things such
# as histrogram, variogram etc. --> put them inot data_analysis module

class Star(object):
    '''
    Star is base object in astronomy. This class is responsible for keeping 
    basic informations about stellar objects. It's possible to create empty star
    and add parameters additionally
    '''    
    
    EPS = 0.000138              # Max distance in degrees to consider two stars equal
    
               
    def __init__(self, ident = {}, name = None, ra = None, dec = None, more = {}, starClass = None):
        '''
        Parameters:
        -----------
            ident : dict
                Dictionary of identifiers of the star. Each key of the dict 
                is name of a database and its value is another dict of database
                identifiers for the star (e.g. 'name') which can be used
                as an unique identifier for querying the star. For example:
                
                    ident = {"OgleII" : {"name" : "LMC_SC1_1","db_ident" : {"field_num" : 1, "starid" : 1,"target" : "lmc"},...}
                
                CONVENTION:
                -----------
                    Please keep convention as is shown above. Star is able to be
                    queried again automatically if ident key is name of database
                    connector and it contains dictionary called "db_ident".
                    This dictionary contains unique query for the star in the database. 
                
                
            name : str
                Optional name of the star across the all databases
                
            ra : str, int, float, RightAscension
                Right Ascension of star (value or RA object) in degrees
                
            dec : str, float, Declination
                Declination of star (value or DEC object) in degrees
                
            more : dict
                Additional informations about the star in dictionary. This attribute
                can be considered as a container. These parameters can be then used
                for filtering. For example it can contains color indexes:
                    
                    more = { "b_mag" : 17.56, "v_mag" : 16.23 }
                    
            star_class : str
                Name of category of the star e.g. 'cepheid', 'RR Lyrae', 'quasar'
         
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
        self.starClass = starClass
        self.scoreList = []
        
        if not name:
            self.name = self.getIdentName()
        else:
            self.name = name
        
        
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
    
    
    def getHistogram(self, days_per_bin = None, bins = None, centred=True, normed=True):
        '''
        @param bins_num: Number of values in histogram
        @param centred: If True values will be shifted (mean value into the zero)
        @param normed: If True values will be normed (according to standart deviation)        
        @return: Tuple of counts and bins (ranges) or None if there are no light curve
        '''
        if not self.lightCurve:
            warn("Star {0} has no light curve".format(self.ident))
            return None
        if not bins:
            if days_per_bin == None:
                bins = None
            else:
                bins = compute_bins(self.lightCurve.time,days_per_bin)
        
        return histogram(self.lightCurve.time,self.lightCurve.mag,bins,centred,normed)
        
        
    def getVariogram(self, days_per_bin = None, bins = 12, log_opt=True):
        '''
        Variogram is function which shows variability of time series in different lags
        
        @return: Tuple of two numpy arrays - time lags and magnitude slope for the certain lag 
        '''
        
        if (self.lightCurve == None):
            warn("Star {0} has no light curve".format(self.ident))
            return None
        if days_per_bin:
            bins = compute_bins(self.lightCurve.time,days_per_bin)
        
        return variogram(self.lightCurve.time,self.lightCurve.mag,bins=bins,log_opt=True)
        
    def getAbbe(self, bins = None):
        '''
        Compute Abbe value of the light curve
        
        @param bins_ratio: Percentage number of bins from original dimension
        @return: Abbe value of star (light curve)
        '''
        if (self.lightCurve == None):
            warn("Star {0} has no light curve".format( self.name ))
            return None
        if not bins:
            bins = len(self.lightCurve.time)
        
        x = to_ekvi_PAA(self.lightCurve.time, self.lightCurve.mag, bins)[1]
        return abbe(x, len(self.lightCurve.time))

                
    def saveStar(self, path=".", ident_convention = None):
        '''
        Save star's light curve into the file
        
        @param path: Path to the folder where light curves will be saved (from 
        '''
        if path == "":
            path = "."
            
        if ident_convention != None:
            try:
                id_name = self.ident[ident_convention]["name"]
            except:
                raise FailToParseName("The star does not contain desired indentifier %s, but %s"%(ident_convention,self.ident))
        else:
            anything = False
            for k in self.ident.keys():
                try:
                    id_name = self.ident[ k ]["name"]
                    anything = True
                    break
                except:
                    pass
            if not anything:
                raise FailToParseName("The star does not contain any identifier")
                
        if self.lightCurve != None:
            fi_path = os.path.join( path, "%s.dat" % id_name )
            np.savetxt( fi_path, np.c_[self.lightCurve.time,self.lightCurve.mag,self.lightCurve.err], fmt='%.3f')
        else:
            warn("Star {0} has no light curve".format(self.ident))
            return None
            
        return fi_path
    
    def getIdentName(self, db_key = None):
        """
        Parameters:
        -----------
            db_key : str
                Database key
                
        Returns:
        --------
            Name of the star in given database. If it is not specified,
            the first database will be taken to construct the name
        """
        
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
  
    
    def putLightCurve(self, lc, meta = {}) :
        '''Add light curve to the star'''
        
        # It's possible to give non light curve object and create it additionally
        if not isinstance(lc, LightCurve) and lc != None: 
            lc = LightCurve(lc, meta = meta)
        
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
        
        
    def getName(self):
        if self.ident.keys():
            for key in self.ident.keys():
                
                name = self.ident[ key ].get("name", None)
                if name:
                    return name
                
            for key in self.ident.keys():
                ident = self.ident[ key ].get("identifier", None)
                
                if ident:
                    return ident
        return "Unresolved"
    
  
    

        
        