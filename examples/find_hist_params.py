'''
Created on Sep 9, 2016

@author: Martin Vo
'''

from conf.params_estim  import ParamsEstimation
from conf import settings
from db_tier.stars_provider import StarsProvider
from stars_processing.filters_impl.compare import ComparingFilter
from stars_processing.filters_impl.word_filters import HistShapeFilter


def main():
    #Get stars
    NUM = 8
    SPLIT_RATIO = 0.5
    FROM1 = 10
    TO1 = 15
    FROM2 = 60
    TO2 = 120
    STEP2 = 30
    
    
    files_prov1 = StarsProvider().getProvider(path=settings.OGLE_QSO_PATH,
                                             files_limit=NUM,
                                             obtain_method="file",
                                             star_class="quasar")
    quasars =  files_prov1.getStarsWithCurves()
    
    
    files_prov2 = StarsProvider().getProvider(path=settings.STARS_PATH,
                                             files_limit=NUM,
                                             obtain_method="file",
                                             star_class="star")
    stars =  files_prov2.getStarsWithCurves()
    
    #Split quasars sample into train and test sample  
    DIV = NUM * SPLIT_RATIO
    quasars_train = quasars[:DIV]
    quasars_test = quasars[DIV:]
    
    #Generate tuned parameters
    tuned_params = []
    range1 = range(FROM1, TO1)
    range2 = range(FROM2, TO2, STEP2)
    TRESHOLD = 5    #Fix value of treshold for this example
    for HIST_ALPHABET_SIZE in range1:
        for HIST_DAYS_PER_BIN in range2:
            cf = []
            cf.append(HistShapeFilter(days_per_bin=HIST_DAYS_PER_BIN,
                                      alphabet_size=HIST_ALPHABET_SIZE))  
            
            treshold = TRESHOLD
        
            tuned_params.append({"compar_filters": cf, "compar_stars": quasars_train, "treshold": treshold})
    
    es = ParamsEstimation(quasars_test,stars, ComparingFilter, tuned_params)
    es.fit()
    

if __name__ == '__main__':
    main()