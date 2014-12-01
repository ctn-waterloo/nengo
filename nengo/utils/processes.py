from __future__ import absolute_import
import numpy as np

from nengo.utils.distributions import Distribution, Gaussian


class StochasticProcess(object):
    """A base class for stochastic processes.

    Parameters
    ----------
    dimensions : int
        The number of dimensions of the process.
    """
    def __init__(self, dimensions=1):
        self.dimensions = dimensions

    def sample(self, dt, timesteps=None, rng=np.random):
        """Samples the process and advances the time.

        Parameters
        ----------
        dt : float
            Timestep for each sample.
        timesteps : int or ``None``, optional
            Number samples to take. If ``None`` a 1d array will be returned,
            whereas a value of 1 returns a 2d array with a second dimension of
            size 1.
        rng : RandomState, optional
            Random number generator state.

        Returns
        -------
        ndarray
            Samples as a 1d or 2d array depending on `timesteps`. The first
            dimensions enumerates the dimensions of the process.
        """
        raise NotImplementedError(
            "A StochasticProcess should implement sample.")


class SampledProcess(StochasticProcess):
    """A process where for every time point an independent sample of a
    probability distribution function is taken.

    Parameters
    ----------
    dist : :class:`Distribution`
        Probability distribution to sample from.
    dimensions : int
        The number of dimensions of the process.
    """
    def __init__(self, dist, dimensions=1):
        super(SampledProcess, self).__init__(dimensions)
        self.dist = dist

    def sample(self, dt, timesteps=None, rng=np.random):
        # FIXME correct for dt here?
        return self.dist.sample(self.dimensions, timesteps, rng=rng)


class MarkovProcess(StochasticProcess):
    """A Markov process (i.e. each new sample only depends on the current
    state).

    Parameters
    ----------
    dist : :class:`Distribution`
        Probability distribution to sample from in each timestep.
    dimensions : int
        The number of dimensions of the process.
    initial_state : 1d array, optional
        The initial state. The length has to match `dimensions`. If not given,
        an initial state of all zeros will be assumed.
    """
    def __init__(self, dist, dimensions=1, initial_state=None):
        super(MarkovProcess, self).__init__(dimensions)
        self.dist = dist
        if initial_state is None:
            self.state = np.zeros(dimensions)
        else:
            self.state = np.array(initial_state)
            if self.state.shape != (dimensions,):
                raise ValueError("initial_state has to match dimensions.")

    def sample(self, dt, timesteps=None, rng=np.random):
        samples = self.state[:, np.newaxis] + np.cumsum(
            self.dist.sample(
                self.dimensions, timesteps, rng=rng) * np.sqrt(dt),
            axis=0 if timesteps is None else 1)
        self.state[:] = samples[:, -1]
        return samples[:, 0] if timesteps is None else samples


class WienerProcess(MarkovProcess):
    """A Wiener process.

    Parameters
    ----------
    dimensions : int
        The number of dimensions of the process.
    initial_state : 1d array, optional
        The initial state. The length has to match `dimensions`. If not given,
        an initial state of all zeros will be assumed.
    """
    def __init__(self, dimensions=1, initial_state=None):
        super(WienerProcess, self).__init__(
            Gaussian(0, 1.), dimensions, initial_state)


class GaussianWhiteNoise(SampledProcess):
    """A Gaussian white noise process.

    Parameters
    ----------
    rms : float
        The RMS power of the signal.
    dimensions : int
        The number of dimensions of the process.
    """
    def __init__(self, rms=0.5, dimensions=1):
        super(GaussianWhiteNoise, self).__init__(Gaussian(0., rms), dimensions)
