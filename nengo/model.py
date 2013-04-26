from simulator import Simulator
from network import Network

import numpy as np

class Model(object):
    
    def __init__(self, name, seed=None, fixed_seed=None):
        """Container class that binds a Network model to a simulator for execution.

        :param string name:
            create and wrap a new Network with the given name.
        :param int seed:
            random number seed to use for creating ensembles.
            This one seed is used only to start the
            random generation process, so each neural group
            created will be different.

        :param int fixed_seed:
            random number seed for creating ensembles
            this one seed is used for all ensembles to create thier neurons
            this means that the neurons will have the same xintercepts and firing rates
            for all ensembles (different from seed above)
            
        """
        self.network = Network(name)
        self.name = name
        self.built = False
        self.time = 0

        self.backend_type = ''

        # set random seed generators
        if seed is None:
            seed = np.random.randint(1e5)
        np.random.seed(seed)
        self.seed = seed

    def build(self, dt=0.001):
        if not self.built:
            self.simulator = Simulator(self.network)
            self.simulator._build(dt)
            self.simulator._reset()
            self.built = True
        else:
            print "Ignoring duplicate build call"
    
    def reset(self):
        """ Reset the state of the simulation

            Runs through all nodes, then ensembles, then connections and then
            probes in the network and calls thier reset functions
            
        """
        self.simulator._reset()

    def run(self, time, dt=0.001, output=None, stop_when=None):
        """Run the simulation.

        If called twice, the simulation will continue for *time*
        more seconds. Note that the ensembles are simulated at the
        dt timestep specified when they are created.
        
        :param float time: the amount of time (in seconds) to run
        :param float dt: the timestep of the update
        
        """
        
        self.build(dt)
        self.simulator.run(time, dt, stop_when=stop_when)
          
    def __getattr__(self, attr):
        """Attempt to pass any failed attr calls to the network."""
        
        try:
            return getattr(self.network, attr)
        except AttributeError:
            raise AttributeError("Model instance has no attribute '" + attr + "'")

                                
