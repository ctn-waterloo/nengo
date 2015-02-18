import collections
import warnings

import numpy as np

from nengo.builder.signal import SignalDict
from nengo.cache import NoDecoderCache


class Model(object):
    """Output of the Builder, used by the Simulator."""

    def __init__(self, dt=0.001, label=None, decoder_cache=NoDecoderCache()):
        self.dt = dt
        self.label = label
        self.decoder_cache = decoder_cache

        # We want to keep track of the toplevel network
        self.toplevel = None
        # Builders can set a config object to affect sub-builders
        self.config = None

        # Resources used by the build process.
        self.operators = []
        self.probe_operators = []  # like operators, but done last
        self.params = {}
        self.seeds = {}
        self.sig = collections.defaultdict(dict)

        # Dummy RNG for checking ops, to not disturb the main RNG
        self._try_rng = np.random.RandomState(9)

    def __str__(self):
        return "Model: %s" % self.label

    def default_signaldict(self):
        return SignalDict(
            __step__=np.array(0, dtype=np.int32),
            __time__=np.array(0, dtype=np.float64))

    def build(self, obj, *args, **kwargs):
        return Builder.build(self, obj, *args, **kwargs)

    def add_op(self, op, probe=False):
        if probe:
            self.probe_operators.append(op)
        else:
            self.operators.append(op)
        self.try_op(op)

    def try_op(self, op):
        # Fail fast by trying make_step with a temporary sigdict
        signals = self.default_signaldict()
        op.init_signals(signals)
        op.make_step(signals, self.dt, self._try_rng)

    def has_built(self, obj):
        """Returns true iff obj has been processed by build."""
        return obj in self.params


class Builder(object):
    builders = {}

    @classmethod
    def register(cls, nengo_class):
        def register_builder(build_fn):
            if nengo_class in cls.builders:
                warnings.warn("Type '%s' already has a builder. Overwriting."
                              % nengo_class)
            cls.builders[nengo_class] = build_fn
            return build_fn
        return register_builder

    @classmethod
    def build(cls, model, obj, *args, **kwargs):
        if model.has_built(obj):
            # TODO: Prevent this at pre-build validation time.
            warnings.warn("Object %s has already been built." % obj)
            return

        for obj_cls in obj.__class__.__mro__:
            if obj_cls in cls.builders:
                break
        else:
            raise TypeError("Cannot build object of type '%s'." %
                            obj.__class__.__name__)
        cls.builders[obj_cls](model, obj, *args, **kwargs)
