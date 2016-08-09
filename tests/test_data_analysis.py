'''
Created on Mar 9, 2016

@author: Martin Vo
'''
import unittest
import numpy as np
from utils.data_analysis import to_ekvi_PAA,normalize, variogram, abbe
import random
from entities.star import Star
from utils.stars import plotStarsPicture
from stars_processing.filtering_manager import FilteringManager
from stars_processing.filters_impl.word_filters import HistShapeFilter,\
    VariogramShapeFilter
from stars_processing.filters_impl.compare import ComparingFilter

class Test(unittest.TestCase):
    def test_abbe(self):
        '''This test check propriety of  Abbe values of various functions'''
        
        a = []
        for i in range(100):
            a.append(random.randint(10,20))        
        
        linear_grow = np.linspace(0, 23, 150)
        exponencial = np.exp(linear_grow)
        sin = np.sin(linear_grow)
        const = np.array(a)
        
        #print abbe(linear_grow),abbe(exponencial),abbe(sin),abbe(const)
        self.failUnless(abbe(linear_grow)<abbe(exponencial)<abbe(sin)<abbe(const))
        
    def test_data_anal_fails(self):
        '''This tests just check  own fails'''
        x = np.linspace(0,2*np.pi,100)
        y = np.sin(x)
        
        self.failUnlessRaises(variogram(x, y))
        self.failUnlessRaises(normalize(x))

    

    def test_ekvidist_PAA(self):
        '''Testing propriety of converting time line in ekvidistant time series'''
        x = [1,1.1,1.2,1.3,1.4,1.5,2,3,4,5]
        y = [99,99,99,99,99,99,99,0,10,20]
        self.failUnless(to_ekvi_PAA(x, y, 5)[1].tolist() == [99.,0.,10.,20.,])
        
    def test_histogram(self):
             
        a = []
        for i in range(100):
            a.append(random.randint(-1,1)/10.0)        
        
        x = np.linspace(0, 23, 100)
        exponencial = np.exp(x)+a
        sin = np.sin(x/4.0)+a
        const = np.array(a)
        
        st1 = Star("sin")
        st1.putLightCurve([x,sin])
        st2 = Star("lin1")
        st2.putLightCurve([x,0.2*x+a])
        st3 = Star("lin2")
        st3.putLightCurve([x,3*x+a])
        st4 = Star("lin3")
        st4.putLightCurve([x,2*x+a])
        
        word_size = 10
        alphabet_size = 15
        treshold = 99
        days_per_bin = 1
        
        
        filteringManager = FilteringManager([st1,st3,st4])
        cf = []
        cf.append(HistShapeFilter(word_size=word_size,alphabet_size=alphabet_size))    
        cf.append(VariogramShapeFilter(days_per_bin, alphabet_size)) 
        #cf.append(CurvesShapeFilter(days_per_bin, alphabet_size))
        comp_filt = ComparingFilter(cf, [st2], treshold, search_opt="onebyone")
        filteringManager.loadFilter(comp_filt)
        res_stars = filteringManager.performFiltering()
        
        for st in res_stars:
            print st.scoreList, st.matchScore
            print st.histWord
        
        #plotStarsPicture(res_stars, word_size)
        

  

        
    

        