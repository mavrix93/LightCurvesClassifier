'''
Created on Mar 3, 2016

@author: martin
'''
from base_test_class import BaseTestClass
from utils.commons import  args_type, default_values, mandatory_args
from entities.star import Star


class TestQueryValidityCheck(BaseTestClass):
    '''
    This tests checking input validators (decorators)
    '''
        
    def test_type_check(self):
        class Foo(object):
            
            @mandatory_args(("rr"),("a","b","t"),("b","a"))
            @default_values(a=55,d=7)
            @args_type(a=(str,list),b=(float,int),c=Star,d=int)
            def __init__(self,*args,**kwargs):
                self.a = args[0]["a"]
                
   
        
        params = {"a":["dog"],"b":8887.4,"c":Star()}
        self.failUnless(Foo(params).a == params["a"]) 