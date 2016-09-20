'''
Created on Jan 6, 2016

@author: Martin Vo
'''

#Throws:
from entities.exceptions import NoInternetConnection, QueryInputError, FailToParseName
import numpy as np
import re
import urllib
import urllib2
from entities.declination import Declination as Dec
from entities.right_ascension import RightAscension as Ra
from entities.star import Star
from db_tier.base_query import LightCurvesDb
from urllib2 import URLError
from utils.commons import args_type,mandatory_args,default_values
import socket
from conf.settings import *
from utils.helpers import verbose
from warnings import warn


#NOTE: This is kind of messy version of db connector. Lots of changes in order
#to get clean connector need to be done. Anyway it is working. 
class OgleII(LightCurvesDb):
    '''
    OgleII class is responsible for searching stars in OGLE db according
    to query. Then it can download light curves and saved them or retrieve
    stars object (with lc, coordinates, name...)
    '''
    
    
    ROOT = "http://ogledb.astrouw.edu.pl/~ogle/photdb"
    TARGETS = ["lmc","smc","bul","sco"]
    #QUERY_TYPE = "phot"
    QUERY_TYPE = "bvi"
    MAX_REPETITIONS = 3
    MAX_TIMEOUT = 60
    
    #Query possibilities (combination of necessary values)       
    #Check types of given parameters 
    #Set default values if they are not specified
    @mandatory_args(("ra","dec","target"),\
                    ("starcat","target"),\
                    ("field","starid","target"),\
                    ("field_num","starid","target"))
    @args_type(ra= (str,int,float,Ra),\
               dec = (str,int,float,Dec),\
               target = str,\
               delta = (int,float),\
               star_class=str,\
               starcat = str,\
               min_mag = (str,int,float),\
               max_mag = (str,int,float))
    @default_values(delta=1.0,\
                    star_class="star")
    def __init__(self,query):
        '''
        @param query:    Query is dictionary of query parameters. 
                         In case of containing "starcat" and "target"searching
                         via starcat will be executed.
                         Other case searching via coordinates will be done. Moreover
                         there is possibility to search in magnitude ranges if
                         "minMag" and "maxMag" is in dictionary
        @param "ra":     Right Ascension value in degrees
        @param "dec":    Declination value in degrees
        
        EXAMPLE:
        print OgleII({"field":"LMC_SC1","starid":"152248","target":"lmc"}).getStarsWithCurves()
        '''
        #Query parameters 
        self.tmpdir = None        
        self.stars = []
        self.field=""
        self.starid=""
        self.use_field = "off"
        self.use_starid = "off"
        self.use_ra = "off"
        self.use_decl = "off"
        self.use_imean = "off"
        self.valmin_imean = ""
        self.valmax_imean = ""
        self.valmin_ra = ""
        self.valmax_ra = "" 
        self.valmin_decl = ""
        self.valmax_decl = ""
        self.use_starcat = "off"
        self.starcat=""
        self.stars_class = query["star_class"]
        self.phot = "off"
        self.bvi = "off"
        
        self.query_err_repetitions = 0
        
        
        if (query["target"] in self.TARGETS):
            self.db_target = query["target"]
        else:
            raise QueryInputError("Unknown given target field %s" %query["target"])
        
        #In case "starat" in dict, searching thru starcat key will be done
        if ("starcat" in query):   
            self.starcat = clean_starcat(query["starcat"])
            self.use_starcat = "on"
            self.ra,self.dec = parseCooFromStarcat(self.starcat)
            
        
        elif ("starid" in query):
            self.starid=query["starid"]
            self.use_field = "on"
            self.use_starid = "on"
            
            if ("field" in query):
                self.field= query["field"]                
                
            elif ("field_num" in query):                  
                target = query["target"]
                if target == "lmc": field_pat = "LMC_SC"
                elif target == "smc": field_pat = "SMC_SC"
                elif target == "bul": field_pat = "BUL_SC"
                else: raise QueryInputError("Unresolved target")
                
                self.field= field_pat+str(query["field_num"])
         
        
        
        #In case "ra","dec","delta","target" in dict, searching thru coordinates will be done
        elif ("ra" in query and "dec" in query and "delta" in query and "target" in query ):
            ra = query["ra"]       
            dec = query["dec"]   
            #If it is not already coordination object 
            if (ra.__class__.__name__  != "RightAscension"):  
                #TODO: check the 15 multipl
                #ra = Ra(ra*15)
                ra = Ra(ra)
            if (dec.__class__.__name__  != "Declination"):                        
                dec = Dec(dec) 
            self.ra = ra
            self.dec = dec  
            self.delta = query["delta"]/3600.0   
            self.use_ra = "on"
            self.use_decl = "on"
            
            #Get range of coordinate values
            self._parse_coords_ranges()
            
            #Add magnitude ranges for searching            
            if ("min_mag" and "max_mag" in query):
                self.use_imean = "on"
                try:
                    self.valmin_imean = float(query["min_mag"])
                    self.valmax_imean = float(query["max_mag"])
                except:
                    raise QueryInputError("Magnitude values should be numbers") 
        else:
            raise QueryInputError("Query option was not resolved")

    def getStars(self):
        try:
            self._post_query()
            return self.stars
        except URLError:
            if self.query_err_repetitions < self.MAX_REPETITIONS:
                self.getStars()
            else:
                return []
            self.query_err_repetitions += 1
            
    def getStarsWithCurves(self,starClass=None): 
        '''
        This method download light curves in db. The query request need to be posted
        firstly to get temporary directory in db.
        
        @return:    List of star objects with light curves
        '''
       
        try:
            self._post_query()
        except URLError:
            raise NoInternetConnection
        
        ready_stars = self._parse_light_curves()
            
        verbose("Light curves have been saved",3,VERBOSITY)  
        return ready_stars
            
            
            
    def _post_query(self):
        '''
        This method execute query in OGLE db
        
        @return:    List of stars meeting query parameters
        '''
        #Number of pages in html file
        PAGE_LEN = 1e10 
        
        #Query parameters       
        params = {
            "db_target": self.db_target,
            "dbtyp": "dia2",
            "sort": "field",
            "use_field": self.use_field,
            "val_field": self.field,
            "use_starid": self.use_starid,
            "val_starid": self.starid,
            "disp_starcat": "on",
            "use_starcat":self.use_starcat,
            "val_starcat":self.starcat,
            "disp_ra": "on",
            "use_ra": self.use_ra,
            "valmin_ra": self.valmin_ra,
            "valmax_ra": self.valmax_ra,
            "disp_decl": "on",
            "use_decl": self.use_decl,
            "valmin_decl": self.valmin_decl,
            "valmax_decl": self.valmax_decl,
            "disp_imean": "on",
            "use_imean": self.use_imean,
            "valmin_imean": self.valmin_imean,
            "valmax_imean": self.valmax_imean,
            "disp_pgood": "off",
            "disp_imean": "on",
            "disp_imed": "off",
            "disp_bsig": "on",
            "disp_vsig": "on",
            "disp_isig": "on",
            "disp_imederr": "off",
            "disp_ndetect": "off",
            "disp_v_i":"on",
            "disp_b_v":"on",
            "sorting": "ASC",
            "pagelen": PAGE_LEN,
        }

        #Delete unneeded parameters
        for key in params.keys():
            if (params[key] == "off") or (params[key] == ""):
                params.pop(key)
        #Url for query
        url = "%s/query.php?qtype=%s&first=1" % (self.ROOT,self.QUERY_TYPE)

        #Post query
        verbose("OGLEII query is about to start",3,VERBOSITY)
        try:
            result = urllib2.urlopen(url, urllib.urlencode(params),timeout=self.MAX_TIMEOUT)
            
        #TODO: Catch timeout (repeat?)
        except socket.timeout:
            if self.query_err_repetitions < self.MAX_REPETITIONS:
                self._post_query
            else:
                raise
            
            self.query_err_repetitions +=1
           
        verbose("OGLEII query is done. Parsing result...",3,VERBOSITY)  
        self.stars = self._parse_result(result)           
        
        
    def _parse_result(self,result):
        '''Parsing result from retrieved web page'''
        #NOTE: Order of particular values is hardcoded, try more regex to 
        #get positions of values from line of column names
        
        stars = []
        values = {}
        more = {}
        #Index of line 
        idx = None
        
        #Patterns for searching star values into query result (html file)
        field_starid_pattern = re.compile("^.*jsgetobj.php\?field=(?P<field>[^&]+)\&starid=(?P<starid>\d+).*$")
        tmpdir_pattern = re.compile("<input type='hidden' name='tmpdir' value='(.*)'>")
        value_pattern = re.compile("^.*<td align='right'>(.*)</td>.*$")
        #If query post is successful         
        if (result.code == 200):            
            for line in result.readlines():
                if line.strip().startswith("<td align="):  
                    #Try to match star id (first line of star line, length is controlled by idx value)
                    field_starid = field_starid_pattern.match(line) 
                    #Load star parameters
                    if (idx is not None):
                        #If all star parameters were loaded
                        end_text = '<td align="right"><a href="bvi_query.html">New Query</a></td></tr></table>'
                        if (idx >=8 or line.strip()==end_text):
                            idx = None 
                            #Append star into the stars list and empty star list
                            values["more"] = more
                            star = Star(**values)
                            
                            og_ident = self.getIdentName(star)
                            star.ident["ogle"]["name"] = og_ident
                            
                            stars.append(star)            
                            values = {}
                            more = {}
                            
                        else:
                            idx += 1
                            value = value_pattern.match(line).group(1)
                            
                            try:
                                value = float(value)
                            except:
                                idx += 1
                                
                            
                            #Ra
                            if (idx == 1):
                                values["ra"] = value*15
                            #Decl
                            elif (idx == 2):
                                values["dec"] = value                 
                            #V-I
                            elif (idx == 3):
                                more["v_i"] = value
                            #I
                            elif (idx==4):
                                more["i_mag"] = value
                                values["more"] = more
                            #Vsig
                            elif (idx==5):
                                more["v_sig"] = value
                            
                            #Isig
                            elif (idx==6):
                                more["i_sig"] = value
                            #B-V
                            elif (idx==7):
                                more["b_v"] = value
                            
                            #Bsig
                            elif (idx==8):
                                more["b_sig"] = value
                    
                    #If first line of star info
                    if (field_starid):
                        ident = {}
                        idx = 0
                        og = {}
                        og["field"] =field_starid.group("field")
                        og["starid"] =field_starid.group("starid")
                        og["target"] = self.db_target
                        ident["ogle"] = og
                        values["ident"] = ident
                    #Try to match tmpdir (once in result) where query data is saved    
                    tmpdir = tmpdir_pattern.match(line)
                    if (tmpdir):
                        self.tmpdir = tmpdir.group(1)
      
        verbose("OGLE II query is done. Amount of the stars meeting the parameters: %i" %len(stars),3,VERBOSITY)
        return stars
        
        
        
  
    def _parse_light_curves(self):
        '''This help method makes query in order to get page with light curve and download them''' 
           
        ready_stars = [] 
        numStars = len(self.stars)
        i = 0
        for star in self.stars: 
            verbose("Parsing query result "+ str(i) +"/"+str(numStars),3,VERBOSITY)
            
        
            #Make post request in order to obtain light curves
            self._make_tmpdir(star.ident["ogle"]["field"].lower(), star.ident["ogle"]["starid"])
         
            #Specific url path to lc into server
            url = "%s/data/%s/%s_i_%s.dat" % (self.ROOT, self.tmpdir, star.ident["ogle"]["field"].lower(), star.ident["ogle"]["starid"])
                        
            #Parse result and download  (if post is successful)
            result = urllib2.urlopen(url)
            if (result.code == 200):
                star_curve = []
                for line in result.readlines(): 
                    parts = line.strip().split(" ")
                    star_curve.append([float(parts[0]),float(parts[1]),float(parts[2])])
                if (star_curve and len(star_curve) != 0): 
                    star.putLightCurve(np.array(star_curve))
                    star.starClass = self.stars_class
            ready_stars.append(star)
            i += 1        
        return ready_stars
    

    
    
    def _make_tmpdir(self,field,starid):
        '''Make post request to get temp directory in db for obtaining light curves'''
        
        params = {
          "field": field,
          "starid": starid,
          "tmpdir": self.tmpdir,
          "db": "DIA",
          "points": "good",
        }

        url = "%s/getobj.php" % self.ROOT
        result = urllib2.urlopen(url, urllib.urlencode(params))
        if (result.code != 200):
            raise Exception("%s %s" % (result.code, result.msg))


    def _parse_coords_ranges(self):
        '''Get coordinates in right format and get coordinates ranges'''
        ra = self.ra.getHours()
        dec = self.dec.getDegrees()
        self.valmin_ra = ra -self.delta/15.0
        self.valmax_ra = ra +self.delta /15.0
        self.valmin_decl = dec -self.delta
        self.valmax_decl = dec +self.delta

            
    @staticmethod
    def getIdentName(star):
        try:
            ident = star.ident["ogle"]
        except KeyError:
            warn("The star does not have OGLE identificator from which name could be made")
            return None
        if ident["field"].find("_") != -1:
            return "%s_%s" %(ident["field"],ident["starid"])
        
        return "%s_SC%s_%s" %(ident["target"].upper(),ident["field"],ident["starid"])
    
    
    
    
def testCandidates(mag,std,target,f1,s1,f2,s2):
    p1 = {
        "field": f1,
        "starid": s1,
        "target": target
         }
    
    p2 = {
        "field": f2,
        "starid": s2,
        "target": target
         }
    
    try:          
        st1 = OgleII(p1).getStarsWithCurves()[0]
    except IndexError:
        return f2, s2
    try:
        st2 = OgleII(p2).getStarsWithCurves()[0]
    except IndexError:
        return f1, s1
    
    diff_mag1 = abs(np.mean(st1.lightCurve.mag)-mag)/mag
    diff_mag2 = abs(np.mean(st2.lightCurve.mag)-mag)/mag
    diff_std1 = abs(np.std(st1.lightCurve.mag)-std)/std
    diff_std2 = abs(np.std(st2.lightCurve.mag)-std)/std
    
    diff_1 = (diff_mag1**2 + diff_std1**2)**0.5
    diff_2 = (diff_mag2**2 + diff_std2**2)**0.5
    
    if (diff_1 != 0 or diff_2 != 0):
        warn("Any of two candidates have no exactly the same light curve")
    
    if diff_1 < diff_2:
        return f1, s1
    return  f2, s2

def parseCooFromStarcat(coo):
    '''
    This  method parse coordinate objects from starcat identifier
    
    @param coo --> str: Ogle starcat
    EXAMPLE: OGLE053234.08-695949.7
    
    @return --> tuple: Right ascension and declination object
    '''   
    
    ra_pat= "(?P<ra_h>\d\d)(?P<ra_m>\d\d)(?P<ra_s>\d\d\.{0,1}\d\d)"
    dec_pat = "(?P<dec_d>[+-]\d\d)(?P<dec_m>\d\d)(?P<dec_s>\d\d\.{0,1}\d+)"
    ra_dec_pat = re.compile("%s%s" % (ra_pat, dec_pat))
    ra_dec = ra_dec_pat.match(coo)
    try:
        ra_s = ra_dec.group("ra_s")
        dec_s = ra_dec.group("dec_s")
        dec_d = ra_dec.group("dec_d")
        if ("+"in dec_d):
            dec_d = dec_d.replace("+","")
        if (len(ra_s) >2 and "." not in ra_s):
            ra_s = ra_s[:2]+"."+ra_s[2:]    
        if (len(dec_s) >2 and "." not in dec_s):
            dec_s = dec_s[:2]+"."+dec_s[2:]
        ra =(int(ra_dec.group("ra_h"))+int(ra_dec.group("ra_m"))/60.0 + float(ra_s)/3600.0)*15
        dec =(int(dec_d),int(ra_dec.group("dec_m")),float(dec_s))
    except AttributeError:
        warn("Could not parse %s into coordinates" % coo)
        ra ,dec = None, None
    return Ra(ra), Dec(dec)


  



def parseIdent(db_ident, lc = None):
    '''
    Method for parsing star name in field_starid format. In case of underscore
    symbol between field and starid file name can be easily parsed. If there
    are not underscore (example II) there are generaly two possibilities.
    This will be resolved by obtaining light curve of the file and these
    two candidates form OgleII db.
    
    @param file_path --> str: Path with OgleII identificator of file
    EXAMPLE: path/LMC_SC10173573.dat or path/LMC_SC10_173573.dat
    
    @return --> tuple: Field and starid
    EXAMPLE: (LMC_SC10,173573)
    '''  
    
    underscores_num = db_ident.count("_")
    
    #Case of for example LMC_SC10173573
    if underscores_num == 1:    
        try:         
            if lc == None:
                raise FailToParseName("For resolving this identificator the light curve needs to be specified")   
            number = re.findall("\d+", db_ident)[0]
            field_str = re.findall("\D+_\D+", db_ident)[0]
            
            target = re.findall("\D+_",field_str)[0][:-1].lower()
            field1 = field_str+str(number[0])
            field2 = field_str+str(number[:2])

            mag = np.mean(lc.mag)
            std = np.std(lc.mag)

            field,starid = testCandidates(mag,std,target,field1,number[1:],field2, number[2:])
            
            return field, starid
            
        except:       
            raise FailToParseName("Star identifier has not been resolved")
    else:
        pat = re.compile("(?P<field>\D+_SC\d+)_(?P<starid>\d+)")
        
        try:
            m = pat.match(db_ident)
            return m.group(1),m.group(2)
        except AttributeError:
            raise FailToParseName("Star identifier has not been resolved")

    
    
def clean_starcat(starcat):
    ''' 
    This method add dots to starcat identifier in order to be resolved by ogle query
    
    @param starcat --> str: Starcat identifier
    @return --> str: Starcat identifier
    '''  
    if not ("." in starcat):
        if "OGLE" in starcat:
            starcat = starcat[4:]
                   
        half_index = starcat.find("-")
        if (half_index == -1):
            half_index = starcat.find("+")
        starcat= starcat[:half_index-2]+"."+starcat[half_index-2:-1]+"."+starcat[-1:]    
    return starcat
            
        


def updateStar(star):
    '''
    This method download coordinates and light curve of given star (in Ogle db) 
    via its field and star id name
    
    @param star: Star object which contains field and star id
    @return: Star object appended by coordinates and light curve
    '''
    target = "lmc"
    try:
        if (star.field[:3] == "SMC"):
            target = "smc"
    except TypeError:
        pass
    
    star = _updateInfo(star,target)
    if not star.lightCurve: star = _updateLc(star,target)
    
    return star
    
def _updateInfo(star,target):
    query = {
        "field": star.ident["ogle"]["field"],
        "starid": star.ident["ogle"]["starid"],
        "target": star.ident["ogle"]["target"]
         }
    provider = OgleII(query)
    provider._post_query()
    stars = provider.stars
    
    if len(stars) >0:
        st =  stars[0]
        star.ra = st.ra
        star.dec = st.dec
        try:
            star.more["bvi"] = st.more["bvi"]
        except KeyError:
            warn("Bvi cannot be obtained")
    return star

def _updateLc(star,target):
    query = {
        "field": star.ident["ogle"]["field"],
        "starid": star.ident["ogle"]["starid"],
        "target": star.ident["ogle"]["target"]
         }
    res_stars = OgleII(query).getStarsWithCurves()
    if len(res_stars) ==0:
        warn("Light curve has not been found")
        return star
    lc =res_stars[0].lightCurve
    if lc: star.putLightCurve(lc)
    return star

    
    
