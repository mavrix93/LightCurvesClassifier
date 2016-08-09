'''
Created on Feb 5, 2016

@author: Martin Vo

There are methods for reviewing results (mainly stars)
'''

from utils.clustering import getClusterMembers, plotDendo
from db_tier.stars_provider import StarsProvider                        
from utils.stars import plotStarsPicture
from utils.output_process_modules import loadFromFile



def show_clust(treshold,clust_num,fi_path="../../data/clusters/", fi_name="linkage_mat",save_plots=False,db="ogle"):
    '''
    Show clusters from object file of linkage matrix and star objects (produced by clustering)
    
    @param treshold: Criterion for dividing clusters
    @param clust_num: Number of cluster to plot
    @param fi_path: Location of cluster folder
    @param fi_name: Name of cluster file
    @param save_plots: If tru stars of cluster (clust_num) will be plotted
    '''
    
    Z,all_stars = loadFromFile(fi_path,fi_name) 
    clusters = getClusterMembers(Z,all_stars,treshold)
    plotDendo(Z,all_stars,treshold,db)
    plotStarsPicture(clusters[clust_num],without_match=True)

    if (save_plots == True):
        dir_id = 1
        for clust in clusters:
            plotStarsPicture(clust,option="save", save_loc="../../data/clusters/"+str(dir_id)+".cluster_"+str(len(clust)),without_match=True)
            dir_id += 1


        
def showStarsCurves(path,plot_option="show",save_loc="../../data/ogle_qso_cand"):
    '''
    This method get stars from given folder and show/save their plots
    
    @param path: Path to the folder of star light curves
    @param plot_option: Option of plotting (show/save plots)
    @param save_loc: Location for saving plots
    '''
       
    all_stars =  StarsProvider().getProvider(obtain_method="file",path=path,star_class="").getStarsWithCurves()   
    plotStarsPicture(all_stars,option=plot_option,save_loc=save_loc) 
    

show_clust(1, 1)    