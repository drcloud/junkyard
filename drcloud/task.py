"""Task model for commands run on nodes.

Tasks are intended to allow "system administration" (installing packages,
transferring files, managing services and kernel parameters) and execution of
programs in support of installing and managing user programs.

A task is always under a lock. Tasks under different locks may be run in
parallel; those under the same lock are run in serial order. This allows on to
prevent interleaving of tasks sent in different messages.

Tasks may be one or many commands and may have labels.
"""
import binascii
from collections import OrderedDict
from fnmatch import fnmatchcase
import os
import subprocess
import tempfile

from schematics.models import Model
from schematics.types import BaseType, BooleanType, StringType
from schematics.types.compound import DictType, ListType, ModelType

from .dns import DomainNameType
from .logger import log


class CmdWordType(BaseType):
    def to_native(self, value, context=None):
        return CmdWord.parse(value)

    def to_primitive(self, value, context=None):
        return value.s


class TaskOptionType(BaseType):
    def to_native(self, value, context=None):
        return TaskOptions.parse(value)

    def to_primitive(self, value, context=None):
        return value.s


class Cmd(Model):
    word = CmdWordType(required=True)
    args = ListType(StringType())
    formerly = ListType(StringType())

    def run(self, **kwargs):
        return self.word(*self.args, **kwargs)


class Task(Model):
    """
    :ivar lock: Tasks which are "alike" and should be queued up behind each
                other should use the same lock.
    :ivar label: The label is used to tag all relevant logs. (Defaults to the
                 lock name.)
    :ivar code: A list of commands to run, including internal special commands
                like ``//env``.
    :ivar options: Options to apply to commands, as key value pairs. The keys
                   are glob expressions that match command names or URLs in the
                   the ``code`` array. The values are arrays of option strings.
    """
    lock = DomainNameType(required=True, default='run')
    label = StringType()
    code = ListType(ModelType(Cmd), required=True)
    options = DictType(TaskOptionType())

    class Options:
        serialize_when_none = False

    def run(self):
        for cmd in self.code:
            log.debug('Running %s', cmd)
            options = TaskOptions()
            if self.options is not None:
                for pattern, opts in self.options.items():
                    if fnmatchcase(cmd.word.s, pattern):
                        options = opts
            cmd.run(**(options.to_native() or {}))


class TaskOptions(Model):
    insecure_download = BooleanType()

    class Options:
        serialize_when_none = False


class CmdWord(Model):
    """
    :ivar s: Command word string.
    :ivar type s: str
    :ivar options: Options to control execution.
    :ivar type: List[TaskOption]
    """
    def __init__(self, s):
        self.s = s
        self._validate()

    def __call__(self, *args, **kwargs):
        raise NotImplementedError('%s is abstract!' % self.__class__.__name__)

    def __str__(self):
        return self.s

    def _validate(self):
        """Overridden in subclasses."""
        raise NotImplementedError('%s is abstract!' % self.__class__.__name__)

    @staticmethod
    def parse(s):
        try:
            return URL(s)
        except AssertionError:
            pass
        try:
            return Internal(s)
        except AssertionError:
            pass
        return System(s)


class System(CmdWord):
    def _validate(self):
        assert '//' not in self.s

    def __call__(self, *args, **kwargs):
        subprocess.check_call([self.s] + list(args))


class URL(CmdWord):
    def _validate(self):
        assert '://' in self.s

    def __call__(self, *args, **kwargs):
        assert 'url' not in kwargs
        for word, f in reversed(Internal.handlers.items()):
            if self.s.startswith(word):
                return f(url=self.s, *args, **kwargs)
        raise NotImplementedError('No handler for %s URLs.',
                                  self.s.split('://')[0])

    handlers = OrderedDict()


class Internal(CmdWord):
    def _validate(self):
        assert self.s.startswith('//')

    def __call__(self, *args, **kwargs):
        for word, f in Internal.handlers.items():
            if word == self.s:
                return f(*args, **kwargs)

    handlers = OrderedDict()


def handler(*patterns):
    def wrapper(f):
        for pattern in patterns:
            if pattern.startswith('//'):
                Internal.handlers[pattern] = f
                continue
            if '://' in pattern:
                URL.handlers[pattern] = f
                continue
            raise ValueError('Bad pattern: %s', pattern)
        return f
    return wrapper


@handler('//env')
def env(key, value):
    os.environ[key] = value
    # TODO: Allow retrieval of values as URLs.


@handler('//source')
def source(something):
    """This is awesome. Source a URL, a file, whatever.
    """
    # How to source? It's impossible. It's like: we fork, run bash, run
    # ourselves in the environment set up by Bash.
    raise NotImplementedError('Impossible.')


@handler('//cd')
def cd(d):
    os.chdir(d)


@handler('//cd+')
def cd_expand(d):
    os.chdir(os.path.expandvars(os.path.expanduser(d)))


@handler('//x')
def x(code, *args):
    with tempfile.NamedTemporaryFile(suffix='.drcloud') as h:
        os.chmod(h.name, 0750)
        h.write(binascii.unhexlify(''.join(code.splitlines())))
        h.flush()
        subprocess.check_call([h.name] + list(args))


@handler('https://')
def https(url=None, insecure_download=False, *args):
    return curlx(url=url, options=['--insecure'], *args)


@handler('http://')
def http(url=None, *args):
    return curlx(url=url, *args)


def curlx(url=None, options=[], *args):
    with tempfile.NamedTemporaryFile(suffix='.drcloud') as h:
        os.chmod(h.name, 0750)
        curl = ['curl', '-o', h.name, '--retry', 2, '-sSfL'] + options + [url]
        subprocess.check_call(curl)
        subprocess.check_call([h.name] + list(args))


@handler('s3://')
def s3x(url=None, *args):
    with tempfile.NamedTemporaryFile(suffix='.drcloud') as h:
        os.chmod(h.name, 0750)
        subprocess.check_call(['aws', 's3', 'cp', url, h.name])
        subprocess.check_call([h.name] + list(args))
