"""The request board consists of a concurrent map and a sync thread.
"""
import logging
import multiprocessing

from psycopg2.extras import Json

from .queries import Queries, Annotator
from ..time import ticks


log = logging.getLogger(__name__)

requests = Annotator('requests.sql')


class Requests(object):
    def __init__(self, dsn, user=None):
        self.user = user
        self.dsn = dsn
        self._db = None

    def start(self):
        self._manager = multiprocessing.Manager()
        self._pending = self._manager.dict()
        self._events = self._manager.dict()
        self._requests = self._manager.dict()
        self._syncer = multiprocessing.Process(target=self.monitor_db)
        self._syncer.start()

    @property
    def db(self):
        if self._db is None:
            self._db = DB(self.dsn, logger=log)
        return self._db

    def refresh(self):
        requests = self.db.refresh(self.user)
        self._requests.update({item['request']: item for item in requests})

    def sync(self):
        requests, events = self.db.submit_requests_and_sync_events(
            requests=[Json(req.to_primitive()) for req in self._pending],
            ids=self._requests.keys()
        )
        self._requests.update({item['request']: item for item in requests})
        self._events.update({item['event']: item for item in events})

    def monitor_db(self):
        self.db.refresh()
        for tick in ticks(0.1):
            if len(self._pending) != 0 or self.db.await(upto=0.1):
                self.sync()


class DB(Queries):
    @requests.sql
    def init(self):
        """Initialize schema search path."""

    @requests.sql
    def listen(self, ids):
        """Subscribe to changes for the given IDs."""

    @requests.sql
    def sync(self, requests, ids):
        """Submit new requests and gather event data."""

    @requests.sql
    def refresh(self, user=None):
        """Submit new requests and gather event data."""

    @requests.sql
    def server_time(self):
        """Fetch server time stamp."""

    def await(self, *args, **kwargs):
        """Wait for updates."""
        notifications = self._pg.await(*args, **kwargs)
        return len(notifications) > 0
