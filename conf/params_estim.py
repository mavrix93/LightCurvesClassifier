'''
Created on Jul 22, 2016

@author: Martin Vo
'''
from sklearn.base import BaseEstimator, ClassifierMixin
from stars_processing.filtering_manager import FilteringManager
from utils.stars import count_types
from entities.exceptions import StarAttributeNotSpecified
from sklearn.grid_search import GridSearchCV
from utils.helpers import verbose
from conf.settings import VERBOSITY
from utils.output_process_modules import saveIntoFile
from conf import settings
import os


class DefaultEstimator(BaseEstimator, ClassifierMixin):
    '''
    This is default estimator which can be used for calculating parameters
    of star filters. Input params of methods of the class is directed
    by GridSearch and ParamsEstimation (see below).
    Scoring function is defined by the result of filtering via given combinations
    of parameters. Evaluation of certain combination of params is by given by "score_calc" as 
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
        filt.loadFilter(self.filt(**self.tuned_params))
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


class ParamsEstimation(object):
    '''
    This class is responsible for calculating best params of star filters 
    according to train classified stars.  
    '''

    def __init__(self, searched,others,filt,
                 tuned_params, estimator = DefaultEstimator(),
                 save_file = "GridSearch_params.pickl"):
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
        self.tuned_params = {"tuned_params":tuned_params}
        self.estimator = estimator
        
        self.save_file_name = save_file
        
    def fit(self):
        ''' Make a fit according to given stars and find best parameters '''
        
        gs = GridSearchCV(self.estimator, self.tuned_params,fit_params={"filt":self.filt})
        gs.fit(self.searched + self.others,y=[1 for i in range(len(self.searched))]+[0 for i in range(len(self.others))])
        best_params =  gs.best_params_['tuned_params']
        
        print best_params
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
        most optimal values:
        
            objects = loadFromFile(os.path.join(settings.FILTERS_PATH,"GridSearch_params.pickel"))
            uninstanc_filter = objects["filter"]
            params = objects["params"]
            
            ready_filter = uninstanc_filter(**params)
        '''
        
        file_path = os.path.join(settings.FILTERS_PATH, self.save_file_name)
        saveIntoFile({"filter": self.filt, "params": best_params}, fileName = file_path)

        
        
        
    def _calcCombinations(self,tuned_params):      
        #{"abbe_lim": [0.37,0.4], "a":[1]}--> ???
        #{[{"abbe_lim": 0.37, "a":1},{"abbe_lim": 0.4}, "a":1]
        pass 
