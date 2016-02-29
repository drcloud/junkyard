"""The ``hello`` protocol describes how nodes come online and go offline.
"""
import socket

from schematics.types import IntType

from . import DrC, Rx
from ..dns import DomainNameType
from ..ip import IPType, IPv6Type, default_ip


class Hello(Rx):
    """Nodes announce themselves to Dr. Cloud."""
    fqdn = DomainNameType(required=True, default=socket.gethostname().lower())
    ip = IPType(required=True, default=default_ip)


class Hi(DrC):
    """Dr. Cloud accepts a node and informs it of its name and IP and service
       IP.

    The name (its true name) may be the same as what it originally sent; as may
    be its IP. Its service IP may also be known to it already, as well.
    """
    service = DomainNameType(required=True)
    name = DomainNameType(required=True)
    service_ip = IPv6Type(required=True)
    ip = IPv6Type(required=True)


class Chill(DrC):
    """Dr. Cloud informs a node that it should pause for a spell and refresh
       Rx."""
    seconds = IntType(default=10)
