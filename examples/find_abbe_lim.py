'''
Created on Sep 9, 2016

@author: Martin Vo

This example shows searching for the best abbe value criterion for searching quasars
according given quasars and ordinary stars curves 
'''


from stars_processing.filters_tools.params_estim  import ParamsEstimation
from conf import settings
from db_tier.stars_provider import StarsProvider
from stars_processing.filters_impl.abbe_value import AbbeValueFilter
import numpy



def main():
    files_prov_quasars = StarsProvider().getProvider(path=settings.OGLE_QSO_PATH,
                                             files_limit=30,
                                             obtain_method="file",
                                             star_class="quasar") 
    
    files_prov_stars = StarsProvider().getProvider(path=settings.STARS_PATH,
                                             files_limit=30,
                                             obtain_method="file",
                                             star_class="star")
    
    #Get stars and quasars objects with light curves
    stars =  files_prov_stars.getStarsWithCurves()
    quasars =  files_prov_quasars.getStarsWithCurves()
    
    #Get all combinations of parameters which will be tried
    tuned_params = []
    for abbe in numpy.linspace(0.01,0.99,20):
        tuned_params.append({"abbe_lim": abbe})
    
    #Use default estimator and fit input objects
    es = ParamsEstimation(quasars,stars,AbbeValueFilter, tuned_params)
    es.fit()


if __name__ == '__main__':
    main()