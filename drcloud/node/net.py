"""Rx's understanding of the network.

From the agent's point of view, what is to be done with the network is a) to
translate names to IPv6 addresses and b) to NAT from a service IP any number
of underlying node IPs.
"""
from collections import namedtuple
import re

from netaddr import IPAddress


class Mappings(object):
    """Mappings of names to logical IPs and logical IPs to upstreams.

    Updating this class or its members will break internal invariants.

    :ivar type names: dict[FQDN, IPv6]
    :ivar type forwards: dict[IPv6, list[IP]]
    """
    def __init__(self, names, forwards):
        assert set(names.values()) == set(forwards.keys())
        self.names = names
        self.forwards = forwards
        self.ips_to_names = {v: k for k, v in names.items()}


class FQDN(namedtuple('FQDN', 'fqdn')):
    """A fully-qualified, lower-case domain name.

    :ivar type fqdn: str
    """
    def __new__(cls, fqdn):
        fqdn = fqdn.strip('.')
        assert FQDN.validate(fqdn)
        return super(FQDN, cls).__new__(cls, fqdn)

    def __str__(self):
        return self.fqdn.strip('.')

    @staticmethod
    def validate(dn):
        if dn.endswith('.'):
            dn = dn[:-1]
        if len(dn) < 1 or len(dn) > 253:
            return False
        ldh_re = re.compile('^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$')
        return all(ldh_re.match(x) for x in dn.split('.'))


class IP(IPAddress):
    pass


class IPv6(IP):
    def __init__(self, *args, **kwargs):
        super(IPv6, self).__init__(*args, **kwargs)
        assert self.version == 6


class IPv4(IP):
    def __init__(self, *args, **kwargs):
        super(IPv4, self).__init__(*args, **kwargs)
        assert self.version == 4


class LocalNet(object):
    """Setup routes and names for a local configuration.

    Subclasses use IPTables, PF, &c.
    """
    def configure(self, mappings):
        """Reconfigure the local network with these names and routes.

        Old routes and names are removed.

        :type mappings: Mappings
        """
        raise NotImplementedError()
