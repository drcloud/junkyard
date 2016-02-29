from schematics.models import Model
from schematics.types import BaseType, BooleanType, StringType, DateTimeType
from schematics.types.compound import ModelType

from status import DeclarationStatus, SystemStatus


class Key(Model):
    """ABC for data identifying a system.
    """
    def __init__(self, *args, **kwargs):
        raise NotImplementedError()


class Spec(Model):
    """ABC for data defining a system's characteristics.

    The data always contains the key, or information sufficient to derive (not
    lookup) the key.
    """
    def __init__(self, *args, **kwargs):
        raise NotImplementedError()


class Info(Model):
    """ABC for system information.

    This never contains the key.
    """
    def __init__(self, *args, **kwargs):
        raise NotImplementedError()


class DeclarationStatusType(BaseType):
    def to_native(self, value, context=None):
        return DeclarationStatus(value)

    def to_primitive(self, value, context=None):
        return value.value


class SystemStatusType(BaseType):
    def to_native(self, value, context=None):
        return SystemStatus(value)

    def to_primitive(self, value, context=None):
        return value.value


class Declare(Model):
    """Declare a system (store the configuration thereof).
    """
    what = StringType(required=True)
    spec = ModelType(Spec, required=True)
    overwrite = BooleanType(default=False)


class DeclareResp(Model):
    code = DeclarationStatusType(required=True)
    spec = ModelType(Spec)


class Configure(Model):
    """Initiate configuration changes."""
    key = ModelType(Key, required=True)
    reflow = BooleanType(default=False)


class Retire(Model):
    """Decommission a system in an orderly manner, returning its resources."""
    key = ModelType(Key, required=True)


class Cancel(Model):
    """Decommission a system as quickly as possible."""
    key = ModelType(Key, required=True)


class Status(Model):
    """Request for system status."""
    key = ModelType(Key, required=True)


class StatusResp(Model):
    code = SystemStatusType(required=True)
    last_seen = DateTimeType(required=True)
    key = ModelType(Key, required=True)
    info = ModelType(Info)
