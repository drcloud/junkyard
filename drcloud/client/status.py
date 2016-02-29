from enum import Enum


class Status(object):
    pass


class DeclarationStatus(Enum, Status):
    Invalid = '- invalid'
    Saved = '+ saved'


class SystemStatus(Enum, Status):
    Changing = '~ changing'
    Failed = '! failed'
    InSpec = '+ in spec'
    Lost = '? lost'
    Rejected = '- rejected'
    Stopped = '+ stopped'
