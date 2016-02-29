import time
import uuid


class Ledger(object):
    """System objects write to and read from the ledger.

    Writes to the ledger are forwarded from the client to workers, by way of a
    stable state store. As the underlying state updates, these changes find
    their way back into the ledger for the local objects to read.
    """
    def __init__(self, conninfo, namespace=None, id=None):
        self._conninfo = conninfo
        self._namespace = namespace
        self.id = id or uuid.uuid4()

    def write(self, key, value):
        raise NotImplementedError()

