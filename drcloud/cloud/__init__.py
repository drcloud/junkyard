class System(object):
    def acquire(self):
        raise NotImplementedError()

    def release(self):
        raise NotImplementedError()


class Cloud(System):
    def __init__(self, cloud, options=None, **kwargs):
        raise NotImplementedError()


class Service(System):
    def __init__(self, service, cloud, nodes=1, profile=None, options=None,
                 **kwargs):
        raise NotImplementedError()

    def run(self, task):
        raise NotImplementedError()
