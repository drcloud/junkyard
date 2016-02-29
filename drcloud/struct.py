from schematics.models import Model


class Struct(Model):
    def __init__(self, **kwargs):
        super(Struct, self).__init(kwargs, strict=False)
