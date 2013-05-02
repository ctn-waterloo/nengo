import nengo

import math
import numpy as np
import matplotlib.pyplot as plt

m = nengo.Model("test_connection")

print "making"

input = m.make_node("input", lambda x: 0.5)
pop1 = m.make_ensemble("pop1", 100, 1)
pop2 = m.make_ensemble('pop2', 100, 1)

print "connecting"

m.connect("input", pop1)
m.connect('pop1','pop2')
#m.connect("pop1", "pop2", func=lambda x: np.asarray([0.5]))

print "probing"

m.probe('input')
m.probe('pop1:output')
m.probe('pop2')

#m.build()
m.run(1, dt=.001)

probes = m.probes

plt.figure()
plt.hold(True)
plt.plot(probes[0].get_data())
plt.plot(probes[1].get_data())
plt.plot(probes[2].get_data())
plt.legend(['input', 'popA', 'popB'])
plt.show()


