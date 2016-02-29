import pkg_resources

from .client import Cloud, DNS, Route, Service


def version():
    try:
        return pkg_resources.get_distribution(__package__).version
    except:
        pass
    try:
        return pkg_resources.resource_string(__package__, 'VERSION').strip()
    except:
        pass
    return '19991231'


__version__ = version()


__all__ = ['Cloud', 'DNS', 'Route', 'Service', '__version__']
