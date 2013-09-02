import numpy as np

import nengo
import nengo.old_api as nef
from nengo.tests.helpers import SimulatorTestCase, unittest


class TestModel(SimulatorTestCase):

    def test_counters(self):
        params = dict(simulator=self.Simulator, seed=123, dt=0.001)

        # Old API
        net = nef.Network('test_counters', **params)
        t_probe = net._raw_probe(net.model.t, dt_sample=.001)
        steps_probe = net._raw_probe(net.model.steps, dt_sample=.001)
        net.run(0.003)
        t_data = t_probe.get_data()
        steps_data = steps_probe.get_data()
        self.assertTrue(np.allclose(t_data.flatten(), [.001, .002, .003]))
        self.assertTrue(np.allclose(steps_data.flatten(), [1, 2, 3]))

        # New API
        m = nengo.Model('test_counters', **params)
        # m.probe(m.t)  # Automatically probed
        # m.probe(m.steps)  # Automatically probed
        m.run(0.003)
        self.assertTrue(np.allclose(m.data[m.t].flatten(),
                                    [.001, .002, .003]))
        self.assertTrue(np.allclose(m.data[m.steps].flatten(), [1, 2, 3]))


if __name__ == "__main__":
    nengo.log_to_file('log.txt', debug=True)
    unittest.main()
