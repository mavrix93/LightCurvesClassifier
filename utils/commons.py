'''
Created on Feb 29, 2016

@author: Martin Vo

There are common functions and decorators mainly for query classes
'''

#Throws
from entities.exceptions import MandatoryKeyInQueryDictIsMissing,\
    ArgumentValidationError, InvalidArgumentNumberError, InvalidReturnType
    
from functools import wraps
import functools
   


def args_type(**decls):
    """
    Decorator to check argument types
    
    Usage:  @args_type(name="str",age=(int,float))
            def func(...):
                ...
                
    @param func: Function which arguments should be checked
    """

    def decorator(func):
        code = func.func_code
        fname = func.func_name
        names = code.co_varnames[:code.co_argcount]
        @wraps(func)
        def decorated(*args,**kwargs):
            dict_option = False
            if len(args) >0 and isinstance(args[0], dict):
                kwargs = args[0]
                dict_option = True
            elif len(args) > 1 and isinstance(args[1], dict):
                kwargs = args[1]
                dict_option = True
                
            for argname, argtype in decls.iteritems():
                try:
                    argval = args[names.index(argname)]
                except (ValueError, IndexError):
                    argval = kwargs.get(argname)
                if not argval== None and not isinstance(argval, argtype) :
                    raise TypeError("%s(...): arg '%s': type is %s, must be %s"
                                    % (fname, argname, type(argval), argtype))
            if dict_option:
                return func(args[0],kwargs)
            return func(*args,**kwargs)
                
        return decorated

    return decorator
    

def default_values(**decls):
    """
    Decorator to add default values to certain arguments if missing
    
    Usage:  @default_values(name="Unknown",age=0)
            def func(...):
                ...
                
    @param func: Function which arguments should be treated
    """

    def decorator(func):
        @wraps(func)
        def decorated(*args,**kwargs):
            dict_option = False
            if len(args) >0 and isinstance(args[0], dict):
                kwargs = args[0]
                dict_option = True
            elif len(args) > 1 and isinstance(args[1], dict):
                kwargs = args[1]
                dict_option = True
                
            for argname, arg_default_value in decls.iteritems():
                if not argname in kwargs:
                    kwargs[argname]= arg_default_value

            if dict_option:
                return func(args[0],kwargs)
            return func(*args,**kwargs)
                
        return decorated

    return decorator


def mandatory_args(*args_options):
    """
    Decorator to check presence of mandatory arguments
    
    Usage:  @default_values(("name","age"),("nick_name","sex"))
            def func(...):
                ...
        - Method func have to have variables "name" and "age or "nickname","sex"
                
    @param func: Function which arguments should be treated
                  
    """
    
    if not isinstance(args_options[0], tuple):
        args_options = tuple(args_options)
    
    def decorator(func):        
        @wraps(func)
        def decorated(*args,**kwargs):
            missing_args = []
            dict_option = False
            if len(args) >0 and isinstance(args[0], dict):
                kwargs = args[0]
                dict_option = True
            elif len(args) > 1 and isinstance(args[1], dict):
                kwargs = args[1]
                dict_option = True
                
            for args_option in args_options:
                satisfied = True
                
                for key in args_option:
                    if not key in kwargs:
                        satisfied = False
                        missing_args.append(key)
                        break
                if satisfied:
                    break
                        
            if not satisfied:   
                raise MandatoryKeyInQueryDictIsMissing(missing_args,kwargs)
            

            if dict_option:
                return func(args[0],kwargs)
            return func(*args,**kwargs)
                
        return decorated

    return decorator

def returns(*accepted_return_type_tuple):
    '''
    Validates the return type. Since there's only ever one
    return type, this makes life simpler. Along with the
    accepts() decorator, this also only does a check for
    the top argument. For example you couldn't check
    (<type 'tuple'>, <type 'int'>, <type 'str'>).
    In that case you could only check if it was a tuple.
    '''
    def return_decorator(validate_function):
        # No return type has been specified.
        if len(accepted_return_type_tuple) == 0:
            raise TypeError('You must specify a return type.')
 
        @functools.wraps(validate_function)
        def decorator_wrapper(*function_args):
            # More than one return type has been specified.
            if len(accepted_return_type_tuple) > 1:
                raise TypeError('You must specify one return type.')
 
            # Since the decorator receives a tuple of arguments
            # and the is only ever one object returned, we'll just
            # grab the first parameter.
            accepted_return_type = accepted_return_type_tuple[0]
 
            # We'll execute the function, and
            # take a look at the return type.
            return_value = validate_function(*function_args)
            return_value_type = type(return_value)
 
            if return_value_type is not accepted_return_type:
                raise InvalidReturnType(return_value_type,
                                        validate_function.__name__) 
 
            return return_value
 
        return decorator_wrapper
    return return_decorator


def accepts(*accepted_arg_types):
    '''
    A decorator to validate the parameter types of a given function.
    It is passed a tuple of types. eg. (<type 'tuple'>, <type 'int'>)
 
    Note: It doesn't do a deep check, for example checking through a
          tuple of types. The argument passed must only be types.
    '''
 
    def accept_decorator(validate_function):
        # Check if the number of arguments to the validator
        # function is the same as the arguments provided
        # to the actual function to validate. We don't need
        # to check if the function to validate has the right
        # amount of arguments, as Python will do this
        # automatically (also with a TypeError).
        @functools.wraps(validate_function)
        def decorator_wrapper(*function_args, **function_args_dict):
            #Case of class function where first arg is 'self'
            if len(accepted_arg_types) == len(function_args)-1:
                to_return_args = function_args
                function_args = function_args[1:]
                
            elif len(accepted_arg_types) is not len(function_args):
                raise InvalidArgumentNumberError("Function: %s " %validate_function.__name__)
 
            # We're using enumerate to get the index, so we can pass the
            # argument number with the incorrect type to ArgumentValidationError.
            for arg_num, (actual_arg, accepted_arg_type) in enumerate(zip(function_args, accepted_arg_types)):
                if not type(actual_arg) is accepted_arg_type:
                    raise ArgumentValidationError("Wrong argument: %s" % actual_arg,
                                                  "Name of the function: %s" %validate_function.__name__,
                                                  "Accepted args: %s" % accepted_arg_type)
 
            return validate_function(*to_return_args)
        return decorator_wrapper
    return accept_decorator

      





