from datetime import timedelta


class Inbox(object):
    """Synchronizes the local inbox.
    """
    etc = '/etc/drcloud'
    spools = '/var/spool/drcloud'
    timeout = 10
    lifetime = timedelta(minutes=15)
