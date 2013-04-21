from .. import nengo as nengo
from ..nengo.connection import gen_transfrom
from ..nengo.filter import ExponentialPSC

## This example demonstrates how to create a controlled integrator in neurons.
##   The controlled integrator takes two inputs: 
##      Input - the input to the integrator
##      Control - the control signal to the integrator
##   The function the controlled integrator implements can be written in the 
##   following control theoretic equation:
##     
##     a_dot(t) = control(t) * a(t) + B * input(t)
##
##   The NEF equivalent equation for this integrator is:
##
##     a_dot(t) = control(t) * a(t) + tau * input(t)
##
##   where tau is the recurrent time constant.
##
## Network diagram:
##
##                     .----.
##                     v    | 
##      [Input] ----> (A) --'
##                     ^ 
##      [Control] -----'
##
##
## Network behaviour:
##   A = tau * Input + Input * Control
##

# Define model parameters
tau = 0.1                                           # Recurrent time constant

# Create the nengo model
model = nengo.Model('Controlled Integrator')

# Create the model inputs
def input_func(t):                                  # Create a function that outputs
    if t < 0.2:                                     #   5 at time 0.2s, then 0 at time 0.3s,
        return [0]                                  #   -10 at time 0.44, then 0 at time 0.8,
    elif t < 0.3:                                   #   5 at time 0.8, then 0 at time 0.9
        return [5]
    elif t < 0.44:
        return [0]
    elif t < 0.54:
        return [-10]
    elif t < 0.8:
        return [0]
    elif t < 0.9:
        return [5]
    else:
        return [0]
model.make_node('Input', input_func)                # Create a controllable input function 
                                                    #   with the function above
model.make_node('Control', [1])                     # Create a controllable input function
                                                    #   with a starting value of 1

# Create the neuronal ensembles
model.make_ensemble('A', 225, 2,                    # Make a population with 225 neurons, 
                    radius = 1.5)                   #   2 dimensions, and a larger radius 
                                                    #   to accommodate large simulataneous 
                                                    #   inputs

# Create the connections within the model
model.connect('Input', 'A', transform = gen_transform(index_post = 0, weight = tau), 
              filter = {'type': 'ExponentialPSC', 'pstc': 0.1})  
                                                    # Connect all the input signals to the 
                                                    #   ensemble with the appropriate 1 x 2
                                                    #   mappings, postsynaptic time
                                                    #   constant is 10ms
model.connect('Control', 'A', transform = gen_transform(index_post = 1), 
              filter = {'type': 'ExponentialPSC', 'pstc': 0.1})

def feedback(x):
    return x[0] * x[1]
model.connect('A', 'A', transform = gen_transform(index_post = 0), func = feedback, 
              filter = {'type': 'ExponentialPSC', 'pstc': tau})  
                                                    # Create the recurrent
                                                    #   connection mapping the
                                                    #   1D function 'feedback'
                                                    #   into the 2D population
                                                    #   using the 1 x 2 transform

# Build the model
model.build()

# Run the model
model.run(1)                                        # Run the model for 1 second
