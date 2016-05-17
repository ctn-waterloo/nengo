from copy import copy
import warnings

import numpy as np
import pytest

import nengo
from nengo.exceptions import NetworkContextError, NotAddedToNetworkWarning
from nengo.params import params
from nengo.utils.compat import is_array_like, pickle
from nengo.utils.testing import warns


@pytest.fixture(scope='module', autouse=True)
def error_on_not_added_to_network_warning(request):
    catcher = warnings.catch_warnings(record=True)
    catcher.__enter__()
    warnings.simplefilter(
        'error', category=NotAddedToNetworkWarning)
    request.addfinalizer(lambda: catcher.__exit__(None, None, None))


def assert_is_copy(cp, original):
    assert cp is not original  # ensures separate parameters
    for param in params(cp):
        param_inst = getattr(cp, param)
        if isinstance(param_inst, nengo.solvers.Solver) or isinstance(
                param_inst, nengo.base.NengoObject):
            assert param_inst is getattr(original, param)
        elif is_array_like(param_inst):
            assert np.all(param_inst == getattr(original, param))
        else:
            assert param_inst == getattr(original, param)


def assert_is_deepcopy(cp, original):
    assert cp is not original  # ensures separate parameters
    for param in params(cp):
        param_inst = getattr(cp, param)
        if isinstance(param_inst, nengo.solvers.Solver) or isinstance(
                param_inst, nengo.base.NengoObject):
            assert_is_copy(param_inst, getattr(original, param))
        elif is_array_like(param_inst):
            assert np.all(param_inst == getattr(original, param))
        else:
            assert param_inst == getattr(original, param)


class CopyTest(object):
    def create_original(self):
        raise NotImplementedError()

    def assert_is_copy(self, cp, original):
        assert_is_copy(cp, original)

    def test_copy_in_network(self):
        original = self.create_original()

        with nengo.Network() as model:
            cp = original.copy(add_to_container=True)
        assert cp in model.all_objects

        self.assert_is_copy(cp, original)

    def test_copy_in_network_without_adding(self):
        original = self.create_original()

        with nengo.Network() as model:
            cp = original.copy(add_to_container=False)
        assert cp not in model.all_objects

        self.assert_is_copy(cp, original)

    def test_copy_outside_network(self):
        original = self.create_original()
        with pytest.raises(NetworkContextError):
            original.copy(add_to_container=True)

    def test_copy_outside_network_without_adding(self):
        original = self.create_original()
        cp = original.copy(add_to_container=False)
        self.assert_is_copy(cp, original)

    def test_python_copy_warns_about_adding_to_network(self):
        original = self.create_original()
        copy(original)  # Fine because not in a network
        with nengo.Network():
            with warns(NotAddedToNetworkWarning):
                copy(original)


class PickleTest(object):
    def create_original(self):
        raise NotImplementedError()

    def assert_is_unpickled(self, cp, original):
        assert_is_deepcopy(cp, original)

    def test_pickle_roundtrip(self):
        original = self.create_original()
        cp = pickle.loads(pickle.dumps(original))
        self.assert_is_unpickled(cp, original)

    def test_unpickling_warning_in_network(self):
        original = self.create_original()
        pkl = pickle.dumps(original)
        with nengo.Network():
            with warns(NotAddedToNetworkWarning):
                pickle.loads(pkl)


class TestCopyEnsemble(CopyTest, PickleTest):
    def create_original(self):
        with nengo.Network():
            e = nengo.Ensemble(10, 1, radius=2.)
        return e

    def test_neurons_reference_copy(self):
        original = self.create_original()
        cp = original.copy(add_to_container=False)
        assert original.neurons.ensemble is original
        assert cp.neurons.ensemble is cp


class TestCopyProbe(CopyTest, PickleTest):
    def create_original(self):
        with nengo.Network():
            e = nengo.Ensemble(10, 1)
            p = nengo.Probe(e, synapse=0.01)
        return p


class TestCopyNode(CopyTest, PickleTest):
    def create_original(self):
        with nengo.Network():
            n = nengo.Node(np.min, size_in=2, size_out=2)
        return n


class TestCopyConnection(CopyTest, PickleTest):
    def create_original(self):
        with nengo.Network():
            e1 = nengo.Ensemble(10, 1)
            e2 = nengo.Ensemble(10, 1)
            c = nengo.Connection(e1, e2, transform=2.)
        return c


class TestCopyNetwork(CopyTest, PickleTest):
    def create_original(self):
        with nengo.Network() as model:
            e1 = nengo.Ensemble(10, 1)
            e2 = nengo.Ensemble(10, 1)
            nengo.Connection(e1, e2, transform=2.)
            nengo.Probe(e2)
        return model

    def assert_is_copy(self, cp, original):
        assert_is_deepcopy(cp, original)

    def test_copy_in_network_default_add(self):
        original = self.create_original()

        with nengo.Network() as model:
            cp = original.copy()
        assert cp in model.all_objects

        self.assert_is_copy(cp, original)

    def test_copy_outside_network_default_add(self):
        original = self.create_original()
        cp = original.copy()
        self.assert_is_copy(cp, original)

    def test_network_copy_allows_independent_manipulation(self):
        with nengo.Network() as original:
            nengo.Ensemble(10, 1)
        original.config[nengo.Ensemble].radius = 1.

        cp = original.copy()
        with cp:
            e2 = nengo.Ensemble(10, 1)
        cp.config[nengo.Ensemble].radius = 2.

        assert e2 not in original.ensembles
        assert original.config[nengo.Ensemble].radius == 1.

    def test_copies_structure(self):
        with nengo.Network() as original:
            e1 = nengo.Ensemble(10, 1)
            e2 = nengo.Ensemble(10, 1)
            nengo.Connection(e1, e2)
            nengo.Probe(e2)

        cp = original.copy()

        assert cp.connections[0].pre is not e1
        assert cp.connections[0].post is not e2
        assert cp.connections[0].pre in cp.ensembles
        assert cp.connections[0].post in cp.ensembles

        assert cp.probes[0].target is not e2
        assert cp.probes[0].target in cp.ensembles

    def test_network_copy_builds(self, RefSimulator):
        RefSimulator(self.create_original().copy())


@pytest.mark.parametrize('original', [
    nengo.learning_rules.PES(),
    nengo.learning_rules.BCM(),
    nengo.learning_rules.Oja(),
    nengo.learning_rules.Voja(),
    nengo.processes.WhiteNoise(),
    nengo.processes.FilteredNoise(),
    nengo.processes.BrownNoise(),
    nengo.processes.PresentInput([.1, .2], 1.),
    nengo.synapses.LinearFilter([.1, .2], [.3, .4], True),
    nengo.synapses.Lowpass(0.005),
    nengo.synapses.Alpha(0.005),
    nengo.synapses.Triangle(0.005),
    ])
class TestFrozenObjectCopies(object):
    def test_copy(self, original):
        assert_is_copy(copy(original), original)

    def test_pickle_roundtrip(self, original):
        assert_is_deepcopy(pickle.loads(pickle.dumps(original)), original)
