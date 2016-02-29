"""Communication in Dr. Cloud are based on per-service channels.
"""
import itertools
import inspect
import json
import socket
import uuid

from schematics.models import Model
from schematics.types import DateTimeType, EmailType, StringType, UUIDType
from schematics.types.compound import ListType, PolyModelType

from .dns import DomainNameType
from . import time


def default_from(height=3):
    """Makes use of inspect to infer a module name."""
    return calling_module(height) + '@' + socket.gethostname().lower()


def calling_module(n=1):
    """Find the `n`th module in this package that made the call.
    """
    name = None
    for frame in inspect.stack():
        scope = frame[0].f_globals
        if scope['__name__'].startswith(__package__ + '.'):
            if n == 0:
                name = scope['__name__']
                break
            n -= 1
    mod = name or __package__
    return [component for component in mod.split('.') if component != ''][-1]


class Message(Model):
    """Base type for all DDS messages."""
    @classmethod
    def typename(cls):
        return 'drcloud.%s' % cls.__name__


def determine_type_from_fields(polymodel, data):
    assert isinstance(polymodel, PolyModelType)
    data_fields = set(data.keys())
    subclasses = [_._subclasses for _ in polymodel.model_classes]
    for subclass in itertools.chain(*subclasses):
        fields = set(subclass._fields.keys())
        if data_fields & fields != set() and data_fields - fields == set():
            return subclass


class Envelope(Model):
    """All messages go in a standard envelope.
    """
    uuid = UUIDType(required=True, default=uuid.uuid4)
    channel = DomainNameType(required=True)
    sender = EmailType(required=True, default=default_from)
    t = DateTimeType(required=True, default=time.utc)
    refs = ListType(UUIDType(), required=True, default=list)
    data = PolyModelType(Message, claim_function=determine_type_from_fields)
    type = StringType(required=True)

    def convert(self, raw_data, **kwargs):
        """
        Override ``convert`` to ensure ``type`` is set based on the underlying
        datatype in ``data``.
        """
        result = super(Envelope, self).convert(raw_data, **kwargs)
        if 'type' not in result or result['type'] is None:
            result['type'] = result['data'].typename()
        return result

    def __str__(self):
        return 'Envelope(%s)' % Envelope.marshal(self)

    @classmethod
    def unmarshal(cls, text):
        """
        :rtype: Envelope
        """
        if hasattr(text, 'read'):
            obj = cls(json.load(text))
        else:
            obj = cls(json.loads(text))
        obj.validate()
        return obj

    @classmethod
    def marshal(cls, obj, handle=None):
        """
        :rtype: String|None
        """
        options = dict(sort_keys=True, indent=2, separators=(',', ': '))
        data = obj.to_primitive()
        if handle is None:
            return json.dumps(data, **options)
        else:
            json.dump(data, handle, **options)
