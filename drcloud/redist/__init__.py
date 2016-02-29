from contextlib import contextmanager
import glob
import os
import shutil
import subprocess
import sys
import tempfile

from .. import err
from ..logger import log


def source_path():
    parent = '.'.join(__package__.split('.')[:-1])
    return sys.modules[parent].__path__[0]


def setup_path():
    from . import setup
    path = setup.__file__
    if path.endswith('.pyc'):
        path = path[:-1]
    return path


@contextmanager
def redist():
    """Bundle the package for remoting.

    Using Python packaging utiltities, bundle the current package for
    installation, to support remoting.

    Returns a handle to a temporary distribution tarball.
    """
    d = tempfile.mkdtemp()
    sources, setup = source_path(), setup_path()
    shutil.copytree(sources, os.path.join(d, os.path.basename(sources)))
    shutil.copy2(setup, os.path.join(d, os.path.basename(setup)))
    with tempfile.TemporaryFile() as o, tempfile.TemporaryFile() as e:
        try:
            subprocess.check_call(['python', 'setup.py', 'sdist'],
                                  cwd=d, stdout=o, stderr=e)
        except subprocess.CalledProcessError:
            o.seek(0)
            log.error('STDOUT from failed call to `setup.py sdist`:\n%s',
                      o.read())
            e.seek(0)
            log.error('STDERR from failed call to `setup.py sdist`:\n%s',
                      e.read())
            raise
    path = None
    for p in glob.iglob(os.path.join(d, 'dist', '*.*')):
        if path is not None:
            examples = ', '.join(os.path.basename(_) for _ in [path, p])
            log.warning('Multiple dist files (%s) in `%s`.', examples, d)
            break
        path = p
    with open(path) as h:
        yield h
    shutil.rmtree(d)


class Err(err.Err):
    pass
