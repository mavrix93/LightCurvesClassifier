'''
Created on Jul 22, 2016

@author: Martin Vo
'''
from sklearn.base import BaseEstimator, ClassifierMixin
from stars_processing.filtering_manager import FilteringManager
from utils.stars import count_types
from entities.exceptions import StarAttributeNotSpecified
from sklearn.grid_search import GridSearchCV
from utils.helpers import verbose, progressbar
from conf.settings import VERBOSITY
from utils.output_process_modules import saveIntoFile
from conf import settings
import os
from stars_processing.filters_impl.compare import ComparingFilter
import random
import numpy as np
from stars_processing.systematic_search.status_resolver import StatusResolver
import collections
import json


class DefaultEstimator(BaseEstimator, ClassifierMixin):
    '''
    This is default estimator which can be used for calculating parameters
    of star filters. Input params of methods of the class is ruled
    by GridSearch and ParamsEstimation (see below).
    Scoring function is defined by the result of filtering via given combinations
    of parameters. Evaluation of certain combination of params is given by "score_calc" as 
    function of true positive (tp) and false positive (fp) values. This method can be changed,
    by default it return difference of tp_rate and fp_rate.
    
    Note:
    -----
        Every estimator has to inherit BaseEstimator, ClassifierMixin and has
        "fit" and "score" function
    
    Attributes:
    -----------
        tuned_params : dict
            Tuned parameters of the inspected filter
        
    '''
     
    def __init__(self,tuned_params = {} ):
        self.tuned_params = tuned_params
      
    def fit(self, all_stars,y,filt): 
        '''Learn to recognize stars
        
        Parameters:
        -----------
            all_stars : list
                Star objects
            
            y : list
                List of zeroes and ones, which say whether object in all_stars
                list is searched object (1) or not (0).
            
            filt : Filter object
                Investigated filter object
                
        Throws:
        -------
            StarAttributeNotSpecified
                The searched type is recognized according to starClass attribute
                of Star objects. The method throws the exception if it is not specified.
        '''
         
        self.searched= []
        self.others = []
        self.filt = filt
        
        for i in range(len(all_stars)):
            if y[i] == 1:
                self.searched.append(all_stars[i])
            else:
                self.others.append(all_stars[i]) 
        try:  
            self.searched_type = self.searched[0].starClass
        except AttributeError as err:
            raise StarAttributeNotSpecified(err)
        
    def score(self,all_stars,y=None):
        '''Use examined parameters to calculate precision of the combination'''
        
        filt = FilteringManager(all_stars)
        
        try:
            filt.loadFilter(self.filt(**self.tuned_params))
        except TypeError:
            raise Exception("Mandatory arguments for given filter is missing.")
       
                    
        stars = filt.performFiltering()
        
        all_num = len(all_stars)
        filt_counts = count_types(stars)
        
        try:
            tp = filt_counts[self.searched_type]
        except KeyError:
            tp = 0
            
        fp = len(stars) - tp
        
        return self.score_calc(tp,fp,all_num)
    
    def score_calc(self, tp, fp, all_num):
        '''Calculate score as difference of tp ratio and fp ratio'''
        
        return tp/float(all_num) - fp/float(all_num)


class ComparativeEstimation(object):
    
    DEFAULT_FILTER_NAME = "ComparativeFilter"
    
    def __init__(self, searched, others ,compar_filters, tuned_params, decider,
                 save_file = DEFAULT_FILTER_NAME + "." + settings.OBJECT_SUFFIX, log_path = "." ):
        
        if not searched or not others:
            raise Exception("Empty searched or other light curves sample")
        
        # TODO: Custom split ratio
        random.shuffle( searched )
        self.searched, self.compar_stars = searched[ : len(searched)/2 ], searched[len(searched)/2 : ]
        self.others = others
        self.tuned_params = tuned_params
        self.decider = decider
        self.compar_filters = compar_filters
        
        if not os.path.isdir( log_path ):
            raise Exception("There is no folder %s" % log_path)
        
        self.save_file = save_file
        self.log_path = log_path
            
    def fit( self ):
        precisions = []
        filters = []
        stats = []
        i = 0
        for tun_param in progressbar(self.tuned_params, "Estimating combinations: "):
            i+=1
            filt = ComparingFilter(compar_filters = self.compar_filters,
                                compar_stars = self.compar_stars,
                                decider = self.decider(),
                                filters_params = tun_param,
                                plot_save_path = os.path.join( self.log_path, self.DEFAULT_FILTER_NAME +"_"+str(i)+".png" ))
            filt.learn(self.searched, self.others)
            
            st = filt.getStatistic( self.searched, self.others )    
            precisions.append( st["precision"] )
            filters.append( filt )
            stats.append( st )
            
            z = collections.OrderedDict(tun_param).copy()
            z.update( collections.OrderedDict(st) )
            StatusResolver.save_query([z], FI_NAME = self.DEFAULT_FILTER_NAME+"_log.dat", PATH = self.log_path, DELIM = settings.FILE_DELIM )
            
        
        best_id = np.argmax( precisions )
        
        print "*"*30
        print "Best params:\n%s\n" % json.dumps( self.tuned_params[best_id] , indent=4)
        print "Statistic:\n%s\n" % json.dumps( stats[ best_id ] , indent=4)
        
        saveIntoFile( filters[best_id] , path = settings.FILTERS_PATH, fileName = self.save_file)

class ParamsEstimation(object):
    '''
    This class is responsible for calculating best params of star filters 
    according to train classified stars.  
    '''
    
    DEFAULT_FILTER_NAME = "tuned_filter"

    def __init__(self, searched,others,filt,
                 tuned_params, estimator = None,
                 save_file = DEFAULT_FILTER_NAME + "." + settings.OBJECT_SUFFIX, comp_info = {} ):
        '''
        @param searched: List of star-like objects containing light curves and "starClass" attribute
        @param others: List of another stars
        @param filt: Star filter type object
        @param tuned_params: List of combinations of parameters which will be tried
        @param estimator: Estimator object   
        
        EXAMPLE:
        --------
            es = ParamsEstimation(quasars,stars,AbbeValueFilter, [{"abbe_lim": 0.37},{"abbe_lim": 0.4}])
            es.fit() 
        '''
        
        self.searched = searched
        self.others = others
        self.filt = filt
        #self.tuned_params = self._calcCombinations(tuned_params)
        self.tuned_params = { "tuned_params" : tuned_params }
        
        if estimator:
            self.estimator = estimator
        else:
            self.estimator = DefaultEstimator( tuned_params,  comp_info)
        
        self.save_file_name = save_file
        
        self.comp_info  = comp_info

        
    def fit(self):
        ''' Make a fit according to given stars and find best parameters '''
        
        gs = GridSearchCV(self.estimator, self.tuned_params,fit_params = {"filt":self.filt})
        gs.fit(self.searched + self.others,y=[1 for i in range(len(self.searched))]+[0 for i in range(len(self.others))])
        best_params =  gs.best_params_['tuned_params']
        
        print "best params", best_params
        #result_dict = unpack_objects(best_params["tuned_params"])
        verbose("Score: "+ str(gs.best_score_), 0, VERBOSITY)
        self._saveResultParams(best_params)
        verbose("Result file was saved into the file", 1, VERBOSITY)
        
    def _saveResultParams(self,best_params):
        '''
        Save results into the file
        
        Result will be saved as pickle object - dictionary with two keys:
            "filter": Filter class (unconstructed filter object)
            "params": Tuned parameters as dictionary
            
        This file can be easily reconstructed as initialized filter object with
        most optimal values by FilterLoader
        '''
        
        file_path = os.path.join(settings.FILTERS_PATH, self.save_file_name)
        saveIntoFile( self.filt( **best_params ), fileName = file_path)

 
    def _calcCombinations(self,tuned_params):      
        #{"abbe_lim": [0.37,0.4], "a":[1]}--> ???
        #{[{"abbe_lim": 0.37, "a":1},{"abbe_lim": 0.4}, "a":1]
        pass 
