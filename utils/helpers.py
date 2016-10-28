'''
Created on Apr 12, 2016

@author: Martin Vo
'''
import sys
import matplotlib.pyplot as plt
import os

def checkDepth(a, deep_level):
    lev = 0
    while True:
        try:
            a = a[0]
            lev += 1
        except:
            break
    if not lev == deep_level:
        raise Exception("Wrong input nested level. Excepted %i, got %i\n %s" % (deep_level, lev, a))
        

def unpack_objects(params):
    """
    EXAMPLE:
        unpack_objects({"a":5, "b": [{"aa":55, "bb": AbbeValueFilter(1)}, {"cc": star}]})
            --> {'a': 5, 'b': {'aa': 55, 'bb': {'abbe_lim': 1}}}
    """
 
    if type(params) is dict:
        for key in params:
            value = params[key]
            try:
                params[key] = value.__dict__
                params[key] = unpack_objects(params[key])
            except AttributeError:                
                if type(value) is list:                    
                    params[key] = unpack_objects(value)
                    if len(params[key] ) == 1:
                        params[key] =  params[key][0]
                elif type(value) is dict:
                    params[key] = unpack_objects(value)
                 
    elif type(params) is list:
        for i,value in enumerate(params):
            try:
                params[i] = value.__dict__
                params[i] = unpack_objects(params[i])
            except AttributeError:  
                if type(value) is list: 
                    params[i] = unpack_objects(value)
                    if len(params[i]) == 1:
                        params[i] = params[i][0]
                elif type(value) is dict:
                    params[i] = unpack_objects(value)
    return params
      
    



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