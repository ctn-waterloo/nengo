from __future__ import absolute_import, division

from datetime import timedelta
import os
import sys
import time
import warnings

import numpy as np

from nengo.utils.compat import get_terminal_size


try:
    from IPython.html import widgets
    from IPython.display import display, Javascript
    import IPython.utils.traitlets as traitlets
    _HAS_WIDGETS = True
except ImportError:
    _HAS_WIDGETS = False


class MemoryLeakWarning(UserWarning):
    pass


warnings.filterwarnings('once', category=MemoryLeakWarning)


class Progress(object):
    def __init__(self, max_steps, observers=None):
        self.steps = 0
        self.max_steps = max_steps
        self.start_time = self.end_time = time.time()
        self.finished = False
        self.success = None
        if observers is None:
            self.observers = []
        else:
            self.observers = observers

    @property
    def progress(self):
        return self.steps / self.max_steps

    @property
    def seconds_passed(self):
        if self.finished:
            return self.end_time - self.start_time
        else:
            return time.time() - self.start_time

    @property
    def eta(self):
        if self.progress > 0.:
            return (1. - self.progress) * self.seconds_passed / self.progress
        else:
            return -1

    def __enter__(self):
        self.finished = False
        self.success = None
        self.steps = 0
        self.start_time = time.time()
        self.notify_observers()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.success = exc_type is None
        if self.success:
            self.steps = self.max_steps
        self.end_time = time.time()
        self.finished = True
        self.notify_observers()

    def step(self, n=1):
        self.steps = min(self.steps + n, self.max_steps)
        self.notify_observers()

    def notify_observers(self):
        for o in self.observers:
            o.update(self)


class ProgressBar(object):
    def update(self, progress):
        raise NotImplementedError()


class NoProgressBar(ProgressBar):
    def update(self, progress):
        pass


class CmdProgressBar(ProgressBar):
    def __init__(self):
        super(CmdProgressBar, self).__init__()
        if _in_ipynb():
            warnings.warn(MemoryLeakWarning((
                "The {cls} continuously adds invisible content to the "
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
        line = "[{{}}] ETA: {eta}".format(eta=timedelta(
            seconds=np.ceil(progress.eta)))
        percent_str = " {}% ".format(int(100 * progress.progress))

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
        line = "Done in {}.".format(
            timedelta(seconds=np.ceil(progress.seconds_passed))).ljust(width)
        return '\r' + line + os.linesep


if _HAS_WIDGETS:
    class IPythonProgressWidget(widgets.DOMWidget):
        # pylint: disable=too-many-public-methods
        _view_name = traitlets.Unicode('NengoProgressBar', sync=True)
        progress = traitlets.Float(0., sync=True)
        text = traitlets.Unicode(u'', sync=True)

        FRONTEND = Javascript('''
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
        });''')

        def _ipython_display_(self, **kwargs):
            display(self.FRONTEND)
            widgets.DOMWidget._ipython_display_(self, **kwargs)


class IPython2ProgressBar(ProgressBar):
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
            self._widget.text = "Done in {}.".format(
                timedelta(seconds=np.ceil(progress.seconds_passed)))
        else:
            self._widget.text = "{progress:.0f}%, ETA: {eta}".format(
                progress=100 * progress.progress,
                eta=timedelta(seconds=np.ceil(progress.eta)))


class LogSteps(ProgressBar):
    def __init__(self, logger):
        self.logger = logger
        super(LogSteps, self).__init__()

    def update(self, progress):
        if progress.finished:
            self.logger.debug(
                "Simulation done in %s.",
                timedelta(seconds=np.ceil(progress.seconds_passed)))
        else:
            self.logger.debug("Step %d", progress.steps)


class AutoProgressBar(ProgressBar):
    def __init__(self, delegate, min_eta=1.):
        self.delegate = delegate

        super(AutoProgressBar, self).__init__()

        self.min_eta = min_eta
        self._visible = False

    def update(self, progress):
        min_delay = progress.start_time + 0.1
        if self._visible:
            self.delegate.update(progress)
        elif progress.eta > self.min_eta and min_delay < time.time():
            self._visible = True
            self.delegate.update(progress)


class MaxNUpdater(object):
    def __init__(self, progress_bar, max_updates=100):
        self.progress_bar = progress_bar
        self.max_updates = max_updates
        self.last_update_step = 0

    def update(self, progress):
        next_update_step = (self.last_update_step +
                            progress.max_steps / self.max_updates)
        if next_update_step < progress.steps or progress.finished:
            self.progress_bar.update(progress)
            self.last_update_step = progress.steps


class EveryNUpdater(object):
    def __init__(self, progress_bar, every_n=1000):
        self.progress_bar = progress_bar
        self.every_n = every_n
        self.next_update = every_n

    def update(self, progress):
        if self.next_update <= progress.steps or progress.finished:
            self.progress_bar.update(progress)
            assert self.every_n > 0
            self.next_update = progress.steps + self.every_n


class IntervalUpdater(object):
    def __init__(self, progress_bar, update_interval=0.05):
        self.progress_bar = progress_bar
        self.next_update = 0
        self.update_interval = update_interval

    def update(self, progress):
        if self.next_update < time.time() or progress.finished:
            self.progress_bar.update(progress)
            self.next_update = time.time() + self.update_interval


def _in_ipynb():
    try:
        cfg = get_ipython().config  # pylint: disable=undefined-variable
        app_key = 'IPKernelApp'
        if 'parent_appname' not in cfg[app_key]:
            app_key = 'KernelApp'  # was used by old IPython versions
        if cfg[app_key]['parent_appname'] == 'ipython-notebook':
            return True
    except NameError:
        pass
    return False


def get_default_progressbar():
    if _in_ipynb() and _HAS_WIDGETS:  # IPython >= 2.0
        return AutoProgressBar(IPython2ProgressBar())
    else:  # IPython < 2.0
        return AutoProgressBar(CmdProgressBar())


def get_default_updater_class(progress_bar):
    if _in_ipynb() and not isinstance(progress_bar, IPython2ProgressBar):
        return MaxNUpdater
    else:
        return IntervalUpdater


def create_progress_bar(progress_bar=None, updater_class=None):
    if progress_bar is None:
        progress_bar = get_default_progressbar()
    if updater_class is None:
        updater_class = get_default_updater_class(progress_bar)
    return updater_class(progress_bar)
