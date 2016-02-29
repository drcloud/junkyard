# coding: utf-8
from ..flock import flock
from ..logger import log
from . import net
from .. import time


class LocalNet(net.LocalNet):
    def __init__(self, hosts_file='/etc/hosts'):
        self.hosts_file = hosts_file

    def configure(self, mappings):
        self.nat(mappings)
        self.hosts(mappings)

    def nat(self, mappings):
        import iptc  # Not available on all platforms that might load this file
        table = iptc.Table6(iptc.Table6.MANGLE)
        table.autocommit = False
        chain = iptc.Chain(table, 'OUTPUT')
        for endpoint, upstreams in mappings.forwards.items():
            rule = iptc.Rule()
            rule.dst = str(endpoint)
            label = rule.create_match('comment')
            label.comment = 'drcloud//%s' % mappings.names[endpoint]
            for ip in upstreams:
                # TODO: Weights
                if isinstance(ip, net.IPv4):
                    # TODO: Taiga for IPv6<->IPv4
                    log.error('Not able to NAT IPv6 to IPv4 yet. (%s <=> %s)',
                              endpoint, ip)
                    continue
                dnat = rule.create_target('DNAT')
                dnat.to_destination = str(ip)
            chain.insert_rule(rule)
        table.commit()

    def hosts(self, mappings):
        updated_names = sort_and_format_hosts(mappings.names)
        with flock(self.hosts_file, seconds=0.1) as handle:
            txt = handle.read()
            # NB: For ~700 lines this takes about 120µs.
            lines = [_ for _ in txt.splitlines(False) if 'drcloud//' not in _]
            handle.seek(0)
            handle.write('\n'.join(lines + updated_names + ['']))


def sort_and_format_hosts(names):
    """
    >>> sort_and_format_hosts({})
    []
    """
    if len(names) <= 0:
        return []
    t = time.utc().isoformat()
    ipw = max(len(str(ip)) for ip in names.values())
    namew = max(len(str(name)) for name in names.keys())
    template = '{ip:{ipw}s} {name:{namew}s} # drcloud//{t}'
    lines = [(name.split('.')[::-1],   # Reversed hostname components, for sort
              template.format(ip=ip, name=name, ipw=ipw, namew=namew, t=t))
             for name, ip in names.items()]
    return [line for _, line in sorted(lines)]
