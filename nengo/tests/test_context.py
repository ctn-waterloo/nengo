import pytest

import nengo


class MyContext():
    def __init__(self):
        self.objs = []

    def add(self, obj):
        self.objs += [obj]

    def __enter__(self):
        nengo.context.append(self)

    def __exit__(self, exception_type, exception_value, traceback):
        nengo.context.pop()


def test_default(Simulator):
    model = nengo.Model("test")

    e = nengo.Ensemble(nengo.LIF(1), 1)
    n = nengo.Node([0])
    assert e in model.ensembles
    assert n in model.nodes

    con = MyContext()
    with con:
        e2 = nengo.Ensemble(nengo.LIF(1), 1)
    assert e2 in con.objs
    assert not e2 in model.connections

    e3 = nengo.Ensemble(nengo.LIF(1), 1)
    assert e3 in model.ensembles

    model2 = nengo.Model("test")  # new default
    e4 = nengo.Ensemble(nengo.LIF(1), 1)
    assert e4 in model2.ensembles
    assert not e4 in model.ensembles

    model3 = nengo.Model("test", use_as_default_context=False)
    e5 = nengo.Ensemble(nengo.LIF(1), 1)
    assert e5 in model2.ensembles
    assert not e5 in model3.ensembles


def test_with(Simulator):
    model = nengo.Model("test")

    con1 = MyContext()
    con2 = MyContext()
    con3 = MyContext()

    with con1:
        e1 = nengo.Ensemble(nengo.LIF(1), 1)
        assert e1 in con1.objs

        with con2:
            e2 = nengo.Ensemble(nengo.LIF(1), 1)
            assert e2 in con2.objs
            assert not e2 in con1.objs

            with con3:
                e3 = nengo.Ensemble(nengo.LIF(1), 1)
                assert e3 in con3.objs
                assert not e3 in con2.objs and not e3 in con1.objs

            e4 = nengo.Ensemble(nengo.LIF(1), 1)
            assert e4 in con2.objs
            assert not e4 in con3.objs

        e5 = nengo.Ensemble(nengo.LIF(1), 1)
        assert e5 in con1.objs

    e6 = nengo.Ensemble(nengo.LIF(1), 1)
    assert e6 in model.ensembles


def test_networks(Simulator):
    # TODO
    pass


if __name__ == "__main__":
    nengo.log(debug=True)
    pytest.main([__file__, '-v'])
