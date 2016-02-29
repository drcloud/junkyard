from contextlib import contextmanager
import logging
import select

from psycopg2.extensions import ISOLATION_LEVEL_SERIALIZABLE
from psycopg2.extras import LoggingConnection, register_inet, register_uuid


log = logging.getLogger(__name__)

autocommit = dict(autocommit=True)
serializable_rw = dict(isolation_level=ISOLATION_LEVEL_SERIALIZABLE)
serializable_ro = dict(readonly=True, deferrable=True, **serializable_rw)


class PG(object):
    def __init__(self, dsn, logger=None, cxn_init=None):
        self.dsn = dsn
        self._log = logger or log
        self._cxn = None
        self._mode = None

    @property
    def cxn(self):
        if self._cxn is None:
            self._cxn = LoggingConnection(self.dsn)
            self._cxn.initialize(self._log)
            register_uuid()
            register_inet()
        return self._cxn

    @contextmanager
    def txn(self, readonly=False):
        mode = serializable_ro if readonly else serializable_rw
        with self.cxn:
            if self._mode != mode:
                self.cxn.set_session(**mode)
                self._mode = mode
            with self.cxn.cursor() as cursor:
                yield cursor

    def listen(self, *channels):
        with self.cxn:
            with self.cxn.cursor() as cursor:
                for channel in channels:
                    cursor.execute('LISTEN %s' % channel)

    def unlisten(self, *channels):
        with self.cxn:
            with self.cxn.cursor() as cursor:
                for channel in channels:
                    cursor.execute('UNLISTEN %s' % channel)

    def notify(self, channel, message=None):
        with self.cxn:
            with self.cxn.cursor() as cursor:
                cursor.execute('NOTIFY %s' % channel if message is None else
                               'NOTIFY %s, %s' % (channel, message))

    def await(self, upto=0.1):
        if self._mode != autocommit:
            self.cxn.set_session(**autocommit)
            self._mode = autocommit
        self.cxn.poll()
        if len(self.cxn.notifies) <= 0:
            if select.select([self.cxn], [], [], upto) == ([], [], []):
                return
            self.cxn.poll()
        notifications = []
        while len(self.cxn.notifies) > 0:
            notification = self.cxn.notifies.pop(0)
            notifications += [notification]
            self._log.debug('PID %s NOTIFY %s, %s',
                            notification.pid,
                            notification.channel,
                            notification.payload)
        return notifications
