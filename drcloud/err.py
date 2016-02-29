class Err(Exception):
    """Parent class of all of Dr. Cloud's exceptions."""
    def __init__(self, *args, **kwargs):
        if 'underlying' in kwargs:
            self.underlying = kwargs['underlying']
            del kwargs['underlying']
        else:
            self.underlying = None
        super(Err, self).__init__(*args, **kwargs)
