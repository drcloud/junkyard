from .core import *


class DNS(object):
    """Something with DNS exposes a fully-qualified domain name."""
    def __init__(self, fqdn):
        self.fqdn = fqdn

    def dns(self):
        return self.fqdn


class Cloud(System, DNS):
    def __init__(self, name, provider=None, options={}):
        self._name = name
        self._provider = provider
        self._options = options

    def dns(self):
        return self.name

    @property
    def name(self):
        """The name of the cloud, a fully-qualified domain name."""
        return self._name

    @property
    def provider(self):
        """The name of the provider for the cloud."""
        return self._provider

    @property
    def options(self):
        """Provider specific options."""
        return self._options

    @options.setter
    def _set_options(self, options):
        self._options = options

    def __repr__(self):
        properties = [
            ('name', self._name),
            ('provider', self._provider),
            ('options', self._options),
        ]
        formatted = ', '.join('%s=%r' % (k, v) for k, v in properties
                              if v is not None and v != {})
        return '%s(%s)' % (self.__class__.__name__, formatted)


class Route(System):
    def __init__(self, entrypoint, upstreams=[], within=None):
        self._entrypoint = entrypoint
        self._upstreams = upstreams
        self._within = within

    @property
    def entrypoint(self):
        """The entrypoint, a fully-qualified domain name.

        The entrypoint receives traffic and this is forwarded to the upstreams.
        """
        return self._endpoint

    @property
    def upstreams(self):
        """Upstreams as a map of DNS names to weights."""
        return self._upstreams

    @upstreams.setter
    def _set_upstreams(self, upstreams):
        self._upstreams = upstreams

    @property
    def within(self):
        """Limit route to be visible only within a certain subomain."""
        return self._within

    def __repr__(self):
        properties = [
            ('entrypoint', self._entrypoint),
            ('upstreams', self._upstreams),
            ('within', self._within),
        ]
        formatted = ', '.join('%s=%r' % (k, v) for k, v in properties
                              if v is not None and v != {})
        return '%s(%s)' % (self.__class__.__name__, formatted)


class Service(System, DNS):
    def __init__(self, name, app=None, cloud=None,
                 profile=None, nodes=1, resources={}, config={}):
        self._name = name
        self._app = app
        self._cloud = cloud
        self._profile = profile
        self._nodes = nodes
        self._resources = resources
        self._config = config

    def dns(self):
        return '%s.%s' % (self.name, self.cloud.name)

    @property
    def name(self):
        """The name of the service."""
        return self._name

    @property
    def app(self):
        """The application program run by the service."""
        return self._app

    @app.setter
    def _set_app(self, app):
        self._app = app

    @property
    def cloud(self):
        """The cloud in which to run the service."""
        if self._cloud is None:
            raise ValueError('Do something to get the default cloud.')
        return self._cloud

    @property
    def profile(self):
        """The node profile (a simple string)."""
        return self._profile

    @profile.setter
    def _set_profile(self, profile):
        self._profile = profile

    @property
    def nodes(self):
        """The number of nodes to run."""
        return self._nodes

    @nodes.setter
    def _set_nodes(self, nodes):
        self._nodes = nodes

    @property
    def resources(self):
        """Detail resource specification for nodes."""
        return self._resources

    @resources.setter
    def _set_resources(self, resources):
        self._resources = resources

    @property
    def config(self):
        """Configuration settings to share with the application."""
        return self._config

    @config.setter
    def _set_config(self, config):
        self._config = config

    def __repr__(self):
        properties = [
            ('name', self._name),
            ('app', self._app),
            ('cloud', self._cloud),
            ('profile', self._profile),
            ('nodes', self._nodes),
            ('resources', self._resources),
            ('config', self._config),
        ]
        formatted = ', '.join('%s=%r' % (k, v) for k, v in properties
                              if v is not None and v != {})
        return '%s(%s)' % (self.__class__.__name__, formatted)
