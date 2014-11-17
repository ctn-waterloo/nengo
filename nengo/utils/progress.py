"""Utilities for progress tracking and display to the user."""

from __future__ import absolute_import, division

from datetime import timedelta
import os
import sys
import time
import warnings

import numpy as np

from nengo.utils.stdlib import get_terminal_size
from nengo.utils.ipython import in_ipynb


try:
    from IPython.html import widgets
    from IPython.display import display
    import IPython.utils.traitlets as traitlets
    _HAS_WIDGETS = True
except ImportError:
    _HAS_WIDGETS = False


class MemoryLeakWarning(UserWarning):
    pass


warnings.filterwarnings('once', category=MemoryLeakWarning)


def _timestamp2timedelta(timestamp):
    return timedelta(seconds=np.ceil(timestamp))


class Progress(object):
    """Stores and tracks information about the progress of some process.

    This class is to be used as part of a ``with`` statement. Use ``step()`` to
    update the progress.

    Parameters
    ----------
    max_steps : int
        The total number of calculation steps of the process.

    Attributes
    ----------
    steps : int
        Number of completed steps.
    max_steps : int
        The total number of calculation steps of the process.
    start_time : float
        Time stamp of the time the process was started.
    end_time : float
        Time stamp of the time the process was finished or aborted.
    success : bool or None
        Whether the process finished successfully. ``None`` if the process
        did not finish yet.

    Examples
    --------

    >>> max_steps = 10
    >>> with Progress(max_steps) as progress:
    ...     for i in range(max_steps):
    ...         # do something
    ...         progress.step()

    """

    def __init__(self, max_steps):
        self.n_steps = 0
        self.max_steps = max_steps
        self.start_time = self.end_time = time.time()
        self.finished = False
        self.success = None

    @property
    def progress(self):
        """
        Returns
        -------
        float
            The current progress as a number from 0 to 1 (inclusive).
        """
        return min(1.0, self.n_steps / self.max_steps)

    def elapsed_seconds(self):
        """
        Returns
        -------
        float
            The number of seconds passed since entering the ``with`` statement.
        """
        if self.finished:
            return self.end_time - self.start_time
        else:
            return time.time() - self.start_time

    def eta(self):
        """
        Returns
        -------
        float
            The estimated number of seconds until the process
            is finished. Also called the estimated time of arrival (ETA).
            If no estimate is available -1 will be returned.
        """
        if self.progress > 0.:
            return (
                (1. - self.progress) * self.elapsed_seconds() / self.progress)
        else:
            return -1

    def __enter__(self):
        self.finished = False
        self.success = None
        self.n_steps = 0
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.success = exc_type is None
        if self.success:
            self.n_steps = self.max_steps
        self.end_time = time.time()
        self.finished = True

    def step(self, n=1):
        """Advances the progress.

        Parameters
        ----------
        n : int
            Number of steps to advance the progress by.
        """
        self.n_steps += n


class UpdateBehavior(object):
    """Abstract base class for classes controlling the updates to a progress
    bar given some progress information.

    Parameters
    ----------
    progress_bar : :class:`ProgressObserver`
        The object to which updates are passed on.
    """
    # pylint: disable=abstract-method

    def __init__(self, progress_bar):
        self.progress_bar = progress_bar

    def update(self, progress):
        """Notify about changed progress and update progress bar if desired

        Parameters
        ----------
        progress : :class:`Progress`
            Changed progress information.
        """
        raise NotImplementedError()


class ProgressBar(object):
    """Abstract base class for progress bars (classes displaying the progress
    in some way).
    """

    def update(self, progress):
        """Updates the displayed progress.

        Parameters
        ----------
        progress : :class:`Progress`
            The progress information to display.
        """
        raise NotImplementedError()


class NoProgressBar(ProgressBar):
    """A progress bar that does not display anything."""

    def update(self, progress):
        pass


class CmdProgressBar(ProgressBar):
    """A progress bar that is displayed as ASCII output on `stdout`."""

    def __init__(self):
        super(CmdProgressBar, self).__init__()
        if in_ipynb():
            warnings.warn(MemoryLeakWarning((
                "The {cls}, if used in an IPython notebook,"
                " will continuously adds invisible content to the "
                "IPython notebook which may lead to excessive memory usage "
                "and ipynb files which cannot be opened anymore. Please "
                "consider doing one of the following:{cr}{cr}"
                "  * Wrap {cls} in an UpdateLimiter class. This reduces the "
                "memory consumption, but does not solve the problem "
                "completely.{cr}"
                "  * Disable the progress bar.{cr}"
                "  * Use IPython 2.0 or later and the IPython2ProgressBar "
                "(this is the default behavior from IPython 2.0 onwards).{cr}"
                ).format(cls=self.__class__.__name__, cr=os.linesep)))
            sys.stderr.flush()  # Show warning immediately.

    def update(self, progress):
        if progress.finished:
            line = self._get_finished_line(progress)
        else:
            line = self._get_in_progress_line(progress)
        sys.stdout.write(line)
        sys.stdout.flush()

    def _get_in_progress_line(self, progress):
        line = "[{{0}}] ETA: {eta}".format(
            eta=_timestamp2timedelta(progress.eta()))
        percent_str = " {0}% ".format(int(100 * progress.progress))

        width, _ = get_terminal_size()
        progress_width = max(0, width - len(line))
        progress_str = (
            int(progress_width * progress.progress) * "#").ljust(
            progress_width)

        percent_pos = (len(progress_str) - len(percent_str)) // 2
        if percent_pos > 0:
            progress_str = (
                progress_str[:percent_pos] + percent_str +
                progress_str[percent_pos + len(percent_str):])

        return '\r' + line.format(progress_str)

    def _get_finished_line(self, progress):
        width, _ = get_terminal_size()
        line = "Done in {0}.".format(
            _timestamp2timedelta(progress.elapsed_seconds())).ljust(width)
        return '\r' + line + os.linesep


if _HAS_WIDGETS:
    class IPythonProgressWidget(widgets.DOMWidget):
        """IPython widget for displaying a progress bar."""

        # pylint: disable=too-many-public-methods
        _view_name = traitlets.Unicode('NengoProgressBar', sync=True)
        progress = traitlets.Float(0., sync=True)
        text = traitlets.Unicode(u'', sync=True)

        FRONTEND = '''
        require(["widgets/js/widget", "widgets/js/manager"],
            function(widget, manager) {
          if (typeof widget.DOMWidgetView == 'undefined') {
            widget = IPython;
          }
          if (typeof manager.WidgetManager == 'undefined') {
            manager = IPython;
          }

          var NengoProgressBar = widget.DOMWidgetView.extend({
            render: function() {
              // $el is the DOM of the widget
              this.$el.css({width: '100%', marginBottom: '0.5em'});
              this.$el.html([
                '<div style="',
                    'width: 100%;',
                    'border: 1px solid #cfcfcf;',
                    'border-radius: 4px;',
                    'text-align: center;',
                    'position: relative;">',
                  '<div class="pb-text" style="',
                      'position: absolute;',
                      'width: 100%;">',
                    '0%',
                  '</div>',
                  '<div class="pb-bar" style="',
                      'background-color: #bdd2e6;',
                      'width: 0%;',
                      'transition: width 0.1s linear;">',
                    '&nbsp;',
                  '</div>',
                '</div>'].join(''));
            },

            update: function() {
              this.$el.css({width: '100%', marginBottom: '0.5em'});
              var progress = 100 * this.model.get('progress');
              var text = this.model.get('text');
              this.$el.find('div.pb-bar').width(progress.toString() + '%');
              this.$el.find('div.pb-text').text(text);
            },
          });

          manager.WidgetManager.register_widget_view(
            'NengoProgressBar', NengoProgressBar);
        });'''

        @classmethod
        def load_frontend(cls):
            """Loads the JavaScript front-end code required by then widget."""
            # pylint: disable=undefined-variable,line-too-long
            get_ipython().run_cell_magic('javascript', '', cls.FRONTEND)  # noqa

    if in_ipynb():
        IPythonProgressWidget.load_frontend()


class IPython2ProgressBar(ProgressBar):
    """IPython progress bar based on widgets."""

    def __init__(self):
        super(IPython2ProgressBar, self).__init__()
        self._widget = IPythonProgressWidget()
        self._initialized = False

    def init(self):
        self._initialized = True
        display(self._widget)

    def update(self, progress):
        if not self._initialized:
            self.init()

        self._widget.progress = progress.progress
        if progress.finished:
            self._widget.text = "Done in {0}.".format(
                _timestamp2timedelta(progress.elapsed_seconds()))
        else:
            self._widget.text = "{progress:.0f}%, ETA: {eta}".format(
                progress=100 * progress.progress,
                eta=_timestamp2timedelta(progress.eta()))


class WriteProgressToFile(ProgressBar):
    """Writes the progress to a file. This file will be overwritten on each
    update of the progress! Useful for remotely and intermittently
    monitoring progress.

    Parameters
    ----------
    filename : str
        Path to the file to write the progress to.
    """

    def __init__(self, filename):
        self.filename = filename
        super(WriteProgressToFile, self).__init__()

    def update(self, progress):
        if progress.finished:
            text = "Done in {0}.".format(
                _timestamp2timedelta(progress.elapsed_seconds()))
        else:
            text = "{progress:.0f}%, ETA: {eta}".format(
                progress=100 * progress.progress,
                eta=_timestamp2timedelta(progress.eta()))

        with open(self.filename, 'w') as f:
            f.write(text + os.linesep)


class AutoProgressBar(ProgressBar):
    """Makes a progress automatically appear if the expected time to completion
     or arrival (ETA) exceeds a threshold.

    Parameters
    ----------
    delegate : :class:`ProgressBar`
        The actual progress bar to display.
    min_eta : float, optional
        The ETA threshold for displaying the progress bar.
    """

    def __init__(self, delegate, min_eta=1.):
        self.delegate = delegate

        super(AutoProgressBar, self).__init__()

        self.min_eta = min_eta
        self._visible = False

    def update(self, progress):
        min_delay = progress.start_time + 0.1
        if self._visible:
            self.delegate.update(progress)
        elif progress.eta() > self.min_eta and min_delay < time.time():
            self._visible = True
            self.delegate.update(progress)


class MaxNUpdater(UpdateBehavior):
    """Limits the number of updates relayed to a :class:`ProgressObserver`.
    Used for IPython 1.x progress bar, since updating
    the notebook saves the output, which will create
    a large amount of memory and cause the notebook to crash.

    Parameters
    ----------
    progress_bar : :class:`ProgressBar`
        The progress bar to relay the updates to.
    max_updates : int
        Maximum number of updates that will be relayed to the progress
        bar.
    """

    def __init__(self, progress_bar, max_updates=100):
        super(MaxNUpdater, self).__init__(progress_bar)
        self.max_updates = max_updates
        self.last_update_step = 0

    def update(self, progress):
        next_update_step = (self.last_update_step +
                            progress.max_steps / self.max_updates)
        if next_update_step < progress.n_steps or progress.finished:
            self.progress_bar.update(progress)
            self.last_update_step = progress.n_steps


class EveryNUpdater(UpdateBehavior):
    """Relays only every `n`-th update to a :class:`ProgressBar`.

    Parameters
    ----------
    progress_bar : :class:`ProgressBar`
        The progress bar to relay the updates to.
    every_n : int
        The number of steps in-between relayed updates.
    """

    def __init__(self, progress_bar, every_n=1000):
        super(EveryNUpdater, self).__init__(progress_bar)
        self.every_n = every_n
        self.next_update = every_n

    def update(self, progress):
        if self.next_update <= progress.n_steps or progress.finished:
            self.progress_bar.update(progress)
            assert self.every_n > 0
            self.next_update = progress.n_steps + self.every_n


class IntervalUpdater(UpdateBehavior):
    """Updates a :class:`ProgressBar` in regular time intervals.

    Parameters
    ----------
    progress_bar : :class:`ProgressBar`
        The progress bar to relay the updates to.
    update_interval : float
        Number of seconds in-between relayed updates.
    """

    def __init__(self, progress_bar, update_interval=0.05):
        super(IntervalUpdater, self).__init__(progress_bar)
        self.next_update = 0
        self.update_interval = update_interval

    def update(self, progress):
        if self.next_update < time.time() or progress.finished:
            self.progress_bar.update(progress)
            self.next_update = time.time() + self.update_interval


class ProgressTracker(object):
    """Tracks the progress of some process with a progress bar.

    Parameters
    ----------
    max_steps : int
        Maximum number of steps of the process.
    progress_bar : :class:`ProgressBar` or :class:`UpdateBehavior`
        The progress bar to display the progress.
    """
    def __init__(self, max_steps, progress_bar):
        self.progress = Progress(max_steps)
        self.progress_bar = progress_bar

    def __enter__(self):
        self.progress.__enter__()
        self.progress_bar.update(self.progress)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.progress.__exit__(exc_type, exc_value, traceback)
        self.progress_bar.update(self.progress)

    def step(self, n=1):
        """Advance the progress and update the progress bar.

        Parameters
        ----------
        n : int
            Number of steps to advance the progress by.
        """
        self.progress.step(n)
        self.progress_bar.update(self.progress)


def get_default_progressbar():
    """
    Returns
    -------
    :class:`ProgressBar`
        The default progress bar to use depending on the execution environment.
    """
    if in_ipynb() and _HAS_WIDGETS:  # IPython >= 2.0
        return AutoProgressBar(IPython2ProgressBar())
    else:  # IPython < 2.0
        return AutoProgressBar(CmdProgressBar())


def get_default_updater_class(progress_bar):
    """
    Parameters
    ----------
    progress_bar : :class:`ProgressBar`
        The progress bar to obtain the default update behavior for.

    Returns
    -------
    :class:`UpdateBehavior`
        The default update behavior depending on the progress bar and
        execution environment.
    """
    if in_ipynb() and not isinstance(progress_bar, IPython2ProgressBar):
        return MaxNUpdater
    else:
        return IntervalUpdater


def wrap_with_update_behavior(progress_bar=None):
    """Wraps a progress bar with the default update behavior if it is not
    wrapped by an update behavior already.

    Parameters
    ----------
    progress_bar : :class:`ProgressObserver`
        The progress bar to wrap.

    Returns
    -------
    :class:`UpdateBehavior`
        The wrapped progress bar.
    """
    if progress_bar is None:
        progress_bar = get_default_progressbar()
    if not isinstance(progress_bar, UpdateBehavior):
        updater_class = get_default_updater_class(progress_bar)
        progress_bar = updater_class(progress_bar)
    return progress_bar
