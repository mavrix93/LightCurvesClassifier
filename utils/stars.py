'''
Created on Mar 18, 2016

@author: Martin Vo

There are common functions for list of star objects (evaluation, plotting...)
'''

import matplotlib.pyplot as plt
import os
import warnings
from conf.settings import *


def resultEvalaution(stars,class_types = ["QC"]):
    '''
    This method decide about correction of filtering according matched star type
    
    @param stars: Inspected list of stars (with attribute starClass)
    @param class_types: Name of class types which we will searching for in all stars
    
    @return: Number of stars which have class_type and stars which do not have it
    '''
    right_stars = []
    wrong_stars = []
    for star in stars:
        if (star.starClass in class_types):
            right_stars.append(star)
        else:
            wrong_stars.append(star)
    print "Good identification: ",len(right_stars), "\tBad identification: ", len(wrong_stars)
    
    return right_stars, wrong_stars
    
    

def count_types(stars):
    """
    Return dictionary of name star type and its number in given list
    
    @param stars: List of star objects resolved with class attribute 'starClass'
    """
    x = {}
    for st in stars:
        star_type = st.starClass
        
        if not star_type in x:
            x[star_type] = 1
        else:
            x[star_type] +=1
    return x
        
        
def get_sorted_stars(stars):
    """
    Get dictionary of star type and list of stars of this kind
    
    @param stars: List of star objects resolved with class attribute 'starClass'
    """
    
    x = {}
    for st in stars:
        star_type = st.starClass
        
        if not star_type in x:
            x[star_type] = [st]
        else:
            x[star_type].append(st)
    return x
        

    
def whichIsNotIn(first_list,second_list):
    '''
    This method decides which items from first list is not in the second list
    
    @return: List of unique items 
    ''' 
    rest_items =[]
    for item1 in first_list:
        if not item1 in second_list:
            rest_items.append(item1)
    return rest_items

def getStarsLabels(stars,opt="names",db=None):
    '''
    This method returns list of star names for given list of star objects
    
    @param stars: List of star objects
    @param opt: Option for format of retrieving star names
    
    @return: List of star names
    '''
    OPTIONS = ["names","types"]
    
    if not opt in OPTIONS:
        raise AttributeError("There are no option %s for getStarsLabels" %opt)
    
    
    labels =  []
    for star in stars:
        if opt=="names": labels.append(star.ident[db]["name"])
        if opt =="types": labels.append(str(star.ident[db]["name"])+": "+str(star.starClass))
    return labels








#**********    Plotting    ********

def plotStarsPicture(stars, option="show", hist_bins = None, vario_bins = None, center=True, save_loc=None, num_plots = None):
    '''
    This function plot three graphs for all stars: Light curve, histogram
    and variogram. Additionally Abbe value will be displayed
    
    @param stars: List of star objects to be plot
    @param option: Option whether plots will be saved or just showed
    '''   
    
    OPTIONS = ["show","save"]
    if not (option in OPTIONS):
        raise Exception("Invalid plot option")

    for num,star in enumerate(stars[:num_plots]):
        num_rows = 1
        
        if (star.lightCurve != None):    
            fig = plt.figure(figsize=(20, 6))
            ax1 = fig.add_subplot(31+num_rows*100)
            ax1.set_xlabel("Magnitude [mag] + %.02f mag" % star.lightCurve.mag.mean())
            ax1.set_ylabel("Normalized counts")
          
            hist,indices = star.getHistogram( bins = hist_bins)
            
            ax1.set_title("Abbe index: %.2f" %star.getAbbe(),loc="left")
            
            width = 1 * (indices[1] - indices[0])
            center = (indices[:-1] + indices[1:]) / 2
            ax1.bar(center, hist, align='center', width=width,color="blue")
 
            ax2 = fig.add_subplot(33+num_rows*100)
            
            ax2.set_xlabel("JD [days]")
            ax2.set_ylabel("Magnitude [mag]" )
            ax2.errorbar(star.lightCurve.time,star.lightCurve.mag, yerr=star.lightCurve.err,fmt='o', ecolor='r')
        
            ax3 = fig.add_subplot(32+num_rows*100)
            if not star.starClass: star.starClass = ""
            ax3.set_title("Star: {0}: {1}".format(star.name,star.starClass))
            ax3.set_xlabel("log(h [days])")
            ax3.set_ylabel("log (I_i - I_j)^2")
            x_v, y_v= star.getVariogram( bins = vario_bins)
            ax3.plot(x_v,y_v,"b--")
            
        else:
            warnings.warn("There are no light curve for plotting")
        
        
        
        if (option=="save"):
            if (save_loc == None):
                save_loc = ""
            else:
                if not os.path.exists(save_loc):         
                    os.makedirs(save_loc)
            
              
            plt.tight_layout()    
            fig.savefig(save_loc+"/"+star.getIdentName()+".png")
        else:
            try:
                plt.tight_layout()
                plt.show()
            except ValueError:
                raise Exception("There no light curves to plot")
        
        plt.close()




            

    
    
    
    
