import sys
from types import ModuleType


class Event(object):
    pass


class Info(Event):
    pass


class Notice(Event):
    """To be used for notifications."""
    pass


class Error(Event):
    """Failure in application."""
    pass


class Warning(Event):
    pass


class UserFacingError(Event):
    """Errors users should see and understand."""
    pass


class Debug(Event):
    """Debugging information."""
    pass


class Trace(Event):
    """Low level debugging information."""
    pass


class Audit(Event):
    """Data store for auditing purposes. Never logged."""
    pass


class Panic(Event):
    """Component failure."""
    pass


class End(Event):
    """Completion of a task or component."""
    pass


class Start(Event):
    """Startup of a task or component."""
    pass


class Bug(Event):
    """Events that should never occur outside of a bug."""
    pass


class Data(Event):
    """Event data to be stored for application use. Not generally logged."""
    pass


# This is how we overload `import`. Modelled on Andrew Moffat's `sh`.
class ImportWrapper(ModuleType):
    def __init__(self, module):
        self._module = module

        # From the original -- these attributes are special.
        for attr in ['__builtins__', '__doc__', '__name__', '__package__']:
            setattr(self, attr, getattr(module, attr, None))

        # Path settings per original -- seemingly obligatory.
        self.__path__ = []

    def __getattr__(self, name):
        if name in ['panic', 'alert', 'error', 'notice',
                    'info', 'debug', 'trace',
                    'audit', 'data']:
            return None
        else:
            return getattr(self._module, name)


self = sys.modules[__name__]
sys.modules[__name__] = ImportWrapper(self)
