#!/usr/bin/env python
from __future__ import absolute_import
import os
import sys

import click
import ptpython.ipython
import ptpython.repl

from . import logger
from .logger import log

from .conf.lld import LayeredLocalDirs


@click.group(invoke_without_command=True)
@click.pass_context
@click.option('-d', '--debug', is_flag=True,
              help='Shortcut to enable debug log level.')
@click.option('--syslog', type=click.Choice(logger.levels()),
              default='notset', help='Syslog log level.')
@click.option('--console', type=click.Choice(logger.levels()),
              default='notset', help='Console log level.')
@click.option('-u', '--using', type=(str, str), multiple=True,
              help='Pass individual configuration parameters.')
@click.option('-c', '--conf-dir', type=str, default=None,
              help=('Sets the configuration directory. Note that this is '
                    'merged with some others; but whatever is set in this '
                    'directory is preferred to the alternatives. For the '
                    '`config` subcommand, this directory will be used for '
                    'writing. If not set, the value is determined based on '
                    'the present (not effective) user ID. For root, the '
                    'writable config hierarchy is /etc/drcloud; for all other '
                    'users it is ~/.config/drcloud.'))
def drcloud(ctx, debug=False, syslog='notset', console='notset',
            using=[], conf_dir=None):
    debug = 'debug' if debug else None
    syslog = syslog if syslog != 'notset' else None
    console = console if console != 'notset' else None
    logger.configure(level=debug, console=console, syslog=syslog)
    if conf_dir is not None:
        ctx.conf = LayeredLocalDirs(writable=conf_dir)
    else:
        ctx.conf = LayeredLocalDirs()
    ctx.using = using
    if ctx.invoked_subcommand is None:
        load_ipython()


@drcloud.command()
@click.pass_context
@click.option('-s', '--setting', type=(str, str), multiple=True,
              help='Store changes to configuration parameters.')
@click.option('-c', '--conf-dir', type=str, default=None,
              help=('Set the target for configuration writes, independent of '
                    'the main `-c` setting.'))
def config(ctx, setting=[], conf_dir=None):
    if conf_dir is not None:
        conf = LayeredLocalDirs(writable=conf_dir)
    else:
        conf = ctx.parent.conf
    with conf._writer.exclusive:
        if len(setting) <= 0:
            for k, v in conf.items():
                print k
                print v
        for k, v in setting:
            conf[k] = v


@drcloud.command()
def console():
    load_ipython()


def load_ipython():
    config_dir = os.path.expanduser('~/.ptpython/')
    history = os.path.join(config_dir, 'drcloud.history')

    # Recycle the user's ptpython configuration.
    def configure(repl):
        path = os.path.join(config_dir, 'config.py')
        if os.path.exists(path):
            ptpython.repl.run_config(repl, unicode(path))

    # Create config directory.
    if not os.path.isdir(config_dir):
        os.mkdir(config_dir)

    # Add the current directory to `sys.path`.
    if sys.path[0] != '':
        sys.path.insert(0, '')

    ptpython.repl.enable_deprecation_warnings()

    ptpython.ipython.embed(history_filename=history,
                           configure=configure,
                           user_ns=ns(),
                           title=unicode('IPython / Dr. Cloud'))


def ns():
    module = sys.modules['drcloud']
    # Expand bindings as though user had run ``from drcloud import *``.
    exports = {k: module.__dict__[k] for k in module.__all__}
    return dict(drcloud=module, log=log, **exports)


def main():
    drcloud()


if __name__ == '__main__':
    main()
