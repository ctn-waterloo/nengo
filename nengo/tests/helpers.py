try:
    # For Python <=2.6
    import unittest2 as unittest
except ImportError:
    import unittest
import os
import os.path
import sys

try:
    # For Python >=3.3
    from unittest.mock import Mock
except:
    from mock import Mock

import numpy as np

import nengo.simulator

simulators = (nengo.simulator.Simulator,)


class Plotter(object):
    plot = int(os.getenv("NENGO_TEST_PLOT", 0))

    def __init__(self, simulator):
        self.dirname = simulator.__module__ + ".plots"

    def __enter__(self):
        if self.plot:
            import matplotlib.pyplot as plt
            self.plt = plt
            if not os.path.exists(self.dirname):
                os.mkdir(self.dirname)
            # Patch savefig
            self.oldsavefig = self.plt.savefig
            self.plt.savefig = self.savefig
        else:
            self.plt = Mock()
        return self.plt

    def __exit__(self, type, value, traceback):
        if self.plot:
            self.plt.savefig = self.oldsavefig

    def savefig(self, fname, **kwargs):
        if self.plot:
            return self.oldsavefig(os.path.join(self.dirname, fname), **kwargs)


def rmse(a, b):
    return np.sqrt(np.mean((a - b) ** 2))


# Inspired by Xavier Decoret's post: http://stackoverflow.com/a/4455312
def simulates(f, simulators=simulators):
    setattr(f, "simulators", getattr(f, "simulators", ()) + simulators)
    return f


class SimulatesMetaclass(type):
    def __new__(meta, name, bases, dict):
        for methodname, method in dict.items():
            if hasattr(method, "simulators"):
                dict.pop(methodname)
                simulators = getattr(method, "simulators")
                delattr(method, "simulators")
                for simulator in simulators:
                    def method_for_sim(self, method=method, sim=simulator):
                        method(self, sim)
                    methodname_for_sim = methodname + "(" + str(simulator) + ")"
                    dict[methodname_for_sim] = method_for_sim
        return type.__new__(meta, name, bases, dict)


simulator_test_cases = []

class AddToTestCaseRegistry(type):
    def __new__(meta, name, bases, dct):

        # -- help devs out by verifying that this
        #    class will automatically be created by typing
        #    import nengo.tests
        if dct['__module__'] not in nengo.tests.simulator_test_case_mods:
            print >> sys.stderr, ("Module %s has not been included in the"
                " nengo.tests.simulator_test_case_mods registry, so it's"
                " tests won't be run automatically for external simulators")

        # -- create the TestCase class
        rval = type.__new__(meta, name, bases, dct)

        # -- add it to the registry (optionally)
        if dct.get('simulator_test_case_ignore', False):
            pass
        elif 'SimulatorTestCase' not in globals():
            # -- don't add the superclass to the registry
            assert name == 'SimulatorTestCase'
        else:
            simulator_test_cases.append(rval)

        # -- return the original class which is identical to what it
        #    would have been without this metaclass
        return rval


class SimulatorTestCase(object):
    """
    Base class for TestCase classes that use self.Simulator(m)
    to produce a simulator for Model `m`.

    There are many such test classes (TODO: add them to class registry).

    External projects that wish to run all SimulatorTestCase subclasses
    as unit tests using a different simulator can achieve that result by
    including the following sort of code among their own unit tests:

    .. code-block:: python

        for TestCase in simulator_test_cases:
            class MyTestCase(TestCase):
                simulator_test_case_ignore = True
                def Simulator(self, model):
                    return MySimulator(model)
            MyTestCase.__name__ = TestCase.__name__
            globals()[TestCase.__name__] = MyTestCase
            del MyTestCase
            del TestCase


    The way this works is that SimulatorTestCase provides a default Simulator
    method, which is then used by the TestCase suite.

    Other projects can borrow the entire TestCaseSuite, and create a new class
    for each one in the original suite. They override the Simulator method in
    each one of these new classes, and thereby create a full test suite
    tailored to use a custom simulator.

    """
    # -- hack to build TestCase registry
    __metaclass__ = AddToTestCaseRegistry

    def Simulator(self, model):
        return nengo.simulator.Simulator(model)

