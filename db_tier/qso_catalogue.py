'''
Created on Mar 22, 2016

@author: Martin Vo
'''
import requests
import re
from entities.star import Star
from entities.declination import Declination
from entities.right_ascension import RightAscension
import warnings
from utils.advanced_query import updateStar
from utils.stars import plotStarsPicture
from db_tier.base_query import StarsCatalogue

class OgleQso(StarsCatalogue):
    '''
    QSO catalogue client which retrieve stars (without lcs) searched via coordinates 
    '''
    
    URL = "http://www.astrouw.edu.pl/~simkoz/MQS/"
    URL_SUFFIX = "results1qso1.php?MQS_dist=1&MQS_name=1&MQS_RA_hex=1&MQS_Dec_hex=1&MQS_V=1&MQS_I=1&MQS_z=1&MQS_ID3=1&"
    
    def __init__(self, query):
        '''
        @param query: Db query parameters
        @keyword ra: Right ascension value in degrees
        @keyword dec: Declination value in degrees
        @keyword rad: 
        
        EXAMPLE: 
        #Get all stars in catalogue
        qso_client = OgleQso({"ra":0,"dec":0,"rad":999})
        all_stars = qso_client.getStars()
        
        color_vi_index = all_stars[0].bvi["vi"]
        '''
        
        self.ra = query["ra"]
        self.dec = query["dec"]
        self.rad = float(query["rad"])
        
    def getStars(self):
        '''
        @return: List of prepared stars
        '''
        self._makeStars(self._postQuery())
        return self.stars
        
    def _postQuery(self):
        query_text = "{0}{1}ra={2}&dec={3}&rad={4}&MQS_R=1".format(self.URL,self.URL_SUFFIX,self.ra,self.dec,self.rad)
        
        raw_result = requests.post(query_text)
        return self._parseResult(raw_result.text)
        
        
    def _parseResult(self,raw_result):
        '''Return list of matched patterns (stars infos)'''
        
        star_id_pat = '<tr><td>(?P<star_id>\\d+)</td>'
        ang_dist_pat = '<td>(?P<dist>\\d+.?\\d*)</td><td>.*?' 
        star_name_pat = 'class="link">(?P<star_name>\\D+\\d+.\\d+[+,-]?\\d+.\\d+)\s*</a></td>'
        coo_pat = '<td>(?P<ra>\\d+:\\d+:\\d+.?\\d*)</td><td>(?P<dec>[+,-]?\\d+:\\d+:\\d+.?\\d*)'
        mag_pat = '</td><td>(?P<mag_v>\\d+.?\\d*)</td><td>(?P<mag_i>\\d+.?\\d*)</td><td>(?P<mag_r>\\d+.?\\d*)</td>'
        shift_pat = '<td>(?P<shift>\\d+.?\\d*)</td>'
        ogle_id_pat = "<td>(OGLE-II |)(?P<ogle_id>(\D+ \D+\d+ \d+\s*|---))</td></tr>"
        #OGLE-II LMC SC7 346891
        
        
        star_pattern = re.compile(star_id_pat+ang_dist_pat+star_name_pat+coo_pat+mag_pat+shift_pat+ogle_id_pat)
        
        expected_num = len(re.findall(star_id_pat ,raw_result))
        result = re.findall(star_pattern,raw_result)
        if len(result) != expected_num:
            warnings.warn("Not every star was parsed (%i/%i)" % (len(result),expected_num))
        
        '''i = 1
        a = 0
        while a <len(result):
            if int(result[a][0]) == i:
                a += 1
            else:
                print "not ok: ", i
            
            i += 1'''
        
        return result
    
    def _makeStars(self,stars_table):
        '''
        Make star objects from table of stars parameters
        
        Table format: ID    Distance (arcsec)    Name    RA (hhmmss)    Dec (ddmmss)    V    I    redshift    OGLE-III ID    OGLE-II ID
        '''
        
        
        
        self.stars = []
        for st in stars_table:     
            field, starid = self._parseOgleId(st[10])
            if field == None:
                    starid=st[2]
            self.stars.append(Star(field=field,starid=starid,ra=self._parseRa(st[3]),dec=self._parseDec(st[4]),mag=st[6],bvi={"V":float(st[5]),"R":float(st[6]),"I":float(st[7])}))
            
            
    def _parseDec(self,dec):
        d,m,s = dec.split(":")
        
        try:
            d = int(d)
            m = float(m)
            s = float(s)
        
        except ValueError:
            raise ValueError("Given coordinates were not parsed")
        
        
        i = 1
        if (d < 0):
            i = -1
            d = d*i
        return Declination((d+m/60.0+s/3600.0)*i)
        
    def _parseRa(self,ra):
            h,m,s = ra.split(":")
            try:
                h = int(h)
                m = float(m)
                s = float(s)
            
            except ValueError:
                raise ValueError("Given coordinates were not parsed") 

            return RightAscension((h+m/60.0+s/3600.0)*15)
        
    def _parseOgleId(self,id):
        if id == "---": return None,None
        parts = id.split(" ")
        field = parts[0] +"_"+ parts[1]
        starid = parts[2]
        return field, starid






        