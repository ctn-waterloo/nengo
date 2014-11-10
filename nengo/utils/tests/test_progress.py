import time

import pytest

import nengo
from nengo.utils.progress import (
    AutoProgressBar, EveryNUpdater, IntervalUpdater, MaxNUpdater, Progress,
    ProgressObserver)


class ProgressObserverMock(ProgressObserver):
    def __init__(self):
        self.n_update_calls = 0

    def update(self, progress):
        self.n_update_calls += 1


class TestProgress(object):
    def test_progress_calculation(self):
        with Progress(10) as p:
            assert p.progress == 0.
            for _ in range(5):
                p.step()
            assert p.progress == 0.5
            p.step(5)
            assert p.progress == 1.

    def test_notifies_observers(self):
        observer = ProgressObserverMock()
        with Progress(10, [observer]) as p:
            for _ in range(5):
                p.step()
        assert observer.n_update_calls >= 5

    def test_finished_property(self):
        with Progress(10) as p:
            assert not p.finished
            p.step(5)
            assert not p.finished
        assert p.finished

    def test_success_property(self):
        with Progress(10) as p:
            assert p.success is None
        assert p.success

        try:
            with Progress(10) as p2:
                raise Exception()
        except:  # pylint: disable=bare-except
            pass
        assert not p2.success

    def test_elapsed_seconds(self, monkeypatch):
        t = 1.
        monkeypatch.setattr(time, 'time', lambda: t)

        with Progress(10) as p:
            t = 10.

        assert p.elapsed_seconds() == 9.

    def test_eta(self):
        with Progress(10) as p:
            assert p.eta() == -1  # no estimate available yet
            p.step()
            assert p.eta() > 0.


class TestAutoProgressBar(object):
    class ProgressMock(object):
        def __init__(self, eta, start_time=1234.5):
            self.eta = lambda: eta
            self.start_time = start_time

    def test_progress_not_shown_if_eta_below_threshold(self):
        progress_mock = self.ProgressMock(0.2)
        observer = ProgressObserverMock()
        auto_progress = AutoProgressBar(observer, min_eta=10.)

        for _ in range(10):
            auto_progress.update(progress_mock)

        assert observer.n_update_calls == 0

    def test_progress_shown_if_eta_above_threshold(self):
        progress_mock = self.ProgressMock(20.)
        observer = ProgressObserverMock()
        auto_progress = AutoProgressBar(observer, min_eta=10.)

        for _ in range(10):
            auto_progress.update(progress_mock)

        assert observer.n_update_calls >= 10


class TestMaxNUpdater(object):
    def test_at_most_n_updates_are_performed(self):
        observer = ProgressObserverMock()
        updater = MaxNUpdater(observer, max_updates=3)

        with Progress(100, [updater]) as p:
            for _ in range(100):
                p.step()

        assert observer.n_update_calls > 0
        assert observer.n_update_calls <= 3


class TestEveryNUpdater(object):
    def test_updates_every_n_steps(self):
        observer = ProgressObserverMock()
        updater = EveryNUpdater(observer, every_n=5)

        with Progress(100, [updater]) as p:
            observer.n_update_calls = 0
            for _ in range(5):
                p.step()
            assert observer.n_update_calls == 1

            p.step(2)
            assert observer.n_update_calls == 1
            p.step(3)
            assert observer.n_update_calls == 2


class TestIntervalUpdater(object):
    def test_updates_after_interval_has_passed(self, monkeypatch):
        observer = ProgressObserverMock()
        updater = IntervalUpdater(observer, update_interval=2.)
        t = 1.
        monkeypatch.setattr(time, 'time', lambda: t)

        with Progress(100, [updater]) as p:
            p.step()  # Update is allowed to happen on first step.

            observer.n_update_calls = 0
            p.step()
            assert observer.n_update_calls == 0

            t = 2.
            p.step()
            assert observer.n_update_calls == 0

            t = 4.
            p.step()
            assert observer.n_update_calls == 1


if __name__ == "__main__":
    nengo.log(debug=True)
    pytest.main([__file__, '-v'])
