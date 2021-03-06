from collections import namedtuple
import inspect
import logging
import logging.handlers
import os
import sys
import textwrap
from types import ModuleType


def configure(logger=None, **kwargs):
    configuration = Configuration.auto(**kwargs)
    if logger is None:
        logger = logging.getLogger()
    configuration(logger)


class Configuration(namedtuple('Configuration', 'syslog console extended')):
    def __call__(self, logger):
        if isinstance(logger, basestring):
            logger = logging.getLogger(logger)
        syslog, console = norm_level(self.syslog), norm_level(self.console)
        configure_handlers(logger, syslog=syslog, console=console,
                           extended=self.extended)
        set_normed_level(logger, min(_ for _ in [syslog, console] if _))

    @classmethod
    def auto(cls, syslog=None, console=None, level=None, extended=None):
        """Tries to guess a sound logging configuration.
        """
        level = norm_level(level)
        if syslog is None and console is None:
            if sys.stderr.isatty():
                syslog, console = None, (level or logging.INFO)
                if extended is None:
                    extended = level <= logging.DEBUG
            else:
                syslog, console = (level or logging.WARNING), None
        return cls(syslog=syslog, console=console, extended=extended)


def configure_handlers(logger, syslog=None, console=None, extended=False):
    console_handler, syslog_handler = None, None
    if console is not None:
        console_handler = logging.StreamHandler()
        configure_console_format(console_handler, extended)
        if console != logging.NOTSET:
            console_handler.level = console
    if syslog is not None:
        dev = '/dev/log' if os.path.exists('/dev/log') else '/var/run/syslog'
        fmt = __package__ + '[%(process)d]: %(name)s %(funcName)s %(message)s'
        syslog_handler = logging.handlers.SysLogHandler(address=dev)
        syslog_handler.setFormatter(logging.Formatter(fmt=fmt))
        if syslog != logging.NOTSET:
            syslog_handler.level = syslog
    clear_handlers(logger)
    logger.handlers = [h for h in [console_handler, syslog_handler] if h]


def set_normed_level(logger, level):
    level = norm_level(level)
    if level is not None:
        logger.level = level


def configure_console_format(console_handler, extended=False):
    if extended:
        fmt = Formatter(datefmt='%H:%M:%S')
    else:
        fmt = logging.Formatter(fmt='%(asctime)s.%(msecs)03d %(message)s',
                                datefmt='%H:%M:%S')
    console_handler.setFormatter(fmt)


def logger(height=1):                 # http://stackoverflow.com/a/900404/48251
    """
    Obtain a function logger for the calling function. Uses the inspect module
    to find the name of the calling function and its position in the module
    hierarchy. With the optional height argument, logs for caller's caller, and
    so forth.
    """
    caller = inspect.stack()[height]
    scope = caller[0].f_globals
    path = scope['__name__'].split('__main__')[0].strip('.')
    if path == '' and scope['__package__']:
        path = scope['__package__']
    return logging.getLogger(path)


def norm_level(level):
    if level is None:
        return level
    if isinstance(level, basestring):
        return logging._levelNames[level.upper()]
    else:
        logging._levelNames[level]                         # Raise if not found
        return level


def levels():
    return {_.lower() for _ in logging._levelNames.keys()
            if isinstance(_, basestring)}


def clear_handlers(root_of_loggers):
    loggers = [root_of_loggers]
    if isinstance(root_of_loggers, logging.RootLogger):
        loggers = logging.Logger.manager.loggerDict.values()
    else:
        for name, logger in logging.Logger.manager.loggerDict.items():
            if name.startswith(root_of_loggers.name + '.'):
                loggers += [logger]
    for logger in loggers:
        logger.handlers = []


try:
    _null_handler = logging.NullHandler()
except:
    # Python 2.6 compatibility
    class NullHandler(logging.Handler):
        def emit(self, record):
            pass
    _null_handler = NullHandler()


# Configure the package logger with a null handler so that we don't crash due
# to logging with no handlers.
root = logging.getLogger(__package__)
root.handlers = [_null_handler]


class Formatter(logging.Formatter):
    wrapper = textwrap.TextWrapper(drop_whitespace=True,
                                   initial_indent='  ',
                                   subsequent_indent='  ',
                                   break_long_words=False,
                                   break_on_hyphens=False,
                                   width=76)

    def format(self, rec):
        """
        :type rec: logging.LogRecord
        """
        t = self.formatTime(rec, self.datefmt)
        func = '' if rec.funcName == '<module>' else ' %s()' % rec.funcName
        left_header_data = (t, rec.msecs, rec.name, func, rec.lineno)
        left_header = '%s.%03d %s%s @ %d' % left_header_data
        right_header = rec.levelname.lower()
        spacer = 79 - 4 - len(left_header) - len(right_header)
        top_line = left_header + ' -' + spacer * '-' + '- ' + right_header
        lines = [_ for __ in textwrap.dedent(rec.getMessage()).splitlines()
                 for _ in self.wrapper.wrap(__)]

        # This is more or less the logic in logging.Formatter.format() for
        # exception logging, though greatly condensed.
        if rec.exc_info:
            exc_text = super(Formatter, self).formatException(rec.exc_info)
            exc_lines = exc_text.splitlines()
            # if len(exc_lines) > 4:
            #     exc_lines = exc_lines[:2] + ['...'] + exc_lines[-2:]
            lines += [''] + ['  ' + l for l in exc_lines]

        return top_line + '\n' + '\n'.join(l for l in lines)


# This is how we overload `import`. Modelled on Andrew Moffat's `sh`.
class ImportWrapper(ModuleType):
    def __init__(self, module):
        self._module = module

        # From the original -- these attributes are special.
        for attr in ['__builtins__', '__doc__', '__name__', '__package__']:
            setattr(self, attr, getattr(module, attr, None))

        # Path settings per original -- seemingly obligatory.
        self.__path__ = []

    def __getattr__(self, name):
        if name == 'log':
            return logger(2)
        else:
            return getattr(self._module, name)


self = sys.modules[__name__]
sys.modules[__name__] = ImportWrapper(self)
