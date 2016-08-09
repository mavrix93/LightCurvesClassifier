'''
Created on Apr 12, 2016

@author: martin
'''
import unittest
from stars_processing.filters_impl.compare import ComparingFilter
from stars_processing.filters_impl.word_filters import HistShapeFilter,\
    VariogramShapeFilter, CurvesShapeFilter
from db_tier.stars_provider import StarsProvider
import numpy as np
from entities.star import Star
from stars_processing.filtering_manager import FilteringManager
from utils.stars import plotStarsPicture, resultEvalaution

class Test(unittest.TestCase):


    def testName(self):
        
        def dec_fun(score_list):
            x = score_list[0]
            y = score_list[1]
            y0 = 0.00415765437185*x**3 -0.143070417878*x**2 - 0.149999181513*x+ 9.68453097125
            return y<y0
        
        path1 = "../../data/light_curves/quasars"
        path2 = "../../data/light_curves/some_stars"
        
        stars = StarsProvider().getProvider(path=path2,obtain_method="file",star_class="star").getStarsWithCurves()[:20]
        quasars = StarsProvider().getProvider(path=path1,obtain_method="file",star_class="qso").getStarsWithCurves()[:20]
        
        vario_alphabet_size=17
        hist_days_per_bin=97
        hist_alphabet_size=7
        treshold= dec_fun
        vario_days_per_bin =9
        
        
        filteringManager = FilteringManager(quasars[:10]+stars)
        cf = []
        cf.append(HistShapeFilter(hist_days_per_bin,hist_alphabet_size))    
        cf.append(VariogramShapeFilter(vario_days_per_bin, vario_alphabet_size)) 
        #cf.append(CurvesShapeFilter(days_per_bin, alphabet_size))
        comp_filt = ComparingFilter(cf, quasars[10:], treshold, search_opt="closest",filt_opt="together")
        filteringManager.loadFilter(comp_filt)
        
        
        res_stars = filteringManager.performFiltering()
        
        for st in res_stars:
            print st.scoreList

        
                
    """def test_filtering(self):
        x = np.linspace(0, 2*np.pi,100)
        y = np.sin(x)
        
        word_size = 40
        alphabet_size = 15
        treshold = 222
        days_per_bin = 0.6
        
        star1= Star()
        star1.putLightCurve([x,y])
        
        
        y2 = np.cos(x-np.pi*0.2)
        y3 = np.exp(x)
        
        star2 = Star()
        star2.putLightCurve([x,y3])
        
        filt_star = Star()
        filt_star.putLightCurve([x,y2])
        
        filteringManager = FilteringManager([star1,star2])
        cf = []
        cf.append(HistShapeFilter(word_size=word_size,alphabet_size=alphabet_size))    
        cf.append(VariogramShapeFilter(days_per_bin, alphabet_size)) 
        cf.append(CurvesShapeFilter(days_per_bin, alphabet_size))
        comp_filt = ComparingFilter(cf, [filt_star], treshold, search_opt="passing")
        filteringManager.loadFilter(comp_filt)
       
        stars = filteringManager.performFiltering()
        print stars[0].scoreList,stars[1].scoreList
        #plotStarsPicture(stars,bins=word_size,)
"""
