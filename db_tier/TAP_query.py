'''
Created on Jan 5, 2016

@author: Martin Vo
'''

from gavo import votable
from base_query import LightCurvesDb
from entities.exceptions import QueryInputError, NoInternetConnection
from gavo.votable.tapquery import RemoteError, WrongStatus, NetworkError
from utils.helpers import verbose
from conf.glo import VERBOSITY

class TapClient(LightCurvesDb):
    '''
    Common class for all TAP db clients
    '''


    #Make tap query        
    def postQuery(self,tap_params):
        '''
        @param tap_params: Tap query parameters (examples below)
        
        @keyword str URL: Url of TAP protocol
        @keyword str table: Name of the table
        @keyword list/str select: Name of columns to retrieve
        @keyword list/tuple conditions: (Name of column, min value, max value)
                 In case of dimension of conditions is 2, the second param will be
                 considered as equal
        '''
        
        #Load tap protocol parameters        
        self.URL = tap_params["URL"]
        self.table = tap_params["table"]
        self.conditions = tap_params["conditions"]
        self.select = tap_params["select"] 
        
        query = self._get_select_text() + self._get_from_text() + self._get_where_text()
        verbose(query,3,VERBOSITY)
        verbose("TAP query is about to start",2,VERBOSITY)
        
        #Run query
        try:
            job = votable.ADQLTAPJob(self.URL, query)
            job.run()
        except RemoteError:
            raise QueryInputError("Wrong TAP query name column/table")
        except WrongStatus:
            raise QueryInputError("Wrong TAP query url")
        except NetworkError:
            raise NoInternetConnection
                    
        retrieve_data = votable.load(job.openResult())[0]
 
        verbose("TAP query is done",2,VERBOSITY) 
        job.delete()
        return retrieve_data
        

    def _get_select_text(self):
        '''Get SELECET part for SQL query'''
        
        if (type(self.select) == list):
            select_text = "SELECT " + ', '.join(map(str,self.select))+ " "
        elif (type(self.select) == str):
            select_text = "SELECT %s " % self.select
        else:
            raise QueryInputError("Select option was not resolved for TAP query")
        return select_text
    
    def _get_from_text(self):
        '''Get GET part for SQL query'''
        
        if (type(self.table) == str):
            return "FROM "+self.table + " "
        raise QueryInputError("Given table name is not string")
    
    def _get_where_text(self):
        '''Get WHERE part for SQL query'''
        
        where_text = "WHERE "
        for condition in self.conditions:
            if (len(condition)==3):            
                where_text += "({0} BETWEEN {1} AND {2}) AND ".format(*condition)
            elif (len(condition)==2):
                where_text += "({0} = {1}) AND ".format(*condition)
            else:
                raise QueryInputError("Unresolved TAP query condition: %s" %condition)
        where_text = where_text[:-4]    
        return where_text
            
