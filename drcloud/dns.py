import re

from schematics.exceptions import ValidationError
from schematics.types import BaseType


class DomainNameType(BaseType):
    def validate_dns(self, dn):
        if not validate(dn):
            raise ValidationError('Not a valid LDH domain: %s' % dn)


ldh_re = re.compile('^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$')


def validate(dn):
    if dn.endswith('.'):
        dn = dn[:-1]
    if len(dn) < 1 or len(dn) > 253:
        return False
    return all(ldh_re.match(x) for x in dn.split('.'))
