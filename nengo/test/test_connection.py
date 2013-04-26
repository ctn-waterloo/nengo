import nengo

import math
import numpy as np
import matplotlib.pyplot as plt

m = nengo.Model("test_connection")

input = m.make_node("input", np.sin)

pop1 = m.make_ensemble("pop1", 100, 1)
pop2 = m.make_ensemble('pop2', 50, 1)

m.connect("input:output", pop1)
m.connect('pop1','pop2')

m.probe('input:output')
m.probe('pop1:output')
m.probe('pop2:output')

#m.build()
m.run(6, dt=.001)

print "done"

probes = m.probes
        
plt.figure()
plt.hold(True)
plt.plot(probes[1].get_data())
plt.plot(probes[2].get_data())
plt.show()


