from collections import namedtuple
from datetime import timedelta
import glob
from multiprocessing import active_children, Process, Manager
import os

from sh import mkdir

from ..dds import Envelope
from ..flock import flock, Timeout
from ..logger import log
from ..protocol import DrC
from ..protocol import run
from ..protocol import hello
from ..status import Status
from ..task import Task
from .. import time


class Rx(object):
    etc = '/etc/drcloud'
    spools = '/var/spool/drcloud'
    timeout = 10
    lifetime = timedelta(minutes=15)

    def __init__(self,
                 service=None, spools=spools, etc=etc, lifetime=lifetime):
        self.inbox = {}
        self.sent = {}
        self.pending = []
        self.spools = spools
        self.etc = etc
        self.lifetime = lifetime
        self._started = None
        self._ended = None
        self._counter = 0
        self._service = service
        self._manager = None
        self._shared = None

    def start(self):
        """Watch the spool filesystem for messages and respond to them.
        """
        if not (self._started is None or self._ended is not None):
            return
        self._started = time.utc()
        self._ended = None
        self._counter = 0
        mkdir('-p', self.i(), self.o())
        announce = Envelope(dict(channel=self.service, data=hello.Hello()))
        self.pending += [announce]
        self.manager()
        self.loop()

    def input_watcher(self):
        import inotify.adapters
        w = inotify.adapters.Inotify()
        w.add_watch(self.i(), mask=inotify.constants.IN_CREATE)
        return (event for event in w.event_gen() if event is not None)

    def out_of_time(self):
        if time.utc() - self._started >= self.lifetime:
            self._ended = time.utc()
            log.info('Reached lifetime %s after %s iterations in %s.',
                     self._counter,
                     self._ended - self._started,
                     self.lifetime)
            return True
        return False

    def loop(self):
        # We use events as a clue for when to take the lock and sync our view
        # of the on-disk inboxes, to save on CPU.
        for event in self.input_watcher().event_gen():
            if self.out_of_time():
                break
            if event is None:
                continue
            (header, types, watchroot, path) = event
            if 'IN_CREATE' not in types:
                continue
            self._counter += 1
            log.debug('Active children: %s', len(active_children()))
            self.sync()

    def sync(self):
        log.info('Locking %s', self.lock)
        with flock(self.lock, seconds=self.timeout) as handle:
            handle.seek(0)
            handle.truncate()
            handle.write(self.ident + '\n')
            ins = [os.path.basename(p) for p in glob.glob(self.i('*'))]
            outs = [os.path.basename(p) for p in glob.glob(self.o('*'))]
            for uuid in ins:
                with open(self.i(str(uuid))) as h:
                    self.inbox[uuid] = Envelope.unmarshal(h)
            for uuid in outs:
                with open(self.o(str(uuid))) as h:
                    self.sent[uuid] = Envelope.unmarshal(h)
            for envelope in self.pending:
                log.debug('Writing %s.', envelope.uuid)
                with open(self.o(str(envelope.uuid)), 'w') as h:
                    Envelope.marshal(envelope, h)
            with self.shared.lock:
                while not self.shared.pending.empty():
                    envelope = self.shared.pending.get()
                    with open(self.o(str(envelope.uuid)), 'w') as h:
                        Envelope.marshal(envelope, h)
            self.pending = []

    def handle(self, envelope):
        assert isinstance(envelope, Envelope)
        handler = Handler(envelope, self.shared.pending)
        self.shared.handlers[envelope.uuid] = handler
        handler.start()

    def manager(self):
        if self._manager is None:
            log.debug('Initializing state manager...')
            self._manager = Manager()
            # self._manager.start()
        return self._manager

    @property
    def shared(self):
        if self._shared is None:
            # Note that this namespace is not shared but rather is used to
            # organize shared resources.
            self._shared = Shared(pending=self.manager().Queue(),
                                  handlers=self.manager().dict(),
                                  lock=self.manager().Lock())
        return self._shared

    def i(self, sub=None):
        return os.path.join(self.spools, 'i', sub or '')

    def o(self, sub=None):
        return os.path.join(self.spools, 'o', sub or '')

    @property
    def lock(self):
        return os.path.join(self.spools, 'lock')

    @property
    def subsidiary_lock(self, name):
        return os.path.join(self.spools, 'locks', name)

    @property
    def ident(self):
        return 'pid %s at %s' % (os.getpid(), time.utc().isoformat())

    @property
    def service(self):
        if self._service is None:
            with open(os.path.join(self.etc, 'service')) as h:
                self._service = h.read().strip()
        return self._service


class Shared(namedtuple('Shared', 'pending handlers lock')):
    pass


def watcher(d):
    import inotify.adapters
    import inotify.constants
    w = inotify.adapters.Inotify()
    w.add_watch(d, mask=inotify.constants.IN_CREATE)
    return ((watchroot, path) for _header, _types, watchroot, path in
            (event for event in w.event_gen() if event is not None))


class Handler(object):
    """Handle a single message.
    """
    def __init__(self, envelope, q, qlock, timeout=Rx.timeout):
        self.q = q
        self.qlock = qlock
        self.envelope = envelope
        self.timeout = timeout
        self.p = None

    def start(self):
        if self.p is None:
            name = '%s/%s' % (__package__, self.envelope.uuid)
            self.p = Process(target=self.handle,
                             args=(self.envelope.message,),
                             name=name)
            self.p.run()
        return self.p

    def handle(self):
        m = self.envelope.message
        assert isinstance(m, DrC)
        if isinstance(m, run.Run):
            self.run(m.task)
        raise ValueError('Unknown message type: %s (%s)',
                         self.envelope.type,
                         m.__class__.__name__)

    def post(self, message):
        envelope = Envelope(dict(channel=self.envelope.channel,
                                 refs=[self.envelope.uuid],
                                 data=message))
        with self.qlock:
            self.q.put(envelope)

    def run(self, task):
        assert isinstance(task, Task)
        self.post(run.Status(uuid=task.uuid, status=Status.started))
        try:
            with flock(self.subsidiary_lock(task.lock), seconds=Rx.timeout):
                return task.run()
        except Timeout as e:
            self.post(run.Status(uuid=task.uuid,
                                 status=Status.failed,
                                 message=str(e)))
        self.post(run.Status(uuid=task.uuid, status=Status.success))
