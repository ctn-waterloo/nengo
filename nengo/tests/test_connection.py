import gc
import logging

import numpy as np
import pytest

import nengo
from nengo.helpers import piecewise
from nengo.tests.helpers import Plotter

logger = logging.getLogger(__name__)


def test_args(nl):
    N = 10
    d1, d2 = 3, 2

    nengo.Model('test_args')
    A = nengo.Ensemble(nl(N), dimensions=d1)
    B = nengo.Ensemble(nl(N), dimensions=d2)
    nengo.Connection(
        A, B,
        eval_points=np.random.normal(size=(500, d1)),
        filter=0.01,
        function=np.sin,
        transform=np.random.normal(size=(d2, d1)))


def test_node_to_neurons(Simulator, nl_nodirect):
    name = 'node_to_neurons'
    N = 30

    m = nengo.Model(name, seed=123)
    a = nengo.Ensemble(nl_nodirect(N), dimensions=1)
    inn = nengo.Node(output=np.sin)
    inh = nengo.Node(piecewise({0: 0, 2.5: 1}))
    nengo.Connection(inn, a)
    nengo.Connection(inh, a.neurons, transform=[[-2.5]]*N)

    inn_p = nengo.Probe(inn, 'output')
    a_p = nengo.Probe(a, 'decoded_output', filter=0.1)
    inh_p = nengo.Probe(inh, 'output')

    sim = Simulator(m)
    sim.run(5.0)
    t = sim.trange()
    ideal = np.sin(t)
    ideal[t >= 2.5] = 0

    with Plotter(Simulator, nl_nodirect) as plt:
        plt.plot(t, sim.data(inn_p), label='Input')
        plt.plot(t, sim.data(a_p), label='Neuron approx, filter=0.1')
        plt.plot(t, sim.data(inh_p), label='Inhib signal')
        plt.plot(t, ideal, label='Ideal output')
        plt.legend(loc=0, prop={'size': 10})
        plt.savefig('test_connection.test_' + name + '.pdf')
        plt.close()

    assert np.allclose(sim.data(a_p)[-10:], 0, atol=.1, rtol=.01)


def test_ensemble_to_neurons(Simulator, nl_nodirect):
    name = 'ensemble_to_neurons'
    N = 30

    m = nengo.Model(name, seed=123)
    a = nengo.Ensemble(nl_nodirect(N), dimensions=1)
    b = nengo.Ensemble(nl_nodirect(N), dimensions=1)
    inn = nengo.Node(output=np.sin)
    inh = nengo.Node(piecewise({0: 0, 2.5: 1}))
    nengo.Connection(inn, a)
    nengo.Connection(inh, b)
    nengo.Connection(b, a.neurons, transform=[[-2.5]]*N)

    inn_p = nengo.Probe(inn, 'output')
    a_p = nengo.Probe(a, 'decoded_output', filter=0.1)
    b_p = nengo.Probe(b, 'decoded_output', filter=0.1)
    inh_p = nengo.Probe(inh, 'output')

    sim = Simulator(m)
    sim.run(5.0)
    t = sim.trange()
    ideal = np.sin(t)
    ideal[t >= 2.5] = 0

    with Plotter(Simulator, nl_nodirect) as plt:
        plt.plot(t, sim.data(inn_p), label='Input')
        plt.plot(t, sim.data(a_p), label='Neuron approx, pstc=0.1')
        plt.plot(
            t, sim.data(b_p), label='Neuron approx of inhib sig, pstc=0.1')
        plt.plot(t, sim.data(inh_p), label='Inhib signal')
        plt.plot(t, ideal, label='Ideal output')
        plt.legend(loc=0, prop={'size': 10})
        plt.savefig('test_connection.test_' + name + '.pdf')
        plt.close()

    assert np.allclose(sim.data(a_p)[-10:], 0, atol=.1, rtol=.01)
    assert np.allclose(sim.data(b_p)[-10:], 1, atol=.1, rtol=.01)


def test_neurons_to_ensemble(Simulator, nl_nodirect):
    name = 'neurons_to_ensemble'
    N = 20

    m = nengo.Model(name, seed=123)
    a = nengo.Ensemble(nl_nodirect(N * 2), dimensions=2)
    b = nengo.Ensemble(nl_nodirect(N * 3), dimensions=3)
    c = nengo.Ensemble(nl_nodirect(N), dimensions=N*2)
    nengo.Connection(a.neurons, b, transform=-10 * np.ones((3, N*2)))
    nengo.Connection(a.neurons, c)

    a_p = nengo.Probe(a, 'decoded_output', filter=0.01)
    b_p = nengo.Probe(b, 'decoded_output', filter=0.01)
    c_p = nengo.Probe(c, 'decoded_output', filter=0.01)

    sim = Simulator(m)
    sim.run(5.0)
    t = sim.trange()

    with Plotter(Simulator, nl_nodirect) as plt:
        plt.plot(t, sim.data(a_p), label='A')
        plt.plot(t, sim.data(b_p), label='B')
        plt.plot(t, sim.data(c_p), label='C')
        plt.savefig('test_connection.test_' + name + '.pdf')
        plt.close()

    assert np.all(sim.data(b_p)[-10:] < 0)


def test_neurons_to_node(Simulator, nl_nodirect):
    name = 'neurons_to_node'
    N = 30

    m = nengo.Model(name, seed=123)
    a = nengo.Ensemble(nl_nodirect(N), dimensions=1)
    out = nengo.Node(lambda t, x: x, size_in=N)
    nengo.Connection(a.neurons, out, filter=None)

    a_spikes = nengo.Probe(a, 'spikes')
    out_p = nengo.Probe(out, 'output')

    sim = Simulator(m)
    sim.run(0.6)
    t = sim.trange()

    with Plotter(Simulator, nl_nodirect) as plt:
        ax = plt.subplot(111)
        try:
            from nengo.matplotlib import rasterplot
            rasterplot(t, sim.data(a_spikes), ax=ax)
            rasterplot(t, sim.data(out_p), ax=ax)
        except ImportError:
            pass
        plt.savefig('test_connection.test_' + name + '.pdf')
        plt.close()

    assert np.allclose(sim.data(a_spikes)[:-1], sim.data(out_p)[1:])


def test_neurons_to_neurons(Simulator, nl_nodirect):
    name = 'neurons_to_neurons'
    N1, N2 = 30, 50

    m = nengo.Model(name, seed=123)
    a = nengo.Ensemble(nl_nodirect(N1), dimensions=1)
    b = nengo.Ensemble(nl_nodirect(N2), dimensions=1)
    inp = nengo.Node(output=1)
    nengo.Connection(inp, a)
    nengo.Connection(a.neurons, b.neurons, transform=-1 * np.ones((N2, N1)))

    inp_p = nengo.Probe(inp, 'output')
    a_p = nengo.Probe(a, 'decoded_output', filter=0.1)
    b_p = nengo.Probe(b, 'decoded_output', filter=0.1)

    sim = Simulator(m)
    sim.run(5.0)
    t = sim.trange()

    with Plotter(Simulator, nl_nodirect) as plt:
        plt.plot(t, sim.data(inp_p), label='Input')
        plt.plot(t, sim.data(a_p), label='A, represents input')
        plt.plot(t, sim.data(b_p), label='B, should be 0')
        plt.legend(loc=0, prop={'size': 10})
        plt.savefig('test_connection.test_' + name + '.pdf')
        plt.close()

    assert np.allclose(sim.data(a_p)[-10:], 1, atol=.1, rtol=.01)
    assert np.allclose(sim.data(b_p)[-10:], 0, atol=.1, rtol=.01)


def test_dimensionality_errors(nl_nodirect):
    nengo.Model("test_dimensionality_error", seed=0)
    N = 10

    n01 = nengo.Node(output=[1])
    n02 = nengo.Node(output=[1, 1])
    n21 = nengo.Node(output=[1], size_in=2)
    e1 = nengo.Ensemble(nl_nodirect(N), 1)
    e2 = nengo.Ensemble(nl_nodirect(N), 2)

    # these should work
    nengo.Connection(n01, e1)
    nengo.Connection(n02, e2)
    nengo.Connection(e2, n21)
    nengo.Connection(n21, e1)
    nengo.Connection(e1.neurons, n21, transform=np.random.randn(2, N))
    nengo.Connection(e2, e1, function=lambda x: x[0])

    # these should not work
    with pytest.raises(ValueError):
        nengo.Connection(n02, e1)
    with pytest.raises(ValueError):
        nengo.Connection(e1, e2)
    with pytest.raises(ValueError):
        nengo.Connection(e2.neurons, e1, transform=np.random.randn(1, N+1))
    with pytest.raises(ValueError):
        nengo.Connection(e2.neurons, e1, transform=np.random.randn(2, N))
    with pytest.raises(ValueError):
        nengo.Connection(e2, e1, function=lambda x: x, transform=[[1]])
    with pytest.raises(ValueError):
        nengo.Connection(n21, e2, transform=np.ones((2, 2)))


def test_nested_labels():
    e1 = nengo.Ensemble(nengo.LIF(10), 1, label='1')
    e2 = nengo.Ensemble(nengo.LIF(10), 1, label='2')
    c = nengo.Connection(e1, e2)
    assert c.label == '1>2'

    e1_1 = nengo.Ensemble(nengo.LIF(10), 1, label='1.1')
    c = nengo.Connection(e1, e1_1)
    assert c.label == '1>1.1'

    e1_2 = nengo.Ensemble(nengo.LIF(10), 1, label='1.2')
    c = nengo.Connection(e1_1, e1_2)
    assert c.label == '1/1>2'

    e2_1 = nengo.Ensemble(nengo.LIF(10), 1, label='2.1')
    c = nengo.Connection(e1_1, e2_1)
    assert c.label == '1.1>2.1'

    e1_1_1 = nengo.Ensemble(nengo.LIF(10), 1, label='1.1.1')
    c = nengo.Connection(e1_1, e1_1_1)
    assert c.label == '1/1>1.1'

    e1_1_2 = nengo.Ensemble(nengo.LIF(10), 1, label='1.1.2')
    c = nengo.Connection(e1_1_1, e1_1_2)
    assert c.label == '1.1/1>2'


def test_different_models():
    m1 = nengo.Model('1', set_context=False)
    m2 = nengo.Model('2', set_context=False)
    e1 = nengo.Ensemble(nengo.LIF(10), 1, model=m1)
    e2 = nengo.Ensemble(nengo.LIF(10), 1, model=m2)
    with pytest.raises(ValueError) as e:
        nengo.Connection(e1, e2)
    assert "Cannot connect two objects in different models." in str(e.value)


def test_deleted_model():
    m1 = nengo.Model('1', set_context=False)
    e1 = nengo.Ensemble(nengo.LIF(10), 1, model=m1)
    e2 = nengo.Ensemble(nengo.LIF(10), 1, model=m1)
    del m1
    gc.collect()
    with pytest.raises(ValueError) as e:
        nengo.Connection(e1, e2)
    assert "model that has been deleted" in str(e.value)


if __name__ == "__main__":
    nengo.log(debug=True)
    pytest.main([__file__, '-v'])
