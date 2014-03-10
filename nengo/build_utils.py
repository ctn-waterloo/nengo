"""These are helper functions that various backends may find useful for
generating their own Builder system.
"""

from . import objects
from . import model
import numpy as np


def generate_dot(objs, connections):
    """Create a .dot file with this set of objects and connections

    Parameters
    ----------
    objs : list of Nodes and Ensembles
        All the objects in the model
    connections : list of Connections
        All the Connections in the model

    Returns the text contents of the desired .dot file

    This can be useful for debugging and testing Builders that manipulate
    the model graph before construction.
    """
    text = []
    text.append('digraph G {')
    for obj in objs:
        text.append('  "%d" [label="%s"];' % (id(obj), obj.label))

    def label(transform):
        # determine the label for a connection based on its transform
        if len(transform.shape) == 0:
            return ''
        return '%dx%d' % transform.shape

    for c in connections:
        text.append('  "%d" -> "%d" [label="%s"];' % (id(c.pre), id(c.post),
                                                      label(c.transform)))
    text.append('}')
    return '\n'.join(text)


def remove_passthrough_nodes(objs, connections):
    """Returns a version of the model without passthrough Nodes

    For some backends (such as SpiNNaker), it is useful to remove Nodes that
    have 'None' as their output.  These nodes simply sum their inputs and
    use that as their output. These nodes are defined purely for organizational
    purposes and should not affect the behaviour of the model.  For example,
    the 'input' and 'output' Nodes in an EnsembleArray, which are just meant to
    aggregate data.

    Note that removing passthrough nodes can simplify a model and may be useful
    for other backends as well.  For example, an EnsembleArray connected to
    another EnsembleArray with an identity matrix as the transform
    should collapse down to D Connections between the corresponding Ensembles
    inside the EnsembleArrays.

    Parameters
    ----------
    objs : list of Nodes and Ensembles
        All the objects in the model
    connections : list of Connections
        All the Connections in the model

    Returns the objs and connections of the resulting model.  The passthrough
    Nodes will be removed, and the Connections that interact with those Nodes
    will be replaced with equivalent Connections that don't interact with those
    Nodes.

    """
    c_removed = []    # connections we are removing
    c_new = []        # connections we are adding
    obj_removed = []  # objects we are removing

    # these hold all of the inputs to and outputs from each object
    inputs = {}
    outputs = {}
    for obj in objs:
        inputs[obj] = []
        outputs[obj] = []
    for c in connections:
        inputs[c.post].append(c)
        outputs[c.pre].append(c)

    # look for passthrough Nodes to remove
    for obj in objs:
        if isinstance(obj, objects.Node) and obj.output is None:
            obj_removed.append(obj)

            # get rid of the connections to and from this Node
            for c in inputs[obj]:
                c_removed.append(c)
                outputs[c.pre].remove(c)
            for c in outputs[obj]:
                c_removed.append(c)
                inputs[c.post].remove(c)

            # replace those connections with equivalent ones
            for c_in in inputs[obj]:
                if c_in.pre is obj:
                    raise Exception('Cannot remove a Node with feedback')

                for c_out in outputs[obj]:

                    # determine the filter for the new Connection
                    if c_in.filter is None:
                        filter = c_out.filter
                    elif c_out.filter is None:
                        filter = c_in.filter
                    else:
                        raise NotImplementedError('Cannot merge two filters')
                        # Note: the algorithm below is in the right ballpark,
                        #  but isn't exactly the same as two low-pass filters
                        #filter = c_out.filter + c_in.filter

                    function = c_in.function
                    if c_out.function is not None:
                        raise Exception('Cannot remove a Node with a' +
                                        'function being computed on it')

                    # compute the combined transform
                    transform = np.dot(c_out.transform, c_in.transform)
                    # check if the transform is 0 (this happens a lot
                    #  with things like identity transforms)
                    if not np.all(transform == 0):
                        dummy = model.Model()  # need a dummy model so these
                        with dummy:            # connections don't get added
                            args = {}
                            if function is not None:
                                args['function'] = function
                            c = objects.Connection(c_in.pre, c_out.post,
                                                   filter=filter,
                                                   transform=transform, **args)

                        c_new.append(c)
                        outputs[c.pre].append(c)  # put this in the list, since
                        inputs[c.post].append(c)  # it might be used another
                                                  # time through the loop

    # build up the resulting lists
    for c in c_new:
        if c not in c_removed:
            connections.append(c)
    for c in c_removed:
        if c not in c_new:
            connections.remove(c)
    for obj in obj_removed:
        objs.remove(obj)

    return objs, connections
