from contextlib import contextmanager
import errno
import fcntl
import signal

from . import err
from .logger import log


@contextmanager
def flock(path, flags=None, seconds=None):
    flags = sort_out_flag_defaults(path, flags, seconds)
    with open(path, 'a+') as handle:
        if (flags & fcntl.LOCK_NB) != 0:
            try:
                fcntl.flock(handle, flags)
            except IOError as e:
                if e.errno not in [errno.EACCES, errno.EAGAIN]:
                    raise e
                raise Locked(path)
        else:
            with timeout(seconds):
                try:
                    fcntl.flock(handle, flags)
                except IOError as e:
                    errnos = [errno.EINTR, errno.EACCES, errno.EAGAIN]
                    if e.errno not in errnos:
                        raise e
                    raise Timeout(path)
        yield handle
        log.debug('Unlocking %s.', path)


def sort_out_flag_defaults(path, flags=None, seconds=None):
    if seconds is None:
        if flags is None:
            flags = fcntl.LOCK_NB | fcntl.LOCK_EX
        log.debug('Locking %s with flags %s.', path, format_lock_flags(flags))
    else:
        if flags is None:
            flags = fcntl.LOCK_EX
        if (flags & fcntl.LOCK_NB) != 0:
            raise Err('LOCK_NB and a timeout are contradictory.')
        log.debug('Locking %s with flags %s (waiting for %ss).',
                  path, format_lock_flags(flags), seconds)
    return flags


@contextmanager
def timeout(seconds):
    """Raise if we run out of time.

    Due to Glenn Maynard: http://stackoverflow.com/a/5255473/48251
    """
    def timeout_handler(signum, frame):
        pass
    original_handler = signal.signal(signal.SIGALRM, timeout_handler)
    try:
        signal.alarm(seconds)
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, original_handler)


def format_lock_flags(flags):
    labels = dict(EX=fcntl.LOCK_EX, SH=fcntl.LOCK_SH,
                  UN=fcntl.LOCK_UN, NB=fcntl.LOCK_NB)
    return '|'.join(s for s, f in sorted(labels.items()) if (flags & f) != 0)


class Err(err.Err):
    pass


class Timeout(Err):
    pass


class Locked(Err):
    pass
