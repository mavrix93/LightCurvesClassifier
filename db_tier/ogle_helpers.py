'''
Created on Aug 8, 2016

@author: Martin Vo
'''
from db_tier.stars_provider import StarsProvider
from db_tier.ogle_client import OgleII
import numpy as np
import re
from warnings import warn
from entities.exceptions import FailToParseName
from entities.right_ascension import RightAscension as Ra
from entities.declination import Declination as Dec


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
            raise     
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
    provider = StarsProvider().getProvider(field=star.field,starid=star.starid,target=target,obtain_method="ogle")
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
    res_stars = StarsProvider().getProvider(field=star.field,starid=star.starid,target=target,obtain_method="ogle").getStarsWithCurves()
    if len(res_stars) ==0:
        warn("Light curve has not been found")
        return star
    lc =res_stars[0].lightCurve
    if lc: star.putLightCurve(lc)
    return star