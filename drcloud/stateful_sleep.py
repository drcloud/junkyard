from __future__ import absolute_import
from time import sleep

from .time import utc


def ticks(delta, duration=None):
    start = utc()
    last = start
    while duration is None or utc() - start < duration:
        while utc() - last > duration:
            last += duration
        sleep((duration - (utc() - last)).total_seconds())
        last = utc()
        yield last
    yield utc()
