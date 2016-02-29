import socket

from netaddr import AddrFormatError, IPAddress
from schematics.exceptions import ConversionError
from schematics.types import BaseType


class IPType(BaseType):
    def to_native(self, value, context=None):
        return convert(value)

    def to_primitive(self, value, context=None):
        return str(value)


class IPv4Type(IPType):
    def to_native(self, value, context=None):
        return convert(value, version=4)


class IPv6Type(IPType):
    def to_native(self, value, context=None):
        return convert(value, version=6)


def convert(value, version=None):
    try:
        return IPAddress(value, version)
    except AddrFormatError as e:
        raise ConversionError(str(e))


def default_ip():
    # Per Collin Anderson: http://stackoverflow.com/a/25850698/48251
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(('8.8.8.8', 1))
    return IPAddress(s.getsockname()[0])
