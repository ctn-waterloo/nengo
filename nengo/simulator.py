"""
simulator.py: Simple reference simulator for base.Model

"""

import numpy as np

from neuron import step_lif
from neuron import step_lif_rate

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
        

def zero_array_dct(dct):
    for arr in dct.values():
        arr[...] = 0


class Simulator(object):
    def __init__(self, model):
        self.model = model

        self.n_steps = 0
        self.signals = {}
        self.signals_tmp = {}
        self.signals_copy = {}
        self.populations = {}
        self.probe_outputs = {}

        for sig in self.model.signals:
            if hasattr(sig, 'value'):
                self.signals[sig] = np.asarray(sig.value)
            else:
                self.signals[sig] = np.zeros(sig.n)
            self.signals_tmp[sig] = np.zeros(sig.n)
            self.signals_copy[sig] = np.zeros(sig.n)

        for pop in self.model.populations:
            self.populations[pop] = {
                'ic': np.zeros(pop.n),
                'v': np.zeros(pop.n),
                'rt': np.zeros(pop.n),
                'out': np.zeros(pop.n),
                'jbias': pop.bias,
            }

        for probe in self.model.signal_probes:
            self.probe_outputs[probe] = []


    def step(self):
        # population bias: bias -> input current
        for pop in self.model.populations:
            self.populations[pop]['ic'][...] = self.populations[pop]['jbias']

        # encoders: signals -> input current
        for enc in self.model.encoders:
            self.populations[enc.pop]['ic'] += np.dot(
                get_signal(self.signals,enc.sig),
                enc.weights.T)

        # population dynamics (TODO: registry)
        for pop in self.model.populations:
            step_lif(
                self.populations[pop]['ic'],
                self.populations[pop]['v'],
                self.populations[pop]['rt'],
                self.populations[pop]['out'],
                dt=self.model.dt,
                tau_rc=pop.tau_rc,
                tau_ref=pop.tau_ref,
                upsample=pop.upsample,
                )

        # population dynamics (TODO: registry)
        for pop in self.model.populations_lif_rate:
            step_lif_rate(
                self.populations[pop]['ic'],
                self.populations[pop]['out'],
                tau_rc=pop.tau_rc,
                tau_ref=pop.tau_ref,
                dt=self.model.dt,
                )

        # decoders: population output -> signals_tmp
        zero_array_dct(self.signals_tmp)
        for dec in self.model.decoders:
            get_signal(self.signals_tmp, dec.sig)[...] += np.dot(
                self.populations[dec.pop]['out'],
                dec.weights.T)

        # -- copy: signals -> signals_copy
        for sig in self.model.signals:
            self.signals_copy[sig][...] = self.signals[sig]

        # -- filters: signals_copy -> signals
        zero_array_dct(self.signals)
        for filt in self.model.filters:
            new, old = filt.newsig, filt.oldsig
            inc =  np.dot(filt.alpha, get_signal(self.signals_copy, old))
            targ = get_signal(self.signals, new)
            # -- we check for size mismatch,
            #    because incrementing scalar to len-1 arrays is ok
            #    if the shapes are not compatible, we'll get a 
            #    problem in targ[...] += inc
            if inc.size != targ.size:
                raise ValueError('shape mismatch in filter',
                                 (filt, inc.shape, targ.shape))
            targ[...] += inc

        # -- transforms: signals_tmp -> signals
        for tf in self.model.transforms:
            get_signal(self.signals, tf.outsig)[...] += np.dot(
                tf.alpha,
                get_signal(self.signals_tmp, tf.insig))

        # -- customs: signals -> signals
        for ct in self.model.custom_transforms:
            get_signal(self.signals, ct.outsig)[...] = ct.func(
                get_signal(self.signals, ct.insig))

        # -- probes signals -> probe buffers
        for probe in self.model.signal_probes:
            period = int(probe.dt / self.model.dt)
            if self.n_steps % period == 0:
                tmp = get_signal(self.signals, probe.sig).copy()
                self.probe_outputs[probe].append(tmp)

        self.n_steps += 1

    def run_steps(self, N, verbose=False):
        for i in xrange(N):
            self.step()
            if verbose:
                print self.signals

    def signal_probe_output(self, probe):
        return self.probe_outputs[probe]

