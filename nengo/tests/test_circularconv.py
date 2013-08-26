try:
    import unittest2 as unittest
except ImportError:
    import unittest

import numpy as np

import nengo
from nengo.objects import Constant
from nengo.templates.circularconv import CircularConvolution

from helpers import SimulatorTestCase


class TestCircularConv(SimulatorTestCase):
    def _test_cconv(self, D, neurons_per_product):
        # D is dimensionality of semantic pointers

        m = nengo.Model(.001)
        rng = np.random.RandomState(1234)

        A = m.add(Constant(D, value=rng.randn(D)))
        B = m.add(Constant(D, value=rng.randn(D)))

        CircularConvolution(m, A, B,
            neurons_per_product=neurons_per_product)

        sim = self.Simulator(m)
        sim.run_steps(10)

        # -- XXX
        #    We're missing correctness testing, but we've already run
        #    smoke test of the code in CircularConvolution.

    def test_small(self):
        return self._test_cconv(D=4, neurons_per_product=3)

    def test_med(self):
        return self._test_cconv(D=50, neurons_per_product=128)

    def test_large(self):
        return self._test_cconv(D=512, neurons_per_product=128)


if __name__ == "__main__":
    nengo.log_to_file('log.txt', debug=True)
    unittest.main()
