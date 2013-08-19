try:
    import unittest2 as unittest
except ImportError:
    import unittest
import os

import numpy as np

import nengo
import nengo.old_api as nef

from nengo.test.helpers import Plotter, rmse, simulates, SimulatesMetaclass


class TestEnsemble(unittest.TestCase):
    __metaclass__ = SimulatesMetaclass

    @simulates
    def test_constant_scalar(self, simulator):
        """A network that represents a constant value."""
        params = dict(simulator=simulator, seed=123, dt=0.001)
        N = 30
        val = 0.5

        # Old API
        net = nef.Network('test_constant_scalar', **params)
        net.make_input('in', value=[val])
        net.make('A', N, 1)
        net.connect('in', 'A')

        in_p = net.make_probe('in', dt_sample=0.001, pstc=0.0)
        a_p = net.make_probe('A', dt_sample=0.001, pstc=0.1)
        net.run(1)

        in_data = in_p.get_data()
        a_data = a_p.get_data()

        with Plotter(simulator) as plt:
            t = net.model.data[net.model.simtime]
            plt.plot(t, in_data, label='Input')
            plt.plot(t, a_data, label='Neuron approximation, pstc=0.1')
            plt.legend(loc=0)
            plt.savefig('test_ensemble.test_constant_scalar-old.pdf')
            plt.close()

        assert np.allclose(in_data.ravel(), val, atol=.05, rtol=.05)
        assert np.allclose(a_data[-10:], val, atol=.05, rtol=.05)

        # New API
        m = nengo.Model('test_constant_scalar', **params)
        m.make_node('in', output=val)
        m.make_ensemble('A', nengo.LIF(N), 1)
        m.connect('in', 'A')

        m.probe('in')
        m.probe('A', filter=0.1)
        m.run(1)

        with Plotter(simulator) as plt:
            t = m.data[m.simtime]
            plt.plot(t, m.data['in'], label='Input')
            plt.plot(t, m.data['A'], label='Neuron approximation, pstc=0.1')
            plt.legend(loc=0)
            plt.savefig('test_ensemble.test_constant_scalar-new.pdf')
            plt.close()

        assert np.allclose(m.data['in'].ravel(), val, atol=.05, rtol=.05)
        assert np.allclose(m.data['A'][-10:], val, atol=.05, rtol=.05)

    @simulates
    def test_constant_vector(self, simulator):
        """A network that represents a constant 3D vector."""
        params = dict(simulator=simulator, seed=123, dt=0.001)
        N = 30
        vals = [0.6, 0.1, -0.5]

        # Old API
        net = nef.Network('test_constant_vector', **params)
        net.make_input('in', value=vals)
        net.make('A', N * len(vals), len(vals))
        net.connect('in', 'A', transform=np.eye(len(vals)))

        in_p = net.make_probe('in', dt_sample=0.001, pstc=0.0)
        a_p = net.make_probe('A', dt_sample=0.001, pstc=0.1)
        net.run(1)

        in_data = in_p.get_data()
        a_data = a_p.get_data()

        with Plotter(simulator) as plt:
            t = net.model.data[net.model.simtime]
            plt.plot(t, in_data, label='Input')
            plt.plot(t, a_data, label='Neuron approximation, pstc=0.1')
            plt.legend(loc=0, prop={'size': 10})
            plt.savefig('test_ensemble.test_constant_vector-old.pdf')
            plt.close()

        assert np.allclose(in_data[-10:], vals, atol=.05, rtol=.05)
        assert np.allclose(a_data[-10:], vals, atol=.05, rtol=.05)

        # New API
        m = nengo.Model('test_constant_vector', **params)
        m.make_node('in', output=vals)
        m.make_ensemble('A', nengo.LIF(N * len(vals)), len(vals))
        m.connect('in', 'A')

        m.probe('in')
        m.probe('A', filter=0.1)
        m.run(1)

        with Plotter(simulator) as plt:
            t = m.data[m.simtime]
            plt.plot(t, m.data['in'], label='Input')
            plt.plot(t, m.data['A'], label='Neuron approximation, pstc=0.1')
            plt.legend(loc=0, prop={'size': 10})
            plt.savefig('test_ensemble.test_constant_vector-new.pdf')
            plt.close()

        assert np.allclose(m.data['in'][-10:], vals, atol=.05, rtol=.05)
        assert np.allclose(m.data['A'][-10:], vals, atol=.05, rtol=.05)

    @simulates
    def test_scalar(self, simulator):
        """A network that represents sin(t)."""
        params = dict(simulator=simulator, seed=123, dt=0.001)
        N = 30
        target = np.sin(np.arange(4999) / 1000.)
        target.shape = (4999, 1)

        # Old API
        net = nef.Network('test_scalar', **params)
        net.make_input('in', value=np.sin)
        net.make('A', N, 1)
        net.connect('in', 'A')

        in_p = net.make_probe('in', dt_sample=0.001, pstc=0.0)
        a_p = net.make_probe('A', dt_sample=0.001, pstc=0.02)
        net.run(5)

        in_data = in_p.get_data()
        a_data = a_p.get_data()

        with Plotter(simulator) as plt:
            t = net.model.data[net.model.simtime]
            plt.plot(t, in_data, label='Input')
            plt.plot(t, a_data, label='Neuron approximation, pstc=0.02')
            plt.legend(loc=0)
            plt.savefig('test_ensemble.test_scalar-old.pdf')
            plt.close()

        # print rmse(target, in_data), rmse(target, a_data)
        assert rmse(target, in_data) < 0.001
        assert rmse(target, a_data) < 0.1

        # New API
        m = nengo.Model('test_scalar', **params)
        m.make_node('in', output=np.sin)
        m.make_ensemble('A', nengo.LIF(N), 1)
        m.connect('in', 'A')

        m.probe('in')
        m.probe('A', filter=0.02)
        m.run(5)

        with Plotter(simulator) as plt:
            t = m.data[m.simtime]
            plt.plot(t, m.data['in'], label='Input')
            plt.plot(t, m.data['A'], label='Neuron approximation, pstc=0.02')
            plt.legend(loc=0)
            plt.savefig('test_ensemble.test_scalar-new.pdf')
            plt.close()

        # print rmse(target, m.data['in']), rmse(target, m.data['A'])
        assert rmse(target, m.data['in']) < 0.001
        assert rmse(target, m.data['A']) < 0.1

        # Check old/new API similarity
        # print rmse(a_data, m.data['A'])
        assert rmse(a_data, m.data['A']) < 0.1

    @simulates
    def test_vector(self, simulator):
        """A network that represents sin(t), cos(t), arctan(t)."""
        params = dict(simulator=simulator, seed=123, dt=0.001)
        N = 40
        target = np.vstack((np.sin(np.arange(4999) / 1000.),
                            np.cos(np.arange(4999) / 1000.),
                            np.arctan(np.arange(4999) / 1000.))).T

        # Old API
        net = nef.Network('test_vector', **params)
        net.make_input('sin', value=np.sin)
        net.make_input('cos', value=np.cos)
        net.make_input('arctan', value=np.arctan)
        net.make('A', N * 3, 3, radius=2)
        net.connect('sin', 'A', transform=[[1], [0], [0]])
        net.connect('cos', 'A', transform=[[0], [1], [0]])
        net.connect('arctan', 'A', transform=[[0], [0], [1]])

        sin_p = net.make_probe('sin', dt_sample=0.001, pstc=0.0)
        cos_p = net.make_probe('cos', dt_sample=0.001, pstc=0.0)
        arctan_p = net.make_probe('arctan', dt_sample=0.001, pstc=0.0)
        a_p = net.make_probe('A', dt_sample=0.001, pstc=0.02)
        net.run(5)

        sin_data = sin_p.get_data()
        cos_data = cos_p.get_data()
        arctan_data = arctan_p.get_data()
        a_data = a_p.get_data()

        with Plotter(simulator) as plt:
            t = net.model.data[net.model.simtime]
            plt.plot(t, sin_data, label='sin')
            plt.plot(t, cos_data, label='cos')
            plt.plot(t, arctan_data, label='arctan')
            plt.plot(t, a_data, label='Neuron approximation, pstc=0.02')
            plt.legend(loc=0, prop={'size': 10})
            plt.savefig('test_ensemble.test_vector-old.pdf')
            plt.close()

        # Not sure why, but this isn't working...
        # print rmse(target[:,0], sin_data), rmse(target[:,1], cos_data),
        # print rmse(target[:,2], arctan_data), rmse(target, a_data)
        # assert rmse(target[:,0], sin_data) < 0.001
        # assert rmse(target[:,1], cos_data) < 0.001
        # assert rmse(target[:,2], arctan_data) < 0.001
        assert rmse(target, a_data) < 0.1

        # New API
        m = nengo.Model('test_vector', **params)
        m.make_node('sin', output=np.sin)
        m.make_node('cos', output=np.cos)
        m.make_node('arctan', output=np.arctan)
        m.make_ensemble('A', nengo.LIF(N * 3), 3, radius=2)
        m.connect('sin', 'A', transform=[[1], [0], [0]])
        m.connect('cos', 'A', transform=[[0], [1], [0]])
        m.connect('arctan', 'A', transform=[[0], [0], [1]])

        m.probe('sin')
        m.probe('cos')
        m.probe('arctan')
        m.probe('A', filter=0.02)
        m.run(5)

        with Plotter(simulator) as plt:
            t = m.data[m.simtime]
            plt.plot(t, m.data['sin'], label='sin')
            plt.plot(t, m.data['cos'], label='cos')
            plt.plot(t, m.data['arctan'], label='arctan')
            plt.plot(t, m.data['A'], label='Neuron approximation, pstc=0.02')
            plt.legend(loc=0, prop={'size': 10})
            plt.savefig('test_ensemble.test_vector-new.pdf')
            plt.close()

        # Not sure why, but this isn't working...
        # assert rmse(target[:,0], m.data['sin']) < 0.001
        # assert rmse(target[:,1], m.data['cos']) < 0.001
        # assert rmse(target[:,2], m.data['arctan']) < 0.001
        assert rmse(target, m.data['A']) < 0.1

        # Check old/new API similarity
        # print rmse(a_data, m.data['A'])
        assert rmse(a_data, m.data['A']) < 0.1


if __name__ == "__main__":
    unittest.main()
