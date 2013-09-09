import logging
import itertools
from collections import defaultdict
import time

import networkx
import networkx as nx
import numpy as np

from objects import LIF, LIFRate, Direct, Signal

def is_base(sig):
    return sig.base == sig

def is_view(sig):
    return not is_base(sig)

def are_aliased(a, b):
    # Terminology: two arrays *overlap* if the lowermost memory addressed
    # touched by upper one is higher than the uppermost memory address touched
    # by the lower one.
    # 
    # np.may_share_memory returns True iff there is overlap.
    # Overlap is a necessary but insufficient condition for *aliasing*.
    #
    # Aliasing is when two ndarrays refer a common memory location.
    #

    # -- least and greatest addresses don't even overlap
    if not np.may_share_memory(a, b):
        return False

    a_info = a.__array_interface__
    b_info = b.__array_interface__
    if a.dtype != b.dtype:
        raise NotImplementedError()
    #a_data = a_info['data']
    #b_data = b_info['data']
    #a_shape = a_info['shape']
    #b_shape = b_info['shape']
    a_strides = a_info['strides']
    b_strides = b_info['strides']

    if a_strides == b_strides == None:
        # -- a and b are both contiguous blocks
        #    if they didn't overlap then
        #    np.may_share_memory would have returned False
        #    It didn't -> they overlap -> they are aliased.
        return  True
    else:
        raise NotImplementedError('are_aliased?', (a_info, b_info))


def foo():
    nxdg = networkx.DiGraph()

    operators = []

    class SigBuf(object):
        def __init__(self, dct, sig):
            self.dct = dct
            self.sig = sig
            assert isinstance(dct, dict)

        def __hash__(self):
            return hash( (id(self.dct), self.sig))

        def __eq__(self, other):
            # XXX signal equality should be implemented to match
            #     base objects, strides, etc.
            return self.dct is other.dct and self.sig == other.sig

        def is_aliased_with(self, other):
            if self.dct is other.dct:
                if self.sig.base != other.sig.base:
                    return False
                elif self is other:
                    return True
                elif self.sig.same_view_as(other.sig):
                    return True
                else:
                    return are_aliased(self.get(), other.get())
            else:
                return False

        def get(self):
            return get_signal(self.dct, self.sig)

        def __str__(self):
            return 'SigBuf(-, %s)' % self.sig


    class Reset(object):
        def __init__(self, dst):
            self.dst = dst

            operators.append(self)

            self.reads = []
            self.sets = [dst]
            self.incs = []

        def __str__(self):
            return 'Reset(%s)' % str(self.dst)

        def go(self):
            self.dst.get()[...] = 0

        def add_edges(self, nxdg):
            nxdg.add_edge(self, self.dst)


    class Copy(object):
        def __init__(self, dst, src):
            self.dst = dst
            self.src = src

            operators.append(self)

            self.reads = [src]
            self.sets = [dst]
            self.incs = []

        def __str__(self):
            return 'Copy(%s -> %s)' % (
                    str(self.src), str(self.dst))

        def go(self):
            self.dst.get()[...] = self.src.get()

        def add_edges(self, nxdg):
            nxdg.add_edge(self.src, self)
            nxdg.add_edge(self, self.dst)


    class DotInc(object):
        def __init__(self, A, X, Y, xT=False, verbose=False, tag=None):
            self.A = A
            self.X = X
            self.Y = Y
            self.xT = xT
            self.verbose = verbose
            self.tag = tag

            operators.append(self)

            self.reads = [self.A, self.X]
            self.sets = []
            self.incs = [self.Y]

        def __str__(self):
            return 'DotInc(%s, %s -> %s "%s")' % (
                    str(self.A), str(self.X), str(self.Y), self.tag)

        def go(self):
            dot_inc(self.A.get(),
                    self.X.get().T if self.xT else self.X.get(),
                    self.Y.get())
            if self.verbose is not False:
                print '---'
                print self.tag
                print self.A, self.X, self.Y
                print self.A.get(), self.X.get(), self.Y.get()
                print self.verbose
                print '---'

        def add_edges(self, nxdg):
            nxdg.add_edge(self.A, self)
            nxdg.add_edge(self.X, self)
            nxdg.add_edge(self, self.Y)


    class NonLin(object):
        def __init__(self, output, J, nl, dt):
            self.output = output
            self.J = J
            self.nl = nl
            self.dt = dt

            operators.append(self)

            self.reads = [J]
            self.sets = [output]
            self.incs = []

        def go(self):
            self.nl.step(
                dt=self.dt,
                J=self.J.get(),
                output=self.output.get())

        def add_edges(self, nxdg):
            nxdg.add_edge(self.J, self)
            nxdg.add_edge(self, self.output)

    class DGCLS(object):
        @property
        def operators(self):
            return operators

        @property
        def dg(self):
            return nxdg

    DG = DGCLS()

    return DG, SigBuf, Copy, DotInc, NonLin, Reset



logger = logging.getLogger(__name__)

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

def get_signal(signals_dct, obj):
    # look up a Signal or SignalView
    # in a `signals_dct` such as self.signals
    if obj in signals_dct:
        return signals_dct[obj]
    elif obj.base in signals_dct:
        base_array = signals_dct[obj.base]
        try:
            # wtf?
            itemsize = int(obj.dtype.itemsize)
        except TypeError:
            itemsize = int(obj.dtype().itemsize)
        byteoffset = itemsize * obj.offset
        bytestrides = [itemsize * s for s in obj.elemstrides]
        view = np.ndarray(shape=obj.shape,
                          dtype=obj.dtype,
                          buffer=base_array.data,
                          offset=byteoffset,
                          strides=bytestrides,
                         )
        view[...]
        return view
    else:
        raise TypeError()


def dot_inc(a, b, targ):
    # -- we check for size mismatch,
    #    because incrementing scalar to len-1 arrays is ok
    #    if the shapes are not compatible, we'll get a
    #    problem in targ[...] += inc
    try:
        inc =  np.dot(a, b)
    except Exception, e:
        e.args = e.args + (a.shape, b.shape)
        raise
    if inc.shape != targ.shape:
        if inc.size == targ.size == 1:
            inc = np.asarray(inc).reshape(targ.shape)
        else:
            raise ValueError('shape mismatch', (inc.shape, targ.shape))
    targ[...] += inc


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
    constant_signals = []
    dynamic_signals = []
    nonlinearities = {}

    for sig in model.signals:
        if hasattr(sig, 'value'):
            if sig.base == sig:
                signals[sig] = np.asarray(sig.value)
            constant_signals.append(sig)
        else:
            if sig.base == sig:
                signals[sig] = np.zeros(sig.n)
            dynamic_signals.append(sig)

    for pop in model.nonlinearities:
        nonlinearities[pop] = registry[pop.__class__](pop)

    output_signals = {}

    dg, SigBuf, Copy, DotInc, NonLin, Reset = foo()

    # -- reset nonlinearities: bias -> input_current
    input_currents = {}
    for nl in model.nonlinearities:
        if is_view(nl.input_signal):
            raise NotImplementedError('need inc instead of copy')
        input_current = Signal(nl.input_signal.n,
                               name=nl.input_signal.name + '-incur')
        signals[input_current] = np.zeros(nl.input_signal.n)
        input_currents[nl.input_signal] = input_current
        Copy(SigBuf(signals, input_current),
             SigBuf(signals, nl.bias_signal))

    # -- encoders: signals -> input current
    #    (N.B. this includes neuron -> neuron connections)
    for enc in model.encoders:
        DotInc(SigBuf(signals, enc.sig),
               SigBuf(signals, enc.weights_signal),
               SigBuf(signals, input_currents[enc.pop.input_signal]),
               xT=True)

    # -- population dynamics
    output_currents = {}
    for nl in model.nonlinearities:
        pop = nonlinearities[nl]
        output_current = Signal(nl.output_signal.n,
                               name=nl.output_signal.name + '-outcur')
        signals[output_current] = np.zeros(nl.output_signal.n)
        output_currents[nl.output_signal] = output_current
        NonLin(output=SigBuf(signals, output_current),
               J=SigBuf(signals, input_currents[nl.input_signal]),
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
        else:
            sigbase = decoder_outputs[dec.sig.base]
        if is_view(dec.sig):
            dec_sig = dec.sig.view_like_self_of(sigbase)
        else:
            dec_sig = sigbase
        decoder_outputs[dec.sig] = dec_sig
        Reset(SigBuf(signals, dec_sig))
        DotInc(SigBuf(signals, output_currents[dec.pop.output_signal]),
               SigBuf(signals, dec.weights_signal),
               SigBuf(signals, dec_sig),
               xT=True)

    # -- set up output buffers
    output_stuff = {}
    output_signals = {}
    for filt in model.filters:
        if filt.newsig.base not in output_stuff:
            output_stuff[filt.newsig.base] = Signal(
                filt.newsig.base.n,
                name=filt.newsig.base.name + '-out')
            #print 'setup F output signal', filt.newsig, output_stuff[filt.newsig.base]
            output_signals[filt.newsig.base] = np.zeros(filt.newsig.base.n)
            signals[output_stuff[filt.newsig.base]] = output_signals[filt.newsig.base]
            Reset(SigBuf(signals, output_stuff[filt.newsig.base]))
        if is_view(filt.newsig):
            #print 'setup F view', filt.newsig, filt.newsig.base
            output_stuff[filt.newsig] = filt.newsig.view_like_self_of(
                output_stuff[filt.newsig.base])
        assert filt.newsig in output_stuff
    for tf in model.transforms:
        if tf.outsig.base not in output_stuff:
            output_stuff[tf.outsig.base] = Signal(
                tf.outsig.base.n,
                name=tf.outsig.base.name + '-out')
            #print 'setup T output signal', tf.outsig, output_stuff[tf.outsig.base]
            output_signals[tf.outsig.base] = np.zeros(tf.outsig.base.n)
            signals[output_stuff[tf.outsig.base]] = output_signals[tf.outsig.base]
            Reset(SigBuf(signals, output_stuff[tf.outsig.base]))
        if is_view(tf.outsig):
            #print 'setup T view', tf.outsig, tf.outsig.base
            output_stuff[tf.outsig] = tf.outsig.view_like_self_of(
                output_stuff[tf.outsig.base])
        assert tf.outsig in output_stuff

    # -- filters: signals_copy -> signals
    for filt in model.filters:
        try:
            #print 'Filter!', filt
            DotInc(SigBuf(signals, filt.alpha_signal),
                   SigBuf(signals, filt.oldsig),
                   SigBuf(signals, output_stuff[filt.newsig]),
                   #verbose=signals,
                   tag='filter')
        except Exception, e:
            e.args = e.args + (filt.oldsig, filt.newsig)
            raise

    # -- transforms: signals_tmp -> signals
    for tf in model.transforms:
        #print 'Transform!', tf
        #print tf
        #print tf.insig, id(tf.insig)
        #print tf.outsig, id(tf.outsig)
        try:
            insig = decoder_outputs[tf.insig]
        except KeyError:
            try:
                insig = output_currents[tf.insig]
            except KeyError:
                if tf.insig.base in decoder_outputs:
                    insig = tf.insig.view_like_self_of(decoder_outputs[tf.insig.base])
                elif tf.insig.base in output_currents:
                    insig = tf.insig.view_like_self_of(output_currents[tf.insig.base])
                else:
                    raise Exception('what is going on?')

        #print output_stuff[tf.outsig]
        DotInc(SigBuf(signals, tf.alpha_signal),
               SigBuf(signals, insig),
               SigBuf(signals, output_stuff[tf.outsig]),
               #verbose=signals,
               tag='transform')

    return Sim2(dg.operators, signals, dg.dg, output_signals, model)


class Sim2(object):
    def __init__(self, operators, signals, dg, _output_signals, model):
        self.operators = operators
        self._signals = signals
        self._output_signals = _output_signals
        self.dg = dg
        self.model = model

        #self.g = nx.DiGraph()
        for op in operators:
            op.add_edges(dg)

        self.add_constraints()  # <- this is slow
        self.order = self.eval_order()
        self.n_steps = 0
        self.probe_outputs = dict((probe, []) for probe in model.probes)

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

    def add_constraints(self, verbose=False):

        # -- all views of a base object in a particular dictionary
        t0 = time.time()
        if verbose: print 'building alias table ...'
        by_base = defaultdict(list)
        reads = defaultdict(list)
        sets = defaultdict(list)
        incs = defaultdict(list)

        for op in self.operators:
            for node in op.reads + op.sets + op.incs:
                by_base[(id(node.dct), node.sig.base)].append(node)

            for node in op.reads:
                reads[node].append(op)

            for node in op.sets:
                sets[node].append(op)

            for node in op.incs:
                incs[node].append(op)

        for node in sets:
            assert len(sets[node]) == 1, (node, sets[node])

        aliased = defaultdict(lambda : False)
        aliased_with = defaultdict(set)
        if verbose: print 'bases done ...'
        for ii, (sb, views) in enumerate(by_base.items()):
            if len(views) > 10:
                if verbose: print '%i / %i ' % (ii, len(views))
            for v1, v2 in itertools.combinations(views, 2):
                is_aliased = v1.is_aliased_with(v2)
                if is_aliased:
                    aliased[(v1, v2)] = True
                    aliased[(v2, v1)] = True
                    aliased_with[v1].add(v2)
                    aliased_with[v2].add(v1)
            if len(views) > 10:
                if verbose: print '%i / %i ' % (ii, len(views)), 'done'
        t1 = time.time()
        if verbose: print 'building alias table took', (t1 - t0)
        #self.sets_before_incs()
        #self.add_aliasing_restrictions()

        # assert that for every node (a) that is set
        # there are no other signals (b) that are
        # aliased to (a) and also set.
        for node, other in itertools.combinations(sets, 2):
            assert not aliased[(node, other)]

        # reads depend on sets and incs
        for node, post_ops in reads.items():
            pre_ops = sets[node] + incs[node]
            for other in aliased_with[node]:
                pre_ops += sets[other] + incs[other]
            for pre_op, post_op in itertools.product(pre_ops, post_ops):
                self.dg.add_edge(pre_op, post_op)

        # incs depend on sets
        for node, post_ops in incs.items():
            pre_ops = sets[node]
            for other in aliased_with[node]:
                pre_ops += sets[other]
            for pre_op, post_op in itertools.product(pre_ops, post_ops):
                self.dg.add_edge(pre_op, post_op)

    def eval_order(self):
        return [node for node in networkx.topological_sort(self.dg)
                if hasattr(node, 'go')]

    def step(self):
        for op in self.order:
            op.go()

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
