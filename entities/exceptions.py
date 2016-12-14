'''
Created on Mar 2, 2016

@author: Martin Vo
'''

class InvalidFilesPath(IOError):
    pass

class InvalidFile(IOError):
    pass


class QueryInputError(ValueError):
    pass
        
class NoInternetConnection(Exception):
    pass

class MandatoryKeyInQueryDictIsMissing(Exception):
    pass

class FailToParseName(Exception):
    pass

class InvalidFilteringParams(Exception):
    pass


class ArgumentValidationError(Exception):
    pass

class InvalidArgumentNumberError(Exception):
    pass

class InvalidReturnType(Exception):
    pass

class NotFilterTypeClass(Exception):
    pass

class StarAttributeNotSpecified(AttributeError):
    pass

class LearningError(Exception):
    pass

