'''
Created on Apr 12, 2016

@author: Martin Vo
'''
from entities.exceptions import InvalidFilteringParams
from utils.helpers import verbose, progressbar
import numpy as np

from conf import settings

from utils.commons import returns,accepts
from stars_processing.filters_tools.base_filter import BaseFilter

class ComparingFilter(BaseFilter):
    '''
    This class is responsible for comparing stars according to implementations
    of comparing subfilters 
    '''
    
    SEARCH_OPTIONS = ["closest","passing"]
    FILTER_OPTIONS = ["together","onebyone"]

    def __init__(self, compar_filters,compar_stars,treshold,search_opt="closest",filt_opt="together"):
        '''
        @param compar_filters: List of comparing subfilters
        @param compar_stars: Stars which will be used as filtering templates
        @param treshold: Complete sum of distances of comparing filters
        @param search_opt: Option for searching:
            "closest": Find the nearest template star (lowest sum of distances)
            "passing": Find a star which match score (sum of distances) is lower then treshold
            
            Whether inspected stars pass thru this filter doesn't matter on search option,
            it just affect the match star and the score which will be assigned
            to the star
        '''
        self.comp_filters = compar_filters
        self.comp_stars = self.prepareStars(compar_stars)
        
        if hasattr(treshold, '__call__'):
            self.decis_fu = treshold
        
        #If just a one number was given, make list of length of given filters 
        elif type(treshold) == int or type(treshold) == float or type(treshold) == np.float64:
            self.treshold = [treshold for i in range(len(self.comp_filters))]
            self.decis_fu = self._default_decis_functio
        else:
            self.treshold = treshold
            self.decis_fu = self._default_decis_functio

        #Check validity of given search option
        if search_opt in self.SEARCH_OPTIONS:
            self.search_opt = search_opt
        else:
            raise InvalidFilteringParams("Unresolved search option.\nAvaible options: %s",self.SEARCH_OPTIONS)
        if filt_opt in self.FILTER_OPTIONS:
            self.filt_opt =filt_opt
        else:
            raise InvalidFilteringParams("Unresolved filter option.\nAvaible options: %s",self.FILTER_OPTIONS)
         
        
        
    @accepts(list)
    @returns(list)    
    def applyFilter(self,stars):
        if (self.filt_opt == "together"):
            return self.togetherFilt(stars)
        elif (self.filt_opt == "onebyone"):
            return self.oneByOneFilt(stars)
        else:
            raise InvalidFilteringParams(self.filt_opt)
    
    
    def togetherFilt(self,stars):
        '''
        Apply all filters and return stars which distances were lower then treshold.
        A star pass thru filtering just if it pass thru all filters of a template star.
        
        @param stars: Stars which will be filtered
        @return: Stars which passed thru filtering
        '''
        
        #Let stars to obtain necessary values        
        stars = self.prepareStars(stars)
        
        result_stars = []
        for star in progressbar(stars,"Comparative filtering: "): 
            match, score_list = self._filtOneStar(star)
   
            if self.decis_fu(score_list):
                star.putMatchStar(match)
                star.scoreList = score_list
                result_stars.append(star)
        return result_stars
    
    
    def oneByOneFilt(self,stars):
        '''
        Apply filter individually. Stars which pass thru one filter will
        be filtered by second one etc. Output are stars passed thru all filters.
        For each filter will be used particular treshold value.
        
        @param stars: List of star objects which will be compared with template stars
        @return: List of stars passed thru filtering appended by match scores
        '''
        
        #Let stars to obtain necessary values
        stars = self.prepareStars(stars)
        
        for i,filt in enumerate(self.comp_filters):
            stars = self._applyOneFilter(filt,stars,self.treshold[i])
        return stars
            
        
    
    def _applyOneFilter(self,filt,stars,this_treshold):
        '''
        @param filt: Comparative filter which will be applied 
        @param stars: List of star objects which will be compared with template stars
        @param this_treshold: Treshold value for current filter
        
        @return: List of stars passed thru filtering appended by match scores
        '''
        result_stars = []
        for star in stars: 
            score = self._lookUpForMatchStar(star,filt,this_treshold)
            if score:
                star.putScore(score)
                star.putIntoScoreList(score)
                result_stars.append(star)
        return result_stars
    
    def _lookUpForMatchStar(self,star,filt,this_treshold):
        '''
        @param star: Star which will be compared with template stars
        @param filt: Comparative filter which will be applied 
        @param this_treshold: Treshold value for current filter
        
        @return: Best score of match or if option is "passing" the first score of match
                 which passed will be returned. If there are no match for given treshold
                 False will be returned
        '''
        
        best_score = 99
        for comp_star in self.comp_stars:  
            score = filt.compareTwoStars(star,comp_star)
            
            if (self.filt_opt == "passing" and score <= this_treshold):
                star.putScore(score)
                star.putIntoScoreList(score)
                return score
            if (score < best_score):
                best_score = score
            
        if (best_score == 99): return False  
        
        return best_score
    
    
             
    def _filtOneStar(self,star):
        '''
        Calculate distances of inspected star and template stars
        
        @return: Best matched template star, its score and list of scores for each comp. filter
        '''
        
        best_score = 99
        best_match = None
        best_score_list = []
        
        #Try every template star
        for comp_star in self.comp_stars:
            this_score_list = []
            
            #Apply all comparative filters
            for filt in self.comp_filters:
                this_score = filt.compareTwoStars(star,comp_star)  
                this_score_list.append(this_score)
            
            #Return best match if match is sufficient (there is no need to find best match)                             
            if (self.search_opt == "passing" and self.decis_fu(this_score_list)):
                return comp_star, this_score_list
            
            #Note best match
            if sum(this_score_list) < best_score:
                best_score = sum(this_score_list)
                best_match = comp_star 
                best_score_list = this_score_list            
            
        return best_match, best_score_list
    
    
    def prepareStars(self,stars):
        '''Obtain necessary attributes for given stars'''
         
        verbose("There are %i stars which will be prepared..." %len(stars),3, settings.VERBOSITY)
        prepared_stars = []
        for star in progressbar(stars,"Preparing stars for comparative filtering: "):
            for filt in self.comp_filters:
                star = filt.prepareStar(star)            
            prepared_stars.append(star)
        verbose("Stars were prepared",2, settings.VERBOSITY)
        return stars
    
    def _default_decis_functio(self,score_list):
        treshold_score_list = self.treshold
        if len(score_list) != len(treshold_score_list):
            raise InvalidFilteringParams("Wrong length of treshold list")
        
        for i in range(len(score_list)):
            if score_list[i]> treshold_score_list[i]:
                return False
        return True
            