'''
Created on Jul 19, 2016

@author: Martin Vo
'''

import numpy as np
from utils.helpers import check_path, subDictInDict
from entities.exceptions import InvalidFilesPath

class StatusResolver(object):
    '''
    This class is responsible for status files generated thru systematic searches
    into databases and for reading files of planned queries.
    '''
    
    NUM_STATUS_INFO = 4         #Number of status info columns +1


    def __init__(self, status_file_path):
        '''
        @param status_file_path: Path to the status file
        
        FORMAT OF STATUS FILE:
        #first_query_param    second_query_param    other_query_param    found    filtered    passed
        value1    value2    other_value    True/False    True/False    True/False
        ...
        
        This file will be generate automatically during systematic search.
        '''
        
        self.status_header, self.status_queries = self._readFile(status_file_path)

        
    def getUnsearchedQuery(self, search_plan_file):
        '''
        Return list of queries which were not searched according to status file
        and file of planed queries
        
        @param search_plan_file: Path to the file of planned queries
        @return: List of query dictionaries   
        
        FORMAT OF PLAN QUERIES FILE is the same as status file except 3 last
        columns (without found,filtred and passed) 
        '''
        
        plan_header, plan_queries = self._readFile(search_plan_file)

        header_restr = self.status_header[:-self.NUM_STATUS_INFO]
        col_num = len(header_restr)   
        queries_restr =  np.hsplit(self.status_queries,np.array([col_num]))[0]
        status_dict = self._getDictQuery(header_restr,queries_restr)
        
        plan_dict = self._getDictQuery(plan_header, plan_queries)
        
        return self._getDiff(plan_dict, status_dict)
  
  
    def getWithStatus(self,stat):
        '''
        Return all queries with desired status
        
        @param stat: Dictionary with status column name and its value
        
        EXAMPLE:
        
        getStatus({"passed" : True}) --> [{"field":1,"starid":1, "target":"lmc"}, .. , {...}] 
        
        This example generates all stars which passed thru filtering
        '''
        
        status_dict = self._getDictQuery(self.status_header, self.status_queries)
        return subDictInDict( status_dict,stat)
    
    
    def getQueries(self):
        '''
        Get status file as list of queries
        '''        
        return self._getDictQuery(self.status_header, self.status_queries)
    
        
    @staticmethod
    def save_query(query, FI_NAME = "query_file.txt", PATH = ".", DELIM = "\t"):
        '''
        Save queries into the file which can be loaded for another query
        
        @param query: List of dictionaries which contains query params
        '''
        
        header = query[0].keys()
        path = PATH+"/"+FI_NAME
        
        try:
            query_file = open(check_path(path),"w")
        except IOError as err:
            raise InvalidFilesPath(err)
        
        query_file.write("#")
        for head in header:
            query_file.write(head + "\t")
        query_file.write("\n")
        
        for que in query:
            for key in que:
                query_file.write(que[key]+"\t")
            query_file.write("\n")
            
        query_file.close()
        
        
    @staticmethod
    def get_with_status(queries, stat = {"passed": True}):
        '''
        Return all queries with desired status
        
        @param stat: Dictionary with status column name and its value
        @param queries: List of query dictionaries
        '''
        return subDictInDict(queries, stat)
    
    
    def _readFile(self,path):
        '''Get header and data from the file'''
        
        header = self._readHeader(path)
        data = np.genfromtxt(path,dtype="|S5")
        return header, data
    
    
    def _readHeader(self,status_file_path):
        '''Get keys from header in a list'''
        
        with open(status_file_path, 'r') as f:
            header_line = f.readline()[1:].rstrip('\n')    #Skip first symbol ('#') and the  '\n'            
        return header_line.split("\t")
    
        
    def _getDiff(self,desir_dicts, comp_dicts):
        '''Get dictionaries from list of desir_dicts which is not present list of comp_dicts'''
        
        diff_dicts = []
        for query in desir_dicts:
            if not query in comp_dicts:
                diff_dicts.append(query)                
        return diff_dicts
    
    
    def _getDictQuery(self,header,queries):
        '''Get header list and contents of the status file as list of dictionaries'''
        
        queries_list = []
        for query in queries:
            queries_list.append(dict(zip(header,query)))
        return queries_list

    
    



        