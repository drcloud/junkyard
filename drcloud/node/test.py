from datetime import timedelta
from glob import glob

from nose import with_setup
from sh import rm

from ..protocol.hello import Hello
from ..dds import Envelope
from .. import logger
from ..logger import log
from . import Agent


test_dir = 'tmp/spools'


def clear_test_dir():
    rm('-rf', test_dir)


@with_setup(setup=clear_test_dir)
def test_runs_at_all():
    rx = Agent(service='test.example.com',
               spools='tmp/spools',
               lifetime=timedelta(milliseconds=100))
    rx.start()
    messages = list(glob(rx.o('*')))
    assert len(messages) > 0, 'No Hello message was generated on startup.'
    hellos = []
    for path in messages:
        with open(path) as h:
            loaded = Envelope.unmarshal(h)
            if isinstance(loaded.data, Hello):
                hellos += [loaded]
    assert len(hellos) == 1, 'No Hello (or too many).'
    log.info('Loaded: %s', hellos[0])


def setup():
    logger.configure()
