'''
Created on Feb 22, 2016

@author: Martin Vo
'''
import unittest

class BaseTestClass(unittest.TestCase):
    '''
    Parent class for other test classes
    '''
     
    def failIfRaises(self,functionToExecute,*args):
        failed = False
        try:
            functionToExecute(*args)
            print "This should fail but it did not"
        except:
            failed = True
        self.failUnless(failed)   