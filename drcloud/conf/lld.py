from collections import MutableMapping
import os


from .. import dns
from ..fsdict import FSDict, split_path


def default_writable():
    if os.getuid() == 0:
        return etc
    else:
        return userdir()


def userdir():
    return os.path.join(os.path.expanduser('~'), '.config/drcloud')


etc = '/etc/drcloud'


class LayeredLocalDirs(MutableMapping):
    def __init__(self,
                 paths=[userdir(), etc],
                 writable=default_writable(),
                 timeout_millis=200):
        self._writer = FSDict(writable, timeout_millis=timeout_millis)
        self._readers = []
        if writable not in paths:
            self._readers += [self._writer]
        for path in paths:
            self._readers += [FSDict(path, timeout_millis=timeout_millis)]

    def __getitem__(self, key):
        path = LayeredLocalDirs.key_to_path(key)
        if '!/' + path in self._writer:
            return
        for reader in self._readers:
            if path in reader:
                return reader[path]

    def __setitem__(self, key, value):
        path = LayeredLocalDirs.key_to_path(key)
        self._writer[path] = value
        del self._writer['!/' + path]

    def __delitem__(self, key):
        path = LayeredLocalDirs.key_to_path(key)
        del self._writer[path]
        self._writer['!/' + path] = ''

    def __iter__(self):
        paths = set()
        negated = {path[2:] for path in self._writer.keys()
                   if path.startswith('!/')}
        for reader in self._readers:
            for path in reader.keys():
                if path in paths or path in negated:
                    continue
                paths |= set([path])
        keys = [LayeredLocalDirs.path_to_key(path) for path in paths]
        return iter(sorted(keys, key=split_path))

    def __len__(self):
        return len(iter(self))

    def __contains__(self, key):
        path = LayeredLocalDirs.key_to_path(key)
        for reader in self._readers:
            if path in reader and '!/' + path not in self._writer:
                return True

    @staticmethod
    def path_to_key(path):
        key = path.replace('/', '.')
        if not dns.validate(key):
            raise ValueError('Only dotted names with hyphens are accepted.')
        return key

    @staticmethod
    def key_to_path(key):
        if not dns.validate(key):
            raise ValueError('Only dotted names with hyphens are accepted.')
        return key.replace('.', '/')
