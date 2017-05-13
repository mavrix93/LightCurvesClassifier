#  testresources: extensions to python unittest to allow declaritive use
#  of resources by test cases.
#  Copyright (C) 2005  Robert Collins <robertc@robertcollins.net>
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

import inspect
import unittest


def test_suite():
    import testresources.tests
    return testresources.tests.test_suite()


def split_by_resources(tests):
    """Split a list of tests by the resources that the tests use.

    :return: a dictionary mapping sets of resources to lists of tests
    using that combination of resources.  The dictionary always
    contains an entry for "no resources".
    """
    no_resources = frozenset()
    resource_set_tests = {no_resources: []}
    for test in tests:
        resources = getattr(test, "resources", ())
        all_resources = list(resource.neededResources() for _, resource in  resources)
        resource_set = set()
        for resource_list in all_resources:
            resource_set.update(resource_list)
        resource_set_tests.setdefault(frozenset(resource_set), []).append(test)
    return resource_set_tests


class OptimisingTestSuite(unittest.TestSuite):
    """A resource creation optimising TestSuite."""

    def adsorbSuite(self, test_case_or_suite):
        """Deprecated. Use addTest instead."""
        self.addTest(test_case_or_suite)

    def addTest(self, test_case_or_suite):
        """Add `test_case_or_suite`, unwrapping standard TestSuites.

        This means that any containing unittest.TestSuites will be removed,
        while any custom test suites will be 'distributed' across their
        members. Thus addTest(CustomSuite([a, b])) will result in
        CustomSuite([a]) and CustomSuite([b]) being added to this suite.
        """
        try:
            tests = iter(test_case_or_suite)
        except TypeError:
            unittest.TestSuite.addTest(self, test_case_or_suite)
            return
        if test_case_or_suite.__class__ in (unittest.TestSuite, OptimisingTestSuite):
            for test in tests:
                self.adsorbSuite(test)
        else:
            for test in tests:
                unittest.TestSuite.addTest(
                    self, test_case_or_suite.__class__([test]))

    def cost_of_switching(self, old_resource_set, new_resource_set):
        """Cost of switching from 'old_resource_set' to 'new_resource_set'.

        This is calculated by adding the cost of tearing down unnecessary
        resources to the cost of setting up the newly-needed resources.

        Note that resources which are always dirtied may skew the predicted
        skew the cost of switching because they are considered common, even
        when reusing them may actually be equivalent to a teardown+setup
        operation.
        """
        new_resources = new_resource_set - old_resource_set
        gone_resources = old_resource_set - new_resource_set
        return (sum(resource.setUpCost for resource in new_resources) +
            sum(resource.tearDownCost for resource in gone_resources))

    def switch(self, old_resource_set, new_resource_set, result):
        """Switch from 'old_resource_set' to 'new_resource_set'.

        Tear down resources in old_resource_set that aren't in
        new_resource_set and set up resources that are in new_resource_set but
        not in old_resource_set.

        :param result: TestResult object to report activity on.
        """
        new_resources = new_resource_set - old_resource_set
        old_resources = old_resource_set - new_resource_set
        for resource in old_resources:
            resource.finishedWith(resource._currentResource, result)
        for resource in new_resources:
            resource.getResource(result)

    def run(self, result):
        self.sortTests()
        current_resources = set()
        for test in self._tests:
            if result.shouldStop:
                break
            resources = getattr(test, 'resources', [])
            new_resources = set()
            for name, resource in resources:
                new_resources.update(resource.neededResources())
            self.switch(current_resources, new_resources, result)
            current_resources = new_resources
            test(result)
        self.switch(current_resources, set(), result)
        return result

    def _arrange(self, by_res_comb):
        """Sorts by_res_comb's values using a greedy cost-minimizing
        heuristic.

        by_res_comb maps sets of resources used to a list of the
        corresponding tests.  The heuristic works by figuring out the
        test most expensive to set up and collecting all resource
        sets that contain it.  It will then separately arrange
        this test subset and the set of tests not requiring this
        currently most expensive test.

        The recursion stops when only one (or less) resource set
        is left in by_res_comb.
        """
        if not by_res_comb:
            return []
        if len(by_res_comb)==1:
            return by_res_comb.values()[0]

        most_expensive_here = max(reduce(
                lambda a,b: a.union(b),
                by_res_comb),
            key=lambda res: res.setUpCost)
        
        with_most_expensive, not_handled = {}, {}
        for res_required in by_res_comb:
            if most_expensive_here in res_required:
                with_most_expensive[
                    res_required-frozenset((most_expensive_here,))
                    ] = by_res_comb[res_required]
            else:
                not_handled[res_required] = by_res_comb[res_required]
        
        return self._arrange(with_most_expensive
            )+self._arrange(not_handled)

    def sortTests(self):
        """Sorts _tests in some way that minimizes the total cost
        of creating and deleting resources.

        We're using a heuristic where we attempt to keep the most
        expensive resources unchanged for the longest time.
        """
        resource_set_tests = split_by_resources(self._tests)
        self._tests = self._arrange(resource_set_tests)


class TestLoader(unittest.TestLoader):
    """Custom TestLoader to set the right TestSuite class."""
    suiteClass = OptimisingTestSuite


class TestResource(object):
    """A resource that can be shared across tests.

    Resources can report activity to a TestResult. The methods
     - startCleanResource(resource)
     - stopCleanResource(resource)
     - startMakeResource(resource)
     - stopMakeResource(resource)
    will be looked for and if present invoked before and after cleaning or
    creation of resource objects takes place.

    :cvar resources: The same as the resources list on an instance, the default
        constructor will look for the class instance and copy it. This is a
        convenience to avoid needing to define __init__ solely to alter the
        dependencies list.
    :ivar resources: The resources that this resource needs. Calling
        neededResources will return the closure of this resource and its needed
        resources. The resources list is in the same format as resources on a 
        test case - a list of tuples (attribute_name, resource).
    :ivar setUpCost: The relative cost to construct a resource of this type.
         One good approach is to set this to the number of seconds it normally
         takes to set up the resource.
    :ivar tearDownCost: The relative cost to tear down a resource of this
         type. One good approach is to set this to the number of seconds it
         normally takes to tear down the resource.
    """

    setUpCost = 1
    tearDownCost = 1

    def __init__(self):
        """Create a TestResource object."""
        self._dirty = False
        self._uses = 0
        self._currentResource = None
        self.resources = list(getattr(self.__class__, "resources", []))

    def _call_result_method_if_exists(self, result, methodname, *args):
        """Call a method on a TestResult that may exist."""
        method = getattr(result, methodname, None)
        if callable(method):
            method(*args)

    def _clean_all(self, resource, result):
        """Clean the dependencies from resource, and then resource itself."""
        self._call_result_method_if_exists(result, "startCleanResource", self)
        self.clean(resource)
        for name, manager in self.resources:
            manager.finishedWith(getattr(self, name))
        self._call_result_method_if_exists(result, "stopCleanResource", self)

    def clean(self, resource):
        """Override this to class method to hook into resource removal."""

    def dirtied(self, resource):
        """Mark the resource as having been 'dirtied'.

        A resource is dirty when it is no longer suitable for use by other
        tests.

        e.g. a shared database that has had rows changed.
        """
        self._dirty = True

    def finishedWith(self, resource, result=None):
        """Indicate that 'resource' has one less user.

        If there are no more registered users of 'resource' then we trigger
        the `clean` hook, which should do any resource-specific
        cleanup.

        :param resource: A resource returned by `TestResource.getResource`.
        :param result: An optional TestResult to report resource changes to.
        """
        self._uses -= 1
        if self._uses == 0:
            self._clean_all(resource, result)
            self._setResource(None)

    def getResource(self, result=None):
        """Get the resource for this class and record that it's being used.

        The resource is constructed using the `make` hook.

        Once done with the resource, pass it to `finishedWith` to indicated
        that it is no longer needed.
        :param result: An optional TestResult to report resource changes to.
        """
        if self._uses == 0:
            self._setResource(self._make_all(result))
        elif self.isDirty():
            self._setResource(self.reset(self._currentResource, result))
        self._uses += 1
        return self._currentResource

    def isDirty(self):
        """Return True if this managers cached resource is dirty.
        
        Calling when the resource is not currently held has undefined
        behaviour.
        """
        if self._dirty:
            return True
        for name, mgr in self.resources:
            if mgr.isDirty():
                return True
            res = mgr.getResource()
            try:
                if res is not getattr(self, name):
                    return True
            finally:
                mgr.finishedWith(res)

    def _make_all(self, result):
        """Make the dependencies of this resource and this resource."""
        self._call_result_method_if_exists(result, "startMakeResource", self)
        dependency_resources = {}
        for name, resource in self.resources:
            dependency_resources[name] = resource.getResource()
        resource = self.make(dependency_resources)
        for name, value in dependency_resources.items():
            setattr(self, name, value)
        self._call_result_method_if_exists(result, "stopMakeResource", self)
        return resource

    def make(self, dependency_resources):
        """Override this to construct resources.
        
        :param dependency_resources: A dict mapping name -> resource instance
            for the resources specified as dependencies.
        """
        raise NotImplementedError(
            "Override make to construct resources.")

    def neededResources(self):
        """Return the resources needed for this resource, including self.
        
        :return: A list of needed resources, in topological deepest-first
            order.
        """
        seen = set([self])
        result = []
        for name, resource in self.resources:
            for resource in resource.neededResources():
                if resource in seen:
                    continue
                seen.add(resource)
                result.append(resource)
        result.append(self)
        return result

    def reset(self, old_resource, result=None):
        """Overridable method to return a clean version of old_resource.

        By default, the resource will be cleaned then remade if it had
        previously been `dirtied`. 

        This function needs to take the dependent resource stack into
        consideration as _make_all and _clean_all do.

        :return: The new resource.
        :param result: An optional TestResult to report resource changes to.
        """
        if self._dirty:
            self._clean_all(old_resource, result)
            resource = self._make_all(result)
        else:
            resource = old_resource
        return resource

    def _setResource(self, new_resource):
        """Set the current resource to a new value."""
        self._currentResource = new_resource
        self._dirty = False


class ResourcedTestCase(unittest.TestCase):
    """A TestCase parent or utility that enables cross-test resource usage.

    :ivar resources: A list of (name, resource) pairs, where 'resource' is a
        subclass of `TestResource` and 'name' is the name of the attribute
        that the resource should be stored on.
    """

    resources = []

    def __get_result(self):
        # unittest hides the result. This forces us to look up the stack.
        # The result is passed to a run() or a __call__ method 4 or more frames
        # up: that method is what calls setUp and tearDown, and they call their
        # parent setUp etc. Its not guaranteed that the parameter to run will
        # be calls result as its not required to be a keyword parameter in 
        # TestCase. However, in practice, this works.
        stack = inspect.stack()
        for frame in stack[3:]:
            if frame[3] in ('run', '__call__'):
                # Not all frames called 'run' will be unittest. It could be a
                # reactor in trial, for instance.
                result = frame[0].f_locals.get('result')
                if (result is not None and
                    getattr(result, 'startTest', None) is not None):
                    return result

    def setUp(self):
        unittest.TestCase.setUp(self)
        self.setUpResources()

    def setUpResources(self):
        """Set up any resources that this test needs."""
        result = self.__get_result()
        for resource in self.resources:
            setattr(self, resource[0], resource[1].getResource(result))

    def tearDown(self):
        self.tearDownResources()
        unittest.TestCase.tearDown(self)

    def tearDownResources(self):
        """Tear down any resources that this test declares."""
        result = self.__get_result()
        for resource in self.resources:
            resource[1].finishedWith(getattr(self, resource[0]), result)
            delattr(self, resource[0])


# vim:sta:et:sw=4
