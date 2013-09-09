import logging
import itertools
from collections import defaultdict
import time

import networkx
import networkx as nx
import numpy as np

from objects import LIF, LIFRate, Direct, Signal

logger = logging.getLogger(__name__)


def is_base(sig):
    return sig.base == sig


def is_view(sig):
    return not is_base(sig)


def get_signal(signals_dct, obj):
    # look up a Signal or SignalView
    # in a `signals_dct` such as self.signals
    if obj in signals_dct:
        return signals_dct[obj]
    elif obj.base in signals_dct:
        base_array = signals_dct[obj.base]
        try:
            # for some installations, this works
            itemsize = int(obj.dtype.itemsize)
        except TypeError:
            # other installations, this...
            itemsize = int(obj.dtype().itemsize)
        byteoffset = itemsize * obj.offset
        bytestrides = [itemsize * s for s in obj.elemstrides]
        view = np.ndarray(shape=obj.shape,
                          dtype=obj.dtype,
                          buffer=base_array.data,
                          offset=byteoffset,
                          strides=bytestrides,
                         )
        return view
    else:
        raise TypeError()


class collect_operators_into(object):
    lists = []
    """
    Within this context, operators that are constructed
    are, by default, appended to an `operators` list.

    For example:

    >>> operators = []
    >>> with collect_operators_into(operators):
    >>>    Reset(foo)
    >>>    Copy(foo, bar)
    >>> assert len(operators) == 2

    After the context exits, `operators` contains the Reset
    and the Copy instances.

    """
    def __init__(self, operators):
        if operators is None:
            operators = []
        self.operators = operators

    def __enter__(self):
        self.lists.append(self.operators)

    def __exit__(self, exc_type, exc_value, tb):
        self.lists.remove(self.operators)

    @staticmethod
    def collect_operator(op):
        for lst in collect_operators_into.lists:
            lst.append(op)


class Operator(object):
    # automatic staticmethod
    def __new__(cls, *args, **kwargs):
        rval = super(Operator, cls).__new__(cls, *args, **kwargs)
        collect_operators_into.collect_operator(rval)
        return rval


class Reset(Operator):
    """
    Assign a constant value to a Signal.
    """
    def __init__(self, dst, value=0):
        self.dst = dst
        self.value = float(value)

        self.reads = []
        self.sets = [dst]
        self.incs = []

    def __str__(self):
        return 'Reset(%s)' % str(self.dst)

    def make_step(self, dct):
        target = get_signal(dct, self.dst)
        value = self.value
        def step():
            target[...] = value
        return step


class Copy(Operator):
    """
    Assign the value of one signal to another
    """
    def __init__(self, dst, src, tag=None):
        self.dst = dst
        self.src = src
        self.tag = tag

        self.reads = [src]
        self.sets = [dst]
        self.incs = []

    def __str__(self):
        return 'Copy(%s -> %s)' % (str(self.src), str(self.dst))

    def make_step(self, dct):
        dst = get_signal(dct, self.dst)
        src = get_signal(dct, self.src)
        def step():
            dst[...] = src
        return step


class DotInc(Operator):
    """
    Increment signal Y by dot(A, X)
    """
    def __init__(self, A, X, Y, xT=False, tag=None):
        self.A = A
        self.X = X
        self.Y = Y
        self.xT = xT
        self.tag = tag

        self.reads = [self.A, self.X]
        self.sets = []
        self.incs = [self.Y]

    def __str__(self):
        return 'DotInc(%s, %s -> %s "%s")' % (
                str(self.A), str(self.X), str(self.Y), self.tag)

    def make_step(self, dct):
        X = get_signal(dct, self.X)
        A = get_signal(dct, self.A)
        Y = get_signal(dct, self.Y)
        X = X.T if self.xT else X
        def step():
            # -- we check for size mismatch,
            #    because incrementing scalar to len-1 arrays is ok
            #    if the shapes are not compatible, we'll get a
            #    problem in Y[...] += inc
            try:
                inc =  np.dot(A, X)
            except Exception, e:
                e.args = e.args + (A.shape, X.shape)
                raise
            if inc.shape != Y.shape:
                if inc.size == Y.size == 1:
                    inc = np.asarray(inc).reshape(Y.shape)
                else:
                    raise ValueError('shape mismatch', (inc.shape, Y.shape))
            Y[...] += inc

        return step


class NonLin(Operator):
    """
    Set signal `output` by some non-linear function of J (and possibly other
    things too.)
    """
    def __init__(self, output, J, nl, dt):
        self.output = output
        self.J = J
        self.nl = nl
        self.dt = dt

        self.reads = [J]
        self.sets = [output]
        self.incs = []

    def make_step(self, dct):
        J = get_signal(dct, self.J)
        output = get_signal(dct, self.output)
        def step():
            self.nl.step(dt=self.dt, J=J, output=output)
        return step


class SimDirect(object):
    def __init__(self, nl):
        self.nl = nl

    def step(self, dt, J, output):
        output[...] = self.nl.fn(J)


class SimLIF(object):
    def __init__(self, nl):
        self.nl = nl
        self.voltage = np.zeros(nl.n_in)
        self.refractory_time = np.zeros(nl.n_in)

    def step(self, dt, J, output):
        self.nl.step_math0(dt, J, self.voltage, self.refractory_time, output)


class SimLIFRate(object):
    def __init__(self, nl):
        self.nl = nl

    def step(self, dt, J, output):
        output[:] = dt * self.nl.rates(J - self.nl.bias)


registry = {
    LIF: SimLIF,
    LIFRate: SimLIFRate,
    Direct: SimDirect,
}


def Simulator(*args):
    if len(args) == 2:
        if 'Test' in str(args[0]):
            model = args[1]
        else:
            raise TypeError('extra args to Simulator', args)
    elif len(args) == 1:
        model = args
    else:
        raise TypeError()

    signals = {}
    nonlinearities = {}

    for sig in model.signals:
        if hasattr(sig, 'value'):
            if sig.base == sig:
                signals[sig] = np.asarray(sig.value)
        else:
            if sig.base == sig:
                signals[sig] = np.zeros(sig.n)

    for pop in model.nonlinearities:
        nonlinearities[pop] = registry[pop.__class__](pop)

    output_signals = {}
    operators = []
    with collect_operators_into(operators):

        # -- reset nonlinearities: bias -> input_current
        input_currents = {}
        for nl in model.nonlinearities:
            if is_view(nl.input_signal):
                raise NotImplementedError('need inc instead of copy')
            input_current = Signal(nl.input_signal.n,
                                   name=nl.input_signal.name + '-incur')
            signals[input_current] = np.zeros(nl.input_signal.n)
            input_currents[nl.input_signal] = input_current
            Copy(input_current,
                 nl.bias_signal)

        # -- encoders: signals -> input current
        #    (N.B. this includes neuron -> neuron connections)
        for enc in model.encoders:
            DotInc(enc.sig,
                   enc.weights_signal,
                   input_currents[enc.pop.input_signal],
                   xT=True)

        # -- population dynamics
        output_currents = {}
        for nl in model.nonlinearities:
            pop = nonlinearities[nl]
            output_current = Signal(nl.output_signal.n,
                                   name=nl.output_signal.name + '-outcur')
            signals[output_current] = np.zeros(nl.output_signal.n)
            output_currents[nl.output_signal] = output_current
            NonLin(output=output_current,
                   J=input_currents[nl.input_signal],
                   nl=pop,
                   dt=model.dt)

        # -- decoders: population output -> signals_tmp
        decoder_outputs = {}
        for dec in model.decoders:
            if dec.sig.base not in decoder_outputs:
                sigbase = Signal(dec.sig.base.n,
                                 name=dec.sig.name + '-decbase')
                signals[sigbase] = np.zeros(sigbase.n)
                decoder_outputs[dec.sig.base] = sigbase
                Reset(sigbase)
            else:
                sigbase = decoder_outputs[dec.sig.base]
            if is_view(dec.sig):
                dec_sig = dec.sig.view_like_self_of(sigbase)
            else:
                dec_sig = sigbase
            decoder_outputs[dec.sig] = dec_sig
            DotInc(output_currents[dec.pop.output_signal],
                   dec.weights_signal,
                   dec_sig,
                   xT=True)

        # -- set up output buffers for filters and transforms
        output_stuff = {}
        output_signals = {}
        for filt in model.filters:
            if filt.newsig.base not in output_stuff:
                output_stuff[filt.newsig.base] = Signal(
                    filt.newsig.base.n,
                    name=filt.newsig.base.name + '-out')
                output_signals[filt.newsig.base] = np.zeros(filt.newsig.base.n)
                signals[output_stuff[filt.newsig.base]] = \
                        output_signals[filt.newsig.base]
                Reset(output_stuff[filt.newsig.base])
            if is_view(filt.newsig):
                output_stuff[filt.newsig] = filt.newsig.view_like_self_of(
                    output_stuff[filt.newsig.base])
            assert filt.newsig in output_stuff

        for tf in model.transforms:
            if tf.outsig.base not in output_stuff:
                output_stuff[tf.outsig.base] = Signal(
                    tf.outsig.base.n,
                    name=tf.outsig.base.name + '-out')
                output_signals[tf.outsig.base] = np.zeros(tf.outsig.base.n)
                signals[output_stuff[tf.outsig.base]] = \
                        output_signals[tf.outsig.base]
                Reset(output_stuff[tf.outsig.base])
            if is_view(tf.outsig):
                output_stuff[tf.outsig] = tf.outsig.view_like_self_of(
                    output_stuff[tf.outsig.base])
            assert tf.outsig in output_stuff

        # -- write to output buffers from filters
        for filt in model.filters:
            try:
                DotInc(filt.alpha_signal,
                       filt.oldsig,
                       output_stuff[filt.newsig],
                       tag='filter')
            except Exception, e:
                e.args = e.args + (filt.oldsig, filt.newsig)
                raise

        # -- write to output buffers from transforms
        for tf in model.transforms:
            try:
                insig = decoder_outputs[tf.insig]
            except KeyError:
                try:
                    insig = output_currents[tf.insig]
                except KeyError:
                    if tf.insig.base in decoder_outputs:
                        insig = tf.insig.view_like_self_of(
                            decoder_outputs[tf.insig.base])
                    elif tf.insig.base in output_currents:
                        insig = tf.insig.view_like_self_of(
                            output_currents[tf.insig.base])
                    else:
                        raise Exception('what is going on?')

            DotInc(tf.alpha_signal,
                   insig,
                   output_stuff[tf.outsig],
                   tag='transform')

    return Sim2(operators, signals, output_signals, model)


class Sim2(object):
    def __init__(self, operators, signals, _output_signals, model):
        self._signals = signals
        self._output_signals = _output_signals
        self.model = model
        self.dg = self._init_dg(operators)
        self._step_order = [node
            for node in networkx.topological_sort(self.dg)
            if hasattr(node, 'make_step')]
        self._steps = [node.make_step(self._signals)
            for node in self._step_order]
        self.n_steps = 0
        self.probe_outputs = dict((probe, []) for probe in model.probes)

    def _init_dg(self, operators, verbose=False):
        dg = networkx.DiGraph()

        for op in operators:
            dg.add_edges_from(itertools.product(op.reads, [op]))
            dg.add_edges_from(itertools.product([op], op.sets + op.incs))

        # -- all views of a base object in a particular dictionary
        by_base_writes = defaultdict(list)
        reads = defaultdict(list)
        sets = defaultdict(list)
        incs = defaultdict(list)

        for op in operators:
            for node in op.sets + op.incs:
                by_base_writes[node.base].append(node)

            for node in op.reads:
                reads[node].append(op)

            for node in op.sets:
                sets[node].append(op)

            for node in op.incs:
                incs[node].append(op)

        # -- assert that only one op sets any particular view
        for node in sets:
            assert len(sets[node]) == 1, (node, sets[node])

        # -- assert that no two views are both set and aliased
        for node, other in itertools.combinations(sets, 2):
            assert not node.shares_memory_with(other)

        # -- Scheduling algorithm for serial evaluation:
        #    1) All sets on a given base signal
        #    2) All incs on a given base signal
        #    3) All reads on a given base signal

        # -- incs depend on sets
        for node, post_ops in incs.items():
            pre_ops = list(sets[node])
            for other in by_base_writes[node.base]:
                pre_ops += sets[other]
            dg.add_edges_from(itertools.product(set(pre_ops), post_ops))

        # -- reads depend on writes (sets and incs)
        for node, post_ops in reads.items():
            pre_ops = sets[node] + incs[node]
            for other in by_base_writes[node.base]:
                pre_ops += sets[other] + incs[other]
            dg.add_edges_from(itertools.product(set(pre_ops), post_ops))

        return dg


    @property
    def signals(self):
        class Accessor(object):
            def __getitem__(_, item):
                return self._signals[item]

            def __setitem__(_, item, val):
                self._signals[item][...] = val

            def __iter__(_):
                return self._signals.__iter__()

            def __len__(_):
                return self._signals.__len__()
        return Accessor()

    def step(self):
        for step_fn in self._steps:
            step_fn()

        for k, v in self._output_signals.items():
            self._signals[k][...] = v

        # -- probes signals -> probe buffers
        for probe in self.model.probes:
            period = int(probe.dt / self.model.dt)
            if self.n_steps % period == 0:
                tmp = get_signal(self._signals, probe.sig).copy()
                self.probe_outputs[probe].append(tmp)

        self.n_steps += 1

    def run_steps(self, N):
        for i in xrange(N):
            if i % 1000 == 0:
                logger.debug("Step %d", i)
            self.step()

    def probe_data(self, probe):
        return np.asarray(self.probe_outputs[probe])
