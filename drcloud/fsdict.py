from collections import MutableMapping
from contextlib import contextmanager
import errno
from fcntl import flock, LOCK_EX, LOCK_NB, LOCK_SH, LOCK_UN
import itertools
import os
import signal
from threading import RLock


from .logger import log


class FSDict(MutableMapping):
    def __init__(self, path, textual=True, timeout_millis=10):
        self.path = path
        self.textual = textual
        self.timeout_millis = timeout_millis
        self._lk = RLock()
        self._fd = None
        self._flags = LOCK_UN
        self._flags_stack = []

    @property
    @contextmanager
    def exclusive(self):
        with self._with() as self:
            yield self

    @property
    @contextmanager
    def shared(self):
        with self._with(shared=True) as self:
            yield self

    @contextmanager
    def _with(self, shared=False):
        self._lock_in(shared=shared)
        yield self
        try:
            self._lock_out()
        except:
            if self._fd is not None:
                os.close(self._fd)
            raise

    # Implement safe locking of this object and the underlying directory. By
    # locking the underlying directory with `flock`, we allow multiple
    # processes to share it safely, either via this library or through external
    # calls to `flock`.

    def _lock_in(self, shared=False):
        with self._lk:
            flags = LOCK_SH if shared else LOCK_EX
            self._flags_stack += [flags]
            if self._flags != LOCK_EX:         # Don't give up EX on the way in
                self._flock(flags)

    def _lock_out(self):
        with self._lk:
            self._flags_stack = self._flags_stack[:-1]
            if self._fd is not None:
                flags = ([LOCK_UN] + self._flags_stack)[-1]
                self._flock(flags)  # It's okay to give up locks on the way out

    def _flock(self, flags):
        with self._lk:
            self._try_to_open_path()
            if self._fd is not None and self._flags != flags:
                log.debug('Lock (%s -> %s) on: %s',
                          fmt_flock(self._flags),
                          fmt_flock(flags),
                          self.path)
                with timeout_in_syscalls(self.timeout_millis / 1000.0):
                    flock(self._fd, flags)
                    self._flags = flags

    def _try_to_open_path(self):
        if self._fd is None:
            try:
                self._fd = os.open(self.path, os.O_RDONLY)
            except OSError as e:
                if e.errno != errno.ENOENT:
                    raise

    def _ensure_path(self):
        mkdir_p(os.path.dirname(self.path))

    def _blind_write(self, path, text):
        if self.textual:
            text = text.strip() + '\n'
        with open(os.path.join(self.path, path), 'w') as h:
            return h.write(text)

    def __getitem__(self, path):
        if not isinstance(path, basestring):
            raise ValueError('FSDicts accept only string keys.')
        with self.shared:
            try:
                with open(os.path.join(self.path, path)) as h:
                    return h.read().strip() if self.textual else h.read()
            except IOError as e:
                if e.errno != errno.ENOENT:
                    raise

    def __setitem__(self, path, data):
        if not isinstance(path, basestring):
            raise ValueError('FSDicts accept only string keys.')
        if data is None:
            self.__delitem__(path)
            return
        if not isinstance(data, basestring):
            raise ValueError('FSDicts accept only string values.')
        self._ensure_path()
        with self.exclusive:
            try:
                self._blind_write(path, data)
                return
            except IOError as e:
                if e.errno != errno.ENOENT:
                    raise
            mkdir_p(os.path.dirname(os.path.join(self.path, path)))
            self._blind_write(path, data)

    def __delitem__(self, path):
        with self.exclusive:
            try:
                os.unlink(os.path.join(self.path, path))
            except OSError as e:
                if e.errno != errno.ENOENT:
                    raise

    def __iter__(self):
        with self.shared:
            self_path_with_slash = os.path.join(self.path, '')
            walker = os.walk(self.path, followlinks=True)
            paths = [(os.path.join(d, f).split(self_path_with_slash, 1)[1]
                      for f in fs)
                     for d, _, fs in walker]
            return iter(sorted(itertools.chain(*paths), key=split_path))

    def __len__(self):
        return len(iter(self))

    def __contains__(self, path):
        with self.shared:
            return os.path.exists(os.path.join(self.path, path))


def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as e:
        if e.errno != errno.EEXIST or not os.path.isdir(path):
            raise


def split_path(path):
    return path.split('/')


def fmt_flock(flags):
    labels = dict(EX=LOCK_EX, NB=LOCK_NB, SH=LOCK_SH, UN=LOCK_UN)
    return '|'.join(s for s, f in sorted(labels.items()) if (flags & f) != 0)


@contextmanager
def timeout_in_syscalls(seconds):
    def do_nothing_handler(signum, frame):
        pass
    previous_handler = signal.signal(signal.SIGALRM, do_nothing_handler)
    previous_itimer_values = None
    try:
        previous_itimer_values = signal.setitimer(signal.ITIMER_REAL, seconds)
        yield
    finally:
        if previous_itimer_values is not None:
            signal.setitimer(signal.ITIMER_REAL, *previous_itimer_values)
        signal.signal(signal.SIGALRM, previous_handler)
