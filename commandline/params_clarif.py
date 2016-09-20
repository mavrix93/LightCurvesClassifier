'''
Created on Apr 12, 2016

@author: Martin Vo

There are mainly work classes for calculating parameters for filtering methods
'''

import sys, os
from db_tier.qso_catalogue import OgleQso
from cProfile import label
myPath = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, myPath + '/../')
import numpy as np
from stars_processing.filters_impl.word_filters import HistShapeFilter,\
    VariogramShapeFilter
from stars_processing.filters_impl.compare import ComparingFilter
from stars_processing.filtering_manager import FilteringManager
from utils.stars import count_types

from utils.helpers import get_borders
from sklearn.cross_validation import train_test_split

from sklearn.naive_bayes import GaussianNB
from utils.output_process_modules import saveIntoFile, loadFromFile
from stars_processing.filters_impl.abbe_value import AbbeValueFilter
from utils.advanced_query import updateStar
from stars_processing.filters_impl.color_index import ColorIndexFilter
from astroML.classification.gmm_bayes import GMMBayes
from sklearn.qda import QDA
import pylab as plt
from sklearn.linear_model.logistic import LogisticRegression
from sklearn.lda import LDA
from sklearn.grid_search import GridSearchCV
from db_tier.stars_provider import StarsProvider


def find_symbolic_space_params(searched_stars,contamination_stars,tuned_params,estimator,n_jobs=1):
    '''
    Search in the whole symbolic space and find optimal parameters
                       
    @param searched_stars: List of searched star objects
    @param contamination_stars: List of undesired star objects 
    @param tuned_params: Dictionary of lists for every parameter we want to tune
    (it depends on implementation of given estimator)
    @param estimator: Estimator class which evaluate propriety of parameters 
    @param n_jobs: Number of jobs ran simultaneously 
    
    EXAMPLE:    
    ...    
    estimator = QsoParamsEstimator()
    tuned_params = {"treshold":np.linspace(10,40,4),
                    "hist_days_per_bin":[5,20,40],
                    "hist_alphabet_size":[5,8,16],
                    "vario_days_per_bin":[10,20,40],
                    "vario_alphabet_size":[5,8,16]} 
    
    '''

    #Perform grid search
    gs = GridSearchCV(estimator, tuned_params,n_jobs)
    gs.fit(searched_stars+contamination_stars,y=[1 for i in range(len(searched_stars))]+[0 for i in range(len(contamination_stars))])
    best_params =  gs.best_params_

    print best_params
    fi = open("grid_search_params.txt","w")
    fi.write(best_params)
    fi.close()
    


def vi_index_distr():
    '''Download all stars from MQS db and plot V-I,I-R color diagram'''
    
    qso_client = OgleQso({"ra":0,"dec":0,"rad":999})
    all_stars = (qso_client.getStars())
    
    vi = []
    ir = []
    for st in all_stars:
        vii = st.bvi["V"] -st.bvi["I"]
        err = st.bvi["I"] -st.bvi["R"]
        if vii >-15 and vii <15 and err > -15 and err<15:
            vi.append(vii)
            ir.append(err)
    vi = np.array(vi)
    ir = np.array(ir)
    plt.xlabel("I-R [mag]")
    plt.ylabel("V-I [mag]")
    plt.plot(ir,vi,"bo")
    plt.show()



def bvi_diagram(many_stars, ab = 0.5):
    '''
    Show color diagram. Query in OGLE II db in order to obtain BV, VI values
    will be executed.
    
    @param stars: List of another lists, which contains stars. Star type for each list.
    (OGLEII identifiers are needed for obtaining color indexes)
    @param ab: Abbe criterion
    '''
    
    
    col_ind = []
    
    for stars in many_stars:
        s = []
        nu = len(stars)
        for st in stars:
            if st.getAbbe() <ab:
                try:
                    st = updateStar(st)
                    bv = st.bvi["b_v"]
                    vi = st.bvi["v_i"]
                    s.append([bv,vi])
                    type_name = st.starClass
                except KeyError:
                    nu -= 1
            
        if len(s) > 0: col_ind.append([s,type_name,nu])
        
    
    a = []
    for stars,ty_name,le in col_ind:
        s = np.array(stars)
        print s
        bv = s[:,0]
        vi = s[:,1]
        score = 0
        for i in range(len(bv)):
            score += 1
        a.append([ty_name,score/float(le)])
    
    for na,sc in a:
        print na,sc
    
    
    for stars,ty_name,le in col_ind:
        s = np.array(stars)
        try:
            si = 10
            if ty_name == "QSO": si = 15
            plt.title("Abbe value cut: 0.5")
            plt.plot(s[:,0],s[:,1],"*",label=ty_name,markersize=si)
            plt.xlabel("B-V [mag]")
            plt.ylabel("V-I [mag]")
        except IndexError:
            print s
    plt.legend()
    plt.show()

    



def hist_vario_clustering():
    '''WORK VERSION of histogram-variogram space clustering'''
    
    '''vario_alphabet_size=17
    hist_days_per_bin=97
    hist_alphabet_size=7
    treshold= 99
    vario_days_per_bin =9
    
    path1 = "../../data/light_curves/qso_eyer"
    path2 = "../../data/light_curves/quasars"
    path4 = "../../data/light_curves/lpv"
    path3 = "../../data/light_curves/some_stars"
    path5 = "../../data/light_curves/be_eyer"
    path6 = "../../data/light_curves/mqs_quasars"
    path7 = "../../data/light_curves/dpv"
    path8 = "../../data/light_curves/rr_lyr"
    path9 = "../../data/light_curves/cepheids"
    
    a = 4
    quasars = StarsProvider().getProvider(path=path2,obtain_method="file",star_class="ogle_quasars").getStarsWithCurves()[:a]
    qso_eyer=  StarsProvider().getProvider(path=path1,obtain_method="file",star_class="qso eyer").getStarsWithCurves()[:a]
    stars =  StarsProvider().getProvider(path=path3,obtain_method="file",star_class="star").getStarsWithCurves()[:a]
    be =  StarsProvider().getProvider(path=path5,obtain_method="file",star_class="be-star eyer").getStarsWithCurves()[:a]
    lpv =  StarsProvider().getProvider(path=path4,obtain_method="file",star_class="lpv").getStarsWithCurves()[:a]
    dpv =  StarsProvider().getProvider(path=path7,obtain_method="file",star_class="dpv").getStarsWithCurves()[:a]
    rr_lyr =  StarsProvider().getProvider(path=path8,obtain_method="file",star_class="RR Lyr").getStarsWithCurves()[:a]
    cep =  StarsProvider().getProvider(path=path9,obtain_method="file",star_class="cep").getStarsWithCurves()[:a]
    macho_quasars = StarsProvider().getProvider(path=path6,obtain_method="file",star_class="macho_quasars").getStarsWithCurves()[:a]
    
    quasars_train, quasars_test, y_train, y_test = train_test_split(quasars+macho_quasars,  [1 for i in range(len(quasars+macho_quasars))], test_size=0.7, random_state=0)
    
    def dec_func(bv,vi):
        if bv <1.5 and vi <1.5:
            return True
        return False
    
    cf = []
    cf.append(HistShapeFilter(hist_days_per_bin, hist_alphabet_size))
    cf.append(VariogramShapeFilter(vario_days_per_bin, vario_alphabet_size))
    
    comp_filt = ComparingFilter(cf, quasars_train, treshold, search_opt="closest", filt_opt="together")
    
    filteringManager = FilteringManager(qso_eyer+cep+rr_lyr+dpv+lpv+be+quasars_test+stars)
    filteringManager.loadFilter(AbbeValueFilter(0.5))
    filteringManager.loadFilter(ColorIndexFilter(dec_func, pass_not_found=True))
    filteringManager.loadFilter(comp_filt)
    
    result_stars = filteringManager.performFiltering()
    saveIntoFile(result_stars,"../../data")'''
    
    result_stars = loadFromFile("../../data", "res4_all")
    plt.figure(figsize=(20,10))
   
    x = {}
    for star in result_stars:
        if not star.starClass in x:
            x[star.starClass] = [star.scoreList]
        else:
            x[star.starClass].append(star.scoreList) 
    q_x,q_y = [],[]
    s_x,s_y = [], []        
    for key,value in x.iteritems():
        xx = np.array(value)
        if key in ["ogle_quasars","qso eyer","macho_quasars"]:
            plt.plot(xx[:,0],xx[:,1],"*",label=key,markersize=15)
            q_x += xx[:,0].tolist()
            q_y += xx[:,1].tolist()
        else:
            plt.plot(xx[:,0],xx[:,1],"o",label=key,markersize=9)
            s_x += xx[:,0].tolist()
            s_y += xx[:,1].tolist()
    plt.xlabel("Histogram distance")
    plt.ylabel("Variogram distance")
    
    q = zip(q_x,q_y)
    s= zip(s_x,s_y)
    X_train, X_test, y_train, y_test = train_test_split(q+s,  [1 for i in range(len(q))]+[0 for i in range(len(s))], test_size=0.7, random_state=0)
    meths= (GaussianNB, QDA,GMMBayes,LogisticRegression,LDA)
    meth = meths[4]
    clf = meth()
    
    clf.fit(X_train,y_train)
    xlim = (0, 20)
    ylim = (0, 25)
    xx, yy = np.meshgrid(np.linspace(xlim[0], xlim[1], 100),
                         np.linspace(ylim[0], ylim[1], 100))
    Z = clf.predict_proba(np.c_[xx.ravel(), yy.ravel()])
    Z = Z[:, 1].reshape(xx.shape)  
    
    def pol(x,a,b,c,d):
        return a*np.power(x,3) + b*np.power(x,2)+c*x+d
    
    def lin(x,a,b):
        return a*x+b
    
    
    #cut = 0.85
    g_ratio = []
    b_ratio = []
    gb_ratio = []
    cuts = []
    for cc in range(88,89,10):
        cut = cc/100.0 
        xxx,yyy = get_borders(xx, yy, Z, cut)
        #**a,b,c,d= np.polyfit(xxx, yyy, 3)
        a,b = np.polyfit(xxx,yyy,1)
        p = []
        for i in xxx:
            #**p.append(pol(i,a,b,c,d))
            p.append(lin(i,a,b))
        
        plt.plot(xxx,p,"g--")
        plt.pcolor(xx,yy,Z)    
        plt.legend()
        plt.colorbar()
        
        ac = ["ogle_quasars","qso eyer","macho_quasars"]    
        good = 0
        bad = 0
        yy_stars = []
        for st in result_stars:
            hist,vario = st.scoreList
            if lin(hist,a,b)> vario:
            #**if pol(hist,a,b,c,d)> vario:
                yy_stars.append(st)
                if st.starClass in ac:                
                    good+=1
                else: bad +=1
        cuts.append(cut)
        
        gb_ratio.append(good/float(len(q_x))-bad/float(len(s_x)))
        g_ratio.append(good/float(len(q_x)))
        b_ratio.append(bad/float(len(s_x)))
        

    '''plt.clf()
    plt.xlabel("Probability level")
    plt.ylabel("Relative number")
    plt.title("Maximum of 'true positive' - 'false positive': "+str(cuts[np.argmax(gb_ratio)]),loc="left")
    plt.title("Clustering method: QDA",loc="right")
    plt.plot(cuts,gb_ratio,"g--",label="True positive - false positive")
    plt.plot(cuts,g_ratio,"b-",label="True positive")
    plt.plot(cuts,b_ratio,"r-",label="False positive")
    plt.legend()
    plt.tight_layout()
    plt.show() '''
    x= count_types(result_stars)
    y = count_types(yy_stars)
    
    for key in y:
        #print key, y[key]/float(x[key])      
        print key, x[key],y[key]
        
    plt.title("Method: %s (cut %.02f)" % (meth.__name__,cut))
    plt.title("True positive: %.01f percent" %(100*good/float(len(q_x))),loc="left")
    plt.title("False positive: %.01f percent" %(100*bad/float(len(s_x))),loc="right")
    plt.tight_layout()
    plt.show()
        
        #plt.savefig("../../data/hv"+str(meth.__name__)+".png")


def roc_curve():
    '''WORK VERSION of histogram-variogram space clustering'''
    

    def dec_func(bv,vi):
        if bv <1.5 and vi <1.5:
            return True
        return False
    result_stars = loadFromFile("../../data", "res4_all")

   
    x = {}
    for star in result_stars:
        if not star.starClass in x:
            x[star.starClass] = [star.scoreList]
        else:
            x[star.starClass].append(star.scoreList) 
    q_x,q_y = [],[]
    s_x,s_y = [], []        
    for key,value in x.iteritems():
        xx = np.array(value)
        if key in ["ogle_quasars","qso eyer","macho_quasars"]:
            q_x += xx[:,0].tolist()
            q_y += xx[:,1].tolist()
        else:
            s_x += xx[:,0].tolist()
            s_y += xx[:,1].tolist()

    
    q = zip(q_x,q_y)
    s= zip(s_x,s_y)
    X_train, X_test, y_train, y_test = train_test_split(q+s,  [1 for i in range(len(q))]+[0 for i in range(len(s))], test_size=0.7, random_state=0)
    meths= (GaussianNB, QDA,GMMBayes,LogisticRegression,LDA)
    meth = meths[4]
    clf = meth()
    
    clf.fit(X_train,y_train)
    xlim = (0, 20)
    ylim = (0, 25)
    xx, yy = np.meshgrid(np.linspace(xlim[0], xlim[1], 100),
                         np.linspace(ylim[0], ylim[1], 100))
    Z = clf.predict_proba(np.c_[xx.ravel(), yy.ravel()])
    Z = Z[:, 1].reshape(xx.shape)  
    
    def pol(x,a,b,c,d):
        return a*np.power(x,3) + b*np.power(x,2)+c*x+d
    
    def lin(x,a,b):
        return a*x+b

    #cut = 0.85
    g_ratio = []
    b_ratio = []
    gb_ratio = []
    cuts = []
    for cc in range(1,100,1):
        cut = cc/100.0 
        xxx,yyy = get_borders(xx, yy, Z, cut)
        #**a,b,c,d= np.polyfit(xxx, yyy, 3)
        a,b = np.polyfit(xxx,yyy,1)
        p = []
        for i in xxx:
            #**p.append(pol(i,a,b,c,d))
            p.append(lin(i,a,b))

        ac = ["ogle_quasars","qso eyer","macho_quasars"]    
        good = 0
        bad = 0
        yy_stars = []
        for st in result_stars:
            hist,vario = st.scoreList
            if lin(hist,a,b)> vario:
            #**if pol(hist,a,b,c,d)> vario:
                yy_stars.append(st)
                if st.starClass in ac:                
                    good+=1
                else: bad +=1
        cuts.append(cut)
        
        gb_ratio.append(good/float(len(q_x))-bad/float(len(s_x)))
        g_ratio.append(good/float(len(q_x)))
        b_ratio.append(bad/float(len(s_x)))
        
       
    plt.clf() 
    plt.title("ROC curve")
    plt.xlabel("False positive rate")
    plt.ylabel("True positive rate")
    xxx = np.linspace(0,1,50)
    plt.plot(xxx,xxx,"r--")
    plt.plot([1] + b_ratio,[1] + g_ratio,"g-")
    plt.tight_layout()
    plt.show() 

#roc_curve()
#hist_vario_clustering()