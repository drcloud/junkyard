from __future__ import absolute_import
from datetime import datetime, timedelta
from numbers import Number
from time import sleep

import psycopg2.tz


def utc():
    return datetime.now(z)


def epoch(t=None, fractional=False):
    delta = (t or utc()) - unix0
    seconds, micros = delta.total_seconds(), delta.microseconds
    return seconds + (micros / 1000000.0 if fractional else 0)


def ticks(delta, duration=None):
    if isinstance(delta, Number):
        delta = timedelta(seconds=delta)
    start = utc()
    last = start
    while duration is None or utc() - start < duration:
        while utc() - last > delta:
            last += delta
        sleep((delta - (utc() - last)).total_seconds())
        last = utc()
        yield last
    yield utc()


z = psycopg2.tz.FixedOffsetTimezone(name='UTC')

unix0 = datetime(1970, 1, 1, tzinfo=z)
