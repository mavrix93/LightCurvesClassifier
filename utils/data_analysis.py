'''
Created on Mar 9, 2016

@author: Martin Vo

There are functions for processing data series
'''

import numpy as np
import math
import warnings


def to_PAA(x,box_size):
    """
    Funciton performs Piecewise Aggregate Approximation on data set, reducing
    the dimension of the dataset x to w discrete levels. returns the reduced
    dimension data set, as well as the indicies corresponding to the original
    data for each reduced dimension
    
    @param x: 1D serie of values
    @param box_size: Size for averaging values
    """
    
    n = len(x)
    stepFloat = n/float(box_size)
    step = int(math.ceil(stepFloat))
    frameStart = 0
    approximation = []
    indices = []
    i = 0
    while frameStart <= n-step:
        thisFrame = np.array(x[frameStart:int(frameStart + step)])
        approximation.append(np.mean(thisFrame))
        indices.append((frameStart, int(frameStart + step)))
        i += 1
        frameStart = int(i*stepFloat)
    return (np.array(approximation), indices)
    
    
def to_ekvi_PAA(x,y,bins=None):
    '''
    This method perform PAA (see above) on y data set, but it will consider
    different time steps between values (in x data set) and return corrected data set
    '''
    
    if isinstance(x, list):
        x = np.array(x)
        y = np.array(y)
    if (bins == None):
        bins = len(x)
    
    if not len(x) == len(y):
        raise Exception("X and Y have no same length")    
                
    n = len(x)
    x_beg= x.min()
    x_end= x.max()
    x_width = x_end-x_beg
    frame_len = int(math.ceil(x_width/float(bins)))
    x_aprox = []
    y_aprox = []
    i = 0
    frame_num = 1
    x_frame_sum = 0
    y_frame_sum = 0
    items_in_this_frame = 0
    for i in range(n):
        y_frame_sum += y[i]
        x_frame_sum += x[i]
        items_in_this_frame += 1
        if (x[i]>=x_beg+frame_len*frame_num):
            y_aprox.append(y_frame_sum/float(items_in_this_frame))
            x_aprox.append(x_frame_sum/float(items_in_this_frame))
            x_frame_sum = 0
            y_frame_sum = 0
            items_in_this_frame = 0
            frame_num +=1
    return np.array(x),np.array(y)
     
def normalize(x,eps=1e-6):
    """
    Function will normalize an array (give it a mean of 0, and a
    standard deviation of 1) unless it's standard deviation is below
    epsilon, in which case it returns an array of zeros the length
    of the original array.
    """
    
    X = np.asanyarray(x)
    if X.std() < eps:
        return [0 for entry in X]
    return (X-X.mean())/X.std()

def abbe(x,smooth_ratio=0.1):
    '''
    Calculation of Abbe value
    
    @param smooth_ratio: Percent value (from 0 to 1) for smoothing 
    '''
    if smooth_ratio: 
        bins = len(x)*smooth_ratio
        x = to_PAA(x, bins)[0]
    
    x_mean = x.mean()
    n = len(x)
    sum1 = ((x[1:]-x[:-1])**2).sum()
    sum2 = ((x-x_mean)**2).sum()    
    return n/(2*(n-1.0)) * sum1/float(sum2)


def variogram(x,y,bins=None,log_opt=True):
    '''
    Variogram of function shows variability of function in various time steps
    
    @param x: List/array of time values
    @param y: List/array of measured values
    @param bins: Number of values in a variogram
    @param : log_opt: Option if variogram values return in logarithm values
      
    @return: Variogram as two numpy arrays
    '''
    x = to_PAA(x, len(x)*0.7)[0]
    y = to_PAA(y,len(y)*0.7)[0]
    
    sort_opt=True
    n = len(x)
    vario_x = []
    vario_y = []
    for i in range(n):
        for j in range(n):
            if i != j:
                x_val = abs(x[i]-x[j])
                y_val = (y[i]-y[j])**2
                vario_x.append(x_val)
                vario_y.append(y_val)
    vario_x, vario_y = np.array(vario_x), np.array(vario_y)
    if sort_opt: vario_x, vario_y =  sort_pairs(vario_x, vario_y)         
    
    if bins: 
        vario_x = to_PAA(vario_x,bins)[0]
        vario_y = to_PAA(vario_y,bins)[0]
    if log_opt: vario_x, vario_y = np.log10(vario_x), np.log10(vario_y)
    
    return vario_x, vario_y



def histogram(xx,yy,bins_num=None,centred=True,normed=True):
    '''
    @param bins_num: Number of values in histogram
    @param centred: If True values will be shifted (mean value into the zero)
    @param normed: If True values will be normed (according to standart deviation)
    '''
    if (bins_num==None):
        warnings.warn("Number of bins of histogram was not specified. Setting default value (a length of given data")
        bins_num = len(yy)*0.1
    
    #Fix light curve length in case of non equidistant time steps between observations
    
    x = to_ekvi_PAA(xx,yy)[1]
    
    #Center values to zero
    if centred: x = x-x.mean()
    hist, bins = np.histogram(x, bins=bins_num)
    
    #Norm histogram (number of point up or below the mean value)
    if normed: hist = normalize(hist)
    return hist,bins          


def sort_pairs(x,y,rev=False):
    '''Sort two numpy arrays according to the first'''
    
    x = np.array(x)
    y = np.array(y)
    
    indx = x.argsort()
    xx= x[indx]
    yy = y[indx]
    
    if rev: return xx[::-1],yy[::-1]
    
    return xx,yy

def compute_bins(x_time,days_per_bin):
    '''
    Compute number of bins for given time series according to given ratio
    of number of days per one bin
    '''
    
    BORDER_AREA = 5
    
    if (type(x_time) == list):
        x_time = np.array(x_time)
    
    n = len(x_time)
    if (n < BORDER_AREA*5):
        BORDER_AREA = 1
    
      
    time_range = x_time[-BORDER_AREA:].mean() - x_time[:BORDER_AREA].mean()
    num_bins = int(round(time_range/float(days_per_bin)))
    
    if (num_bins < 5):
        warnings.warn("Too low number of bins for given ratio. Setting bin number to minimal default value.")
        num_bins = 5
    
    return num_bins
    
    
def cart_distance(x,y):
    ''' Calculate cartesian distance '''
    
    return np.sqrt(x**2 + y**2)



    

        
    


        