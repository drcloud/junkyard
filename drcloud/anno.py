"""Annotations for class methods.
"""
from functools import wraps


def pre(other):
    def anno(m):
        @wraps(m)
        def n(self, *args, **kwargs):
            other(self)
            return m(self, *args, **kwargs)
        return n
    return anno


def runonce(m):
    @wraps(m)
    def n(self):
        attrname = '__' + m.__name__
        if not hasattr(self, attrname):
            m(self)
            setattr(self, attrname, True)
    return n


def computedfield(m):
    @wraps(m)
    def n(self):
        attrname = '__' + m.__name__
        if not hasattr(self, attrname):
            setattr(self, attrname, m(self))
        return getattr(self, attrname)
    return property(n)
