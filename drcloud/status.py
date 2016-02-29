from enum import Enum

from schematics.exceptions import ValidationError
from schematics.types import BaseType


class Status(str, Enum):
    waiting = 'waiting'
    started = 'started'
    success = 'success'
    failure = 'failure'


class StatusType(BaseType):
    def to_native(self, value, context=None):
        if isinstance(value, Status):
            return value
        if value not in Status.__members__:
            raise ValidationError('Not a valid Status: %s' % value)
        return Status.__members__[value]

    def to_primitive(self, value, context=None):
        return str(value)
