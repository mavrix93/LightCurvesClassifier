'''
Created on Apr 12, 2016

@author: Martin Vo
'''
import sys
import matplotlib.pyplot as plt
import os

def check_path(path):
    '''
    Correct path if there are more backslashes 
    
    @param path: String path
    
    EXAMPLE:
    "home/ap//bla" --> "home/ap/bla"    
    '''
    
    while True:
        pos = path.find("//")
        if (pos == -1):
            break
        path = path[:pos] + path[pos+1:]
    return path


def subDictInDict(sub_dict, dict_list):
    '''
    Return list of dictionaries which contain condition in sub_dict
    
    @param sub_dict:  Single dictionary
    @param dict_list: List of dictionaries
    
    EXAMPLE:
    subDictInDict({"x":1},[{"x":2,"y":5,..},{"x":1,"z":2,..}, ..} --> [{"x":1, "z":2, ..},..]
    
    In this example list of dictionaries which contain x = 1 is returned
    '''
    
    assert len(sub_dict.keys()) == 1
    
    key = sub_dict.keys()[0]
    matched_dicts = []
    for one_dict in dict_list:
        if str(one_dict[key]) == str(sub_dict[key]):
            matched_dicts.append(one_dict)
    return matched_dicts

#TODO: Get rid of this
def get_borders(xx,yy,Z,lim=0.5):
    cs = plt.contour(xx,yy,Z, [lim])
    p = cs.collections[0].get_paths()[0]
    v = p.vertices
    return v[:,0],v[:,1]



def verbose(txt,verbosity,verb_level=2):
    '''
    @param txt: Message which will be showed
    @param verb_level: Level of verbosity:
        0 - All messages will be showed
        1 - Just messages witch verbosity 1 an 2 will be showed
        2 - Just messages witch verbosity 2 will be showed   
    @param verb_level: Set verbosity level    
    '''
    if verbosity <= verb_level:
        print txt
        

def progressbar(it, prefix = "", size = 60):
    count = len(it)
    
    if count > 0:
        def _show(_i):
            x = int(size*_i/count)
            sys.stdout.write("%s[%s%s] %i/%i\r" % (prefix, "#"*x, "."*(size-x), _i, count))
            sys.stdout.flush()
        
        _show(0)
        for i, item in enumerate(it):
            yield item
            _show(i+1)
        sys.stdout.write("\n")
        sys.stdout.flush()
        
        
def create_folder(path):
    if not os.path.exists(path):
        os.makedirs(path)