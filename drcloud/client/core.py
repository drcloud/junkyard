class System(object):
    def __init__(self):
        raise NotImplementedError()

    def configure(self, redo=False):
        """Initiate system startup and configuration.

        Use ``.stabilize()`` to wait for startup to finish. Separating calls
        to ``.configure()`` and ``.stabilize()`` allows many systems to be
        started in parallel.
        """
        raise NotImplementedError()

    def retire(self, timeout=None):
        """Release system resources in an orderly manner.

        If the system is in the middle of starting, it will finish startup,
        stabilize and then shutdown.
        """
        raise NotImplementedError()

    def stabilize(self, timeout=None):
        """Wait for system state to catch up with specification.
        """
        raise NotImplementedError()

    def cancel(self):
        """Release system resources with all haste.
        """
        raise NotImplementedError()

    def status(self):
        """Describes system status with a short status code.
        """
        raise NotImplementedError()

