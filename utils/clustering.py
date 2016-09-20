'''
Created on Apr 2, 2016

@author: Martin Vo
'''


import scipy
import scipy.spatial.distance as ssd
from matplotlib import pyplot as plt
from scipy.cluster.hierarchy import dendrogram, fcluster
from utils.data_analysis import sort_pairs
import numpy as np
from stars_processing.filtering_manager import FilteringManager
from stars_processing.filters_impl.word_filters import HistShapeFilter,\
    VariogramShapeFilter, CurvesShapeFilter
from stars_processing.filters_impl.abbe_value import AbbeValueFilter
from utils.stars import getStarsLabels, resultEvalaution, plotStarsPicture
from stars_processing.filters_impl.compare import ComparingFilter
import networkx as nx   
from utils.output_process_modules import saveIntoFile
from sklearn.cross_validation import train_test_split
from conf.settings import TO_THE_DATA_FOLDER


#TODO: Need to be cleaned



def getVarioHistSpace(searched_stars,another_stars,hist_days_per_bin,hist_alphabet_size,vario_days_per_bin,vario_alphabet_size):
    '''
    Plot hist_vario space of given star objects. Sample searched star object
    will be splitted into train and test sample. 
    '''
    
    treshold = 99

    searched_train, searched_test, y_train, y_test = train_test_split(searched_stars, [1 for i in range(len(searched_stars))], test_size=0.6, random_state=0)
    
    filteringManager = FilteringManager(another_stars+searched_test)
    cf = []
    cf.append(HistShapeFilter(days_per_bin=hist_days_per_bin,alphabet_size=hist_alphabet_size))   
    cf.append(VariogramShapeFilter(days_per_bin=vario_days_per_bin,alphabet_size=vario_alphabet_size)) 
    comp_filt = ComparingFilter(cf, searched_train, treshold, search_opt="closest")
    filteringManager.loadFilter(comp_filt)
   
    res_stars = filteringManager.performFiltering()
    
    result_qsos, result_stars = resultEvalaution(res_stars,["QSO","qso"])
    #result_qsos, result_eyer = resultEvalaution(result_qsos,["QSO","qso","quasar"])
    
    hist_q, vario_q = [],[]
    hist_s, vario_s = [],[]
    #hist_e, vario_e = [],[]
    for st in result_qsos:
        coo = st.scoreList
        hist_q.append(coo[0])
        vario_q.append(coo[1])
    for st in result_stars:
        coo = st.scoreList
        hist_s.append(coo[0])
        vario_s.append(coo[1])
    
    plt.xlabel("Histogram distance")
    plt.ylabel("Variogram distance")
    plt.plot(hist_q, vario_q,"ro")
    plt.plot(hist_s, vario_s,"bo")
    plt.show()
    

    

def getClusters(all_stars,vario_alphabet_size, hist_days_per_bin, hist_alphabet_size, vario_days_per_bin, db ):    
    '''
    Get members (stars) of clusters. Membership will be determined according to
    given metric and criterion for maximal distance of stars/clusters
    
    @param all_stars: Stars which will be clustered
    @param days_per_bin: Length of words (for SAX)
    @param alphabetSize: Size of alphabet (for SAX)
    @param save_plots: Option whether plot of stars will be saved (folder per cluster)
    
    @return: List of members of clusters and it save their plots into folders
    '''
    
    #Prefiltering (cut off high abbe value objects)
    #all_stars = _preFiltAbbe(all_stars,abbe_lim=0.55)
    
    
    #Get distances between stars
    tree = getAllDistances(all_stars,vario_alphabet_size, hist_days_per_bin, hist_alphabet_size, vario_days_per_bin,db )
    star_names = getStarsLabels(all_stars, "names",db)
    Z = getLinkageMat(tree,star_names)
    treshold = 13
    saveIntoFile((Z,all_stars),TO_THE_DATA_FOLDER+"clusters/", "linkage_mat")
    
    #Get members of clusters
    clusters = getClusterMembers(Z,all_stars,treshold)
    
    #plotDendo(Z,all_stars,treshold)
    return clusters


def show_distance_matrix(dist_matrix):
    # Create a graph
    G = nx.Graph()
    
    labels = {}
    for n in range(len(dist_matrix)):
        for m in range(len(dist_matrix)-(n+1)):
            G.add_edge(n,n+m+1)
            labels[ (n,n+m+1) ] = str(round(dist_matrix[n][n+m+1],2))
    
    pos=nx.spring_layout(G)
    
    nx.draw(G, pos)
    nx.draw_networkx_edge_labels(G,pos,edge_labels=labels,font_size=30)
    
    
    plt.show()




def getLinkageMat(scores_dict,star_names):
    '''
    Get linkage matrix (see scipy.cluster.hierarchy.linkage) which could be used
    for next processing such as sorting stars into clusters or visualizing dendrograms  
    
    @param scores_dict: Dictionary of scores (distances) between pairs of stars
    @param star_names: List of star names in scores_dist    
    @return: Linkage matrix
    '''
    
    dist_matrix = getDistMatrix(scores_dict,star_names)
    
    #show_distance_matrix(dist_matrix)
    
    y = ssd.squareform(dist_matrix)
    Z = scipy.cluster.hierarchy.linkage(y, method='complete', metric='euclidean')    
    return Z

def getDistMatrix(scores_dict,star_names):
    distMatrix = []
    for r in star_names:
        row = []
        for c in star_names:
            if (c,r) in scores_dict: row.append(scores_dict[(c,r)])
            else: row.append(0)
        distMatrix.append(row)
    return distMatrix

    
def getClusterMembers(Z,stars,depth_crit):
    '''
    Get members of clusters according to given linkage matrix. Number of clusters
    will be determined according to cut off value which represent max distance
    for merging clusters and stars into one cluster
    
    @param Z: Linkage matrix
    @param stars: List of stars objects
    @param depth_crit: Cut off value
    '''
    
    #Get list of indexes which represent cluster into which star (on that position of stars list) belongs 
    clust_ind = fcluster(Z, depth_crit, criterion='distance')
    
    #Sort pairs cluster index - star object according to indexes
    clust_ind, stars = sort_pairs(clust_ind, np.array(stars))
    clusters = []
    cluster = []
    clust_num = 0
    
    #Get list stars for each cluster
    for ide,star in zip(clust_ind, stars):
        print ide,star
        if ide > clust_num:
            clust_num += 1
            if len(cluster) > 0: clusters.append(cluster)
            cluster = []
            
        if ide == clust_num:
            cluster.append(star)
    clusters.append(cluster)
    return clusters
    
    
def plotDendo(Z,stars,max_d,db):  
    '''
    Plot dendrogram
    
    @param Z: Linkage matrix
    @param stars: List of stars
    @param max_d:   Cut off value (there are no effect on functionality,
                    it will be just plotted as horizontal line
    '''  
    labels = getStarsLabels(stars,"types",db)
    
    plt.figure(figsize=(25, 10))
    plt.title('Hierarchical Clustering Dendrogram')
    plt.xlabel('Stars')
    plt.ylabel('Distance')
    dendrogram(
        Z, 
        p=12,
        labels=labels,
        leaf_rotation=90., 
        leaf_font_size=8.,
        show_contracted=True,
    )
    plt.axhline(y=max_d, c='k')
    plt.tight_layout()
    plt.show()
        

def getAllDistances(all_stars,vario_alphabet_size, hist_days_per_bin, hist_alphabet_size, vario_days_per_bin,db ):  
    '''
    This method returns dissimilarities between each stars. Dissimilarity is 
    could be defined in _dissimilarityDistance method.
    
    @param all_stars: List of stars which will be compared each other
    @return: Dictionary:
        @keyword (first star name, second star name): Dissimilarity
        
    '''
    
    treshold = 999
    i = 0
    tree = {}    
    

    for filt_star in all_stars:
        filteringManager = FilteringManager(all_stars)
        cf = []
        cf.append(HistShapeFilter(hist_days_per_bin,hist_alphabet_size))
        cf.append(VariogramShapeFilter(vario_days_per_bin,vario_alphabet_size)) 
        comp_filt = ComparingFilter(cf, [filt_star], treshold, search_opt="passing")
        filteringManager.loadFilter(comp_filt)
       
        stars = filteringManager.performFiltering()
        
        
        for star in stars:
            tree[(star.ident[db]["name"],filt_star.ident[db]["name"])]= _dissimilarityDistance(star,filt_star)
        i += 1 
    return tree

def _dissimilarityDistance(star1,star2):
    '''Definition of distance (dissimilarity) of stars in our metric'''
    #return star1.matchScore*(star1.getAbbe()-star2.getAbbe())**2
    return sum(star1.scoreList)

def _preFiltAbbe(all_stars,abbe_lim=0.25):
    '''Filter star via abbe limitation'''
    
    abbe_filter = AbbeValueFilter(abbe_lim)
    filteringManager = FilteringManager(all_stars)
    filteringManager.loadFilter(abbe_filter)
    return filteringManager.performFiltering()  


