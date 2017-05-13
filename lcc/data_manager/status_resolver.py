import ast
import os

from lcc.entities.exceptions import InvalidFilesPath
import numpy as np
from lcc.utils.helpers import sub_dict_in_dict
from lcc.utils.helpers import check_depth


class StatusResolver(object):
    '''
    This class is responsible for status files generated thru systematic searches
    into databases and for reading files of planned queries.

    Attributes
    ----------
    status_header : list
        Column names of status file

    status_queries : list
        Rows of status file
    '''

    NUM_STATUS_INFO = 4  # Number of status info columns +1
    DELIMITER = ";"

    def __init__(self, status_file_path):
        '''
        Parameters
        ----------
        status_file_path : str
            Path to the status file

            FORMAT OF STATUS FILE:
            #first_query_param    second_query_param    other_query_param    found    filtered    passed
            value1    value2    other_value    True/False    True/False    True/False
            ...

            This file is generated automatically during systematic search.
        '''

        self.status_header, self.status_queries = self._readFile(
            status_file_path)

    @classmethod
    def getUnsearchedQuery(self, search_plan_file):
        '''
        Return list of queries which have not been queried yet.

        Parameters
        ----------
        Search_plan_file : str
            Path to the file of planned queries

        Returns
        -------
        list
            List of query dictionaries

        Note
        ----
        FORMAT OF PLAN QUERIES FILE is the same as status file except 3 last
        columns (without found, filtered and passed)
        '''
        plan_header, plan_queries = self._readFile(search_plan_file)

        header_restr = self.status_header[:-self.NUM_STATUS_INFO]
        col_num = len(header_restr)
        queries_restr = np.hsplit(self.status_queries, np.array([col_num]))[0]
        status_dict = self._getDictQuery(header_restr, queries_restr)

        plan_dict = self._getDictQuery(plan_header, plan_queries)

        return self._getDiff(plan_dict, status_dict)

    def getWithStatus(self, stat):
        '''
        Get queries with given query status

        Parameters
        ----------
        stat : dict
            Dictionary with status column name and its value

        Example
        --------
        getStatus({"passed" : True}) --> [{"field":1,"starid":1, "target":"lmc"}, .. , {...}] 

        This example generates all stars which passed thru filtering

        Returns
        -------
        list
            Returns all queries with desired status
        '''

        status_dict = self._getDictQuery(
            self.status_header, self.status_queries)
        return sub_dict_in_dict(stat, status_dict, ["passed", "filtered", "found"])

    def getQueries(self):
        '''
        Get status file as list of queries

        Returns
        -------
        list
            List of dictionary queries
        '''
        return self._getDictQuery(self.status_header, self.status_queries)

    @classmethod
    def save_query(self, query, fi_name="query_file.txt", PATH=".", DELIM=None,
                   overwrite=False):
        '''
        Save queries into the file which can be loaded for another query

        Parameters
        ----------
        query : list
            List of dictionaries which contains query params

        Returns
        -------
            None
        '''

        header = query[0].keys()
        path = os.path.join(PATH, fi_name)

        if not DELIM:
            DELIM = self.DELIMITER

        try:
            if overwrite:
                query_file = open(path, "w+")
            else:
                query_file = open(path, "a+")

        except IOError as err:
            raise InvalidFilesPath(err)

        n = len(header)
        if not query_file.readline().startswith("#"):
            query_file.write("#")
            for i, head in enumerate(header):

                delim = DELIM
                if i >= n - 1:
                    delim = ""

                query_file.write(head + delim)
            query_file.write("\n")

        for que in query:
            if len(que) != len(header):
                raise Exception(
                    "Number of header params and values have to be the same.\nGot query %s and header %s \nCheck the query file if there are no missing value in any column or if there is a whitespace." % (que, header))
            for i, key in enumerate(que):
                delim = DELIM
                if i >= n - 1:
                    delim = ""

                query_file.write(str(que[key]) + delim)
            query_file.write("\n")

        query_file.close()

    @classmethod
    def save_lists_query(self, query=[], fi_name="query_file.txt", PATH=".", DELIM=None,
                         overwrite=False, header=None):
        '''
        Save queries into the file which can be loaded for another query

        Parameters
        ----------
        query : list
            List of lists which contains

        Returns
        -------
            None
        '''

        path = os.path.join(PATH, fi_name)

        if not DELIM:
            DELIM = self.DELIMITER

        if not check_depth(query, 2, ifnotraise=False):
            query = [query]

        if not header and query[0]:
            return False

        try:
            if overwrite:
                query_file = open(path, "w+")
            else:
                query_file = open(path, "a+")

        except IOError as err:
            raise InvalidFilesPath(err)

        if header and not query_file.readline():
            query_file.write(
                "#" + DELIM.join([str(it) for it in header]))

        for line in query:
            query_file.write(DELIM.join([str(it) for it in line]) + "\n")

        query_file.close()

    @staticmethod
    def get_with_status(queries, stat={"passed": True}):
        '''
        Return all queries with desired status

        Parameters
        ----------
        stat : dict
            Dictionary with status column name and its value

        queries : list
            List of query dictionaries

        Returns
        -------
        list
            Returns all queries with desired status
        '''
        return sub_dict_in_dict(stat, queries)

    def _readFile(self, path):
        '''Get header and data from the file'''

        header = self._readHeader(path)

        data = self._getFileData(path)
        # data = np.genfromtxt(path,dtype="|S5", delimiter = self.DELIMITER)
        # data = self._correctData(data, header)

        if len(header) != len(data[0]):
            raise Exception(
                "Number of header params and values have to be the same.\nGot %s and %s" % (data[0], header))
        return header, data

    def _readHeader(self, status_file_path):
        '''Get keys from header in a list'''

        with open(status_file_path, 'r') as f:
            # Skip first symbol ('#') and the  '\n'
            header_line = f.readline()[1:].rstrip('\n')

        return [head.strip() for head in header_line.split(self.DELIMITER)]

    def _getDiff(self, desir_dicts, comp_dicts):
        '''Get dictionaries from list of desir_dicts which is not present list of comp_dicts'''

        diff_dicts = []
        for query in desir_dicts:
            if not query in comp_dicts:
                diff_dicts.append(query)
        return diff_dicts

    def _getDictQuery(self, header, queries):
        '''Get header list and contents of the status file as list of dictionaries'''
        queries_list = []
        for query in queries:
            if type(query) is not np.ndarray and type(query) is not list:
                query = [query]
            queries_list.append(dict(zip(header, query)))
        return queries_list

    def _readInStr(self, words):
        ENUM_SEP = ","
        x = []
        for word in words:
            if ENUM_SEP in str(word):
                x.append(word.split(ENUM_SEP))
            else:
                try:
                    x.append(ast.literal_eval(word.strip()))
                except:
                    x.append(word)

        return x

    def _correctData(self, data, header):
        try:
            len(data[0])
            assert not isinstance(data[0], str)
        except:
            # Check if just one value
            try:
                len(data)
            except:
                return [[data]]

            # One line
            if len(data) == len(header):
                return [data]

            # One column
            else:
                return [[i] for i in data]
        return data

    def _getFileData(self, path):

        fi = open(path)

        data = []
        for line in fi.readlines():
            line = line.strip()

            if not line.startswith("#"):
                parts = line.split(self.DELIMITER)

                parts = self._readInStr(parts)
                data.append(parts)
        fi.close
        return data
