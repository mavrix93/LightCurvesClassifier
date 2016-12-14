'''
Created on Jul 22, 2016

@author: Martin Vo
'''
from utils.helpers import progressbar, clean_path, create_folder
from utils.output_process_modules import saveIntoFile
from conf import settings
import os
import numpy as np
from stars_processing.systematic_search.status_resolver import StatusResolver
import collections
import json



class DeciderEstimation(object):
    
    def __init__(self, searched, others, star_filter, tuned_params, log_path = None,
                 save_filter_name = None,**kwargs):
        '''
         tuned_params, decider,
                 save_file = DEFAULT_FILTER_NAME + "." + settings.OBJECT_SUFFIX, log_path = "." 
        '''
       
        
        # TODO: Custom split ratio
        
        self.searched = searched
        self.others = others   
        self.star_filter = star_filter
        self.tuned_params = tuned_params
        self.log_path = log_path
        
        if not save_filter_name:
            save_filter_name = star_filter.__class__.__name__ + "_tunedfilter." + settings.OBJECT_SUFFIX
        self.save_filter_name = save_filter_name
        
        self.params = kwargs
        if log_path:
            create_folder( log_path )
            if not os.path.isdir( log_path ):
                raise Exception("There is no folder %s" % log_path)
        
  
    def fit( self, save = True ):
        precisions = []
        filters = []
        stats = []
        i = 0
        for tun_param in progressbar(self.tuned_params, "Estimating combinations: "):
            i+=1
            
            x = tun_param.copy()
            x.update( self.params)
            filt = self.star_filter( **x )
            
            filt.learn(self.searched, self.others, learn_num = i )
            
            st = filt.getStatistic( self.searched, self.others )    
            precisions.append( st["precision"] )
            filters.append( filt )
            stats.append( st )
            
            z = collections.OrderedDict(tun_param).copy()
            z.update( collections.OrderedDict(st) )
            
            if save:
                StatusResolver.save_query([z], FI_NAME = clean_path(self.save_filter_name) +"_log.dat", PATH = self.log_path, DELIM = "\t" )
            
        best_id = np.argmax( precisions )
        
        print "*"*30
        try:
            print "Best params:\n%s\n" % json.dumps( self.tuned_params[best_id] , indent=4)            
        except:
            pass
        print "Statistic:\n%s\n" % json.dumps( stats[ best_id ] , indent=4)
            
        if save:
            saveIntoFile( filters[best_id] , path = settings.FILTERS_PATH, fileName = self.save_filter_name)
        
        return filters[best_id]
